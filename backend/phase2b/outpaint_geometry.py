"""
Phase 2B WP1 — server-owned outpaint geometry.

Everything in this module is computed on the server from validated enum
parameters only. Nothing here reads a client-supplied width, height, offset,
mask, prompt or graph. The client sends `output_preset`, `direction`, `anchor`,
`expansion_mode` and `style_mode` — nothing else can influence the canvas.

Placement contract
------------------
`direction` says where the NEW pixels go; `anchor` says where the source is
pinned on the expansion axis:

    direction=left    anchor=right   -> source flush to the right edge
    direction=right   anchor=left    -> source flush to the left edge
    direction=top     anchor=bottom  -> source flush to the bottom edge
    direction=bottom  anchor=top     -> source flush to the top edge
    direction=<any>   anchor=center  -> source centred on the expansion axis
    direction=symmetric anchor=center-> source centred on both axes

On the perpendicular axis the source is always centred.

Scaling contract
----------------
The source is never upscaled. It is downscaled (LANCZOS, aspect preserved)
only when it does not fit inside the canvas. The scaled source is the
authoritative "source region": its bytes are what get composited back and what
the integrity check hashes, so the check is exact and independent of any
sampler behaviour.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from typing import Any

from PIL import Image

PRESETS: dict[str, tuple[int, int]] = {
    "1200x627": (1200, 627),
    "1600x900": (1600, 900),
}

# Feathered mask edge (px) so the sampler blends into the source instead of
# leaving a hard seam. The composite step restores the exact source rectangle
# afterwards, so feathering never changes source pixels.
FEATHER_PX = 24


@dataclass(frozen=True)
class Placement:
    canvas_width: int
    canvas_height: int
    region_left: int
    region_top: int
    region_width: int
    region_height: int
    scaled: bool
    source_region_sha256: str

    @property
    def box(self) -> tuple[int, int, int, int]:
        return (
            self.region_left,
            self.region_top,
            self.region_left + self.region_width,
            self.region_top + self.region_height,
        )

    def as_provenance(self) -> dict[str, Any]:
        return {
            "canvas": [self.canvas_width, self.canvas_height],
            "source_region": [
                self.region_left,
                self.region_top,
                self.region_width,
                self.region_height,
            ],
            "source_downscaled": self.scaled,
            "source_region_sha256": self.source_region_sha256,
            "feather_px": FEATHER_PX,
        }


def resolve_preset(output_preset: str) -> tuple[int, int]:
    if output_preset not in PRESETS:
        raise ValueError("unsupported output preset")
    return PRESETS[output_preset]


def _offset(free: int, mode: str) -> int:
    """Offset of the source inside `free` spare pixels on one axis."""
    if free <= 0:
        return 0
    if mode == "start":
        return 0
    if mode == "end":
        return free
    return free // 2  # centre


def _axis_modes(direction: str, anchor: str) -> tuple[str, str]:
    """Return (horizontal_mode, vertical_mode) as start/center/end."""
    if direction == "symmetric":
        return "center", "center"
    if direction in ("left", "right"):
        if anchor == "center":
            horizontal = "center"
        else:
            # anchor names the edge the source sticks to
            horizontal = "end" if anchor == "right" else "start"
        return horizontal, "center"
    # top / bottom
    if anchor == "center":
        vertical = "center"
    else:
        vertical = "end" if anchor == "bottom" else "start"
    return "center", vertical


def plan(
    *,
    source: Image.Image,
    output_preset: str,
    direction: str,
    anchor: str,
) -> tuple[Image.Image, Placement]:
    """Return (scaled_source_rgb, placement)."""
    canvas_w, canvas_h = resolve_preset(output_preset)
    src = source.convert("RGB")
    src_w, src_h = src.size

    scale = min(canvas_w / src_w, canvas_h / src_h, 1.0)
    if scale < 1.0:
        region_w = max(1, int(round(src_w * scale)))
        region_h = max(1, int(round(src_h * scale)))
        src = src.resize((region_w, region_h), Image.LANCZOS)
    else:
        region_w, region_h = src_w, src_h

    h_mode, v_mode = _axis_modes(direction, anchor)
    left = _offset(canvas_w - region_w, h_mode)
    top = _offset(canvas_h - region_h, v_mode)

    region_bytes = io.BytesIO()
    src.save(region_bytes, format="PNG", compress_level=6)
    digest = hashlib.sha256(region_bytes.getvalue()).hexdigest()

    return src, Placement(
        canvas_width=canvas_w,
        canvas_height=canvas_h,
        region_left=left,
        region_top=top,
        region_width=region_w,
        region_height=region_h,
        scaled=scale < 1.0,
        source_region_sha256=digest,
    )


def build_canvas_and_mask(
    scaled_source: Image.Image, placement: Placement
) -> tuple[bytes, bytes]:
    """Padded canvas (edge-extended, so the sampler starts from plausible
    colour) plus the inpaint mask. White = generate, black = keep.
    Both are produced here, on the server; neither is ever accepted from a
    client, and neither is written outside the job temp directory."""
    canvas = Image.new("RGB", (placement.canvas_width, placement.canvas_height))

    # Edge extension: stretch the 1px border of the source outward so the
    # generated region starts from source-adjacent colour, not grey.
    left, top, right, bottom = placement.box
    if left > 0:
        strip = scaled_source.crop((0, 0, 1, placement.region_height))
        canvas.paste(strip.resize((left, placement.region_height)), (0, top))
    if right < placement.canvas_width:
        strip = scaled_source.crop(
            (placement.region_width - 1, 0, placement.region_width, placement.region_height)
        )
        canvas.paste(
            strip.resize((placement.canvas_width - right, placement.region_height)),
            (right, top),
        )
    if top > 0:
        strip = canvas.crop((0, top, placement.canvas_width, top + 1))
        canvas.paste(strip.resize((placement.canvas_width, top)), (0, 0))
    if bottom < placement.canvas_height:
        strip = canvas.crop((0, bottom - 1, placement.canvas_width, bottom))
        canvas.paste(
            strip.resize((placement.canvas_width, placement.canvas_height - bottom)),
            (0, bottom),
        )
    canvas.paste(scaled_source, (left, top))

    mask = Image.new("L", (placement.canvas_width, placement.canvas_height), 255)
    keep_left = min(placement.canvas_width, left + FEATHER_PX)
    keep_top = min(placement.canvas_height, top + FEATHER_PX)
    keep_right = max(keep_left, right - FEATHER_PX)
    keep_bottom = max(keep_top, bottom - FEATHER_PX)
    mask.paste(0, (keep_left, keep_top, keep_right, keep_bottom))

    canvas_buf, mask_buf = io.BytesIO(), io.BytesIO()
    canvas.save(canvas_buf, format="PNG", compress_level=6)
    mask.save(mask_buf, format="PNG", compress_level=6)
    return canvas_buf.getvalue(), mask_buf.getvalue()


def composite_and_verify(
    *,
    generated_png: bytes,
    scaled_source: Image.Image,
    placement: Placement,
) -> tuple[bytes, bool]:
    """Paste the untouched source rectangle back over the generated canvas,
    then prove byte-for-byte that the source region survived.

    Returns (output_png, source_region_verified). A False verdict must fail the
    job: no asset row, no storage object.
    """
    generated = Image.open(io.BytesIO(generated_png))
    generated.load()
    generated = generated.convert("RGB")
    if generated.size != (placement.canvas_width, placement.canvas_height):
        generated = generated.resize(
            (placement.canvas_width, placement.canvas_height), Image.LANCZOS
        )

    generated.paste(scaled_source, (placement.region_left, placement.region_top))

    crop = generated.crop(placement.box)
    crop_buf = io.BytesIO()
    crop.save(crop_buf, format="PNG", compress_level=6)
    verified = (
        hashlib.sha256(crop_buf.getvalue()).hexdigest() == placement.source_region_sha256
    )

    out = io.BytesIO()
    generated.save(out, format="PNG", compress_level=6)
    return out.getvalue(), verified
