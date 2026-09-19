"""
Module C type stage — local typesetting over the generated picture.

The picture model never draws text. This module draws the headline, standfirst
and label locally with Pillow over the reserved copy zone, so type is always
spelt correctly, reproducible, and re-typesettable without a new generation.

Layered output: the clean picture is never modified here; `typeset()` returns a
*new* image plus a metadata record, and the caller stores both as separate
assets.

Type presets are enum-only and server-owned (font family, weight, casing,
scale). Clients pick a preset key and supply the copy — never fonts, sizes or
CSS. Fonts are the open-licence families bundled in ./fonts (OFL).

Copy limits are enforced here as well as in the request parser; both reject
over-length copy rather than truncating silently.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from PIL import Image, ImageDraw, ImageFont, ImageStat

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

HEADLINE_MAX_CHARS = 90
STANDFIRST_MAX_CHARS = 200
LABEL_MAX_CHARS = 40

LIGHT = (250, 250, 248)
DARK = (26, 26, 28)

# Below this contrast ratio the scrim is applied automatically (WCAG AA text).
MIN_CONTRAST = 4.5
SCRIM_ALPHA = 110

# --------------------------------------------------------------------------- #
# Type presets — enum-only
# --------------------------------------------------------------------------- #

TYPE_PRESETS: dict[str, dict[str, Any]] = {
    "display_sans": {
        "label": "Display sans",
        "font_file": "LibreFranklin.ttf",
        "weight": 700,
        "headline_scale": 0.115,  # fraction of the zone's short side, per line
        "uppercase_headline": False,
        "letter_tracking": 0.0,
    },
    "editorial_serif": {
        "label": "Editorial serif",
        "font_file": "LibreBaskerville.ttf",
        "weight": 700,
        "headline_scale": 0.105,
        "uppercase_headline": False,
        "letter_tracking": 0.0,
    },
    "condensed_caps": {
        "label": "Condensed caps",
        "font_file": "Oswald.ttf",
        "weight": 500,
        "headline_scale": 0.125,
        "uppercase_headline": True,
        "letter_tracking": 0.02,  # fraction of font size, added between glyphs
    },
}

DEFAULT_TYPE_PRESET = "display_sans"

# --------------------------------------------------------------------------- #
# Copy validation
# --------------------------------------------------------------------------- #


def _clean_copy(value: Any, field: str, max_chars: int, required: bool) -> Optional[str]:
    if value is None:
        if required:
            raise ValueError(f"{field} is required")
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text")
    collapsed = " ".join(value.split())
    if required and not collapsed:
        raise ValueError(f"{field} is required")
    if len(collapsed) > max_chars:
        raise ValueError(f"{field} must be {max_chars} characters or fewer")
    return collapsed or None


def validate_copy(
    headline: Any,
    standfirst: Any = None,
    label: Any = None,
) -> dict[str, Optional[str]]:
    return {
        "headline": _clean_copy(headline, "headline", HEADLINE_MAX_CHARS, True),
        "standfirst": _clean_copy(standfirst, "standfirst", STANDFIRST_MAX_CHARS, False),
        "label": _clean_copy(label, "label", LABEL_MAX_CHARS, False),
    }


# --------------------------------------------------------------------------- #
# Font loading and measuring
# --------------------------------------------------------------------------- #

_font_cache: dict[tuple[str, int, int], ImageFont.FreeTypeFont] = {}


def load_font(preset_key: str, size_px: int) -> ImageFont.FreeTypeFont:
    preset = TYPE_PRESETS[preset_key]
    cache_key = (preset["font_file"], int(preset["weight"]), size_px)
    font = _font_cache.get(cache_key)
    if font is None:
        font = ImageFont.truetype(
            os.path.join(FONT_DIR, preset["font_file"]), size_px
        )
        try:
            font.set_variation_by_axes([int(preset["weight"])])
        except Exception:
            pass  # static font — weight is baked into the file
        _font_cache[cache_key] = font
    return font


def _text_width(draw: ImageDraw.ImageDraw, text: str, font, tracking: float) -> float:
    width = draw.textlength(text, font=font)
    if tracking and len(text) > 1:
        width += tracking * font.size * (len(text) - 1)
    return width


def _wrap(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    max_width: float,
    tracking: float,
) -> list[str]:
    """Greedy wrap onto lines that fit max_width. Raises if a single word is
    wider than the zone — the caller shrinks the font and retries."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if _text_width(draw, trial, font, tracking) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    for line in lines:
        if _text_width(draw, line, font, tracking) > max_width:
            raise ValueError("word too wide")
    return lines


def _fit_headline(
    draw: ImageDraw.ImageDraw,
    headline: str,
    preset_key: str,
    max_width: float,
    max_height: float,
) -> tuple[Any, list[str]]:
    """Largest font size whose wrapped headline fits the zone. Deterministic:
    same inputs always produce the same size and break points."""
    preset = TYPE_PRESETS[preset_key]
    short_side = min(max_width, max_height)
    start = max(12, int(short_side * preset["headline_scale"] * 3))
    tracking = float(preset["letter_tracking"])
    size = start
    while size > 8:
        font = load_font(preset_key, size)
        try:
            lines = _wrap(draw, headline, font, max_width, tracking)
        except ValueError:
            size -= 2
            continue
        line_height = font.getbbox("Ag")[3] - font.getbbox("Ag")[1]
        block_height = line_height * len(lines) * 1.15
        if block_height <= max_height and all(
            _text_width(draw, ln, font, tracking) <= max_width for ln in lines
        ):
            return font, lines
        size -= 2
    font = load_font(preset_key, 9)
    return font, _wrap(draw, headline, font, max_width, tracking)


# --------------------------------------------------------------------------- #
# Contrast and scrim
# --------------------------------------------------------------------------- #


def _relative_luminance(v: float) -> float:
    """sRGB channel value (0-1) -> WCAG relative luminance contribution."""
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _zone_luminance(image: Image.Image, rect: tuple[int, int, int, int]) -> float:
    crop = image.convert("L").crop(rect).resize((32, 32))
    return _relative_luminance(ImageStat.Stat(crop).mean[0] / 255.0)


def _contrast_ratio(lum_text: float, lum_bg: float) -> float:
    high, low = max(lum_text, lum_bg), min(lum_text, lum_bg)
    return (high + 0.05) / (low + 0.05)


def choose_text_colour(image: Image.Image, rect: tuple[int, int, int, int]) -> dict[str, Any]:
    """Pick light or dark type for the zone; add a scrim when neither reaches
    the contrast floor on its own."""
    bg = _zone_luminance(image, rect)
    # Relative luminance approximations for the two ink colours.
    light_lum, dark_lum = 0.95, 0.03
    light_ratio = _contrast_ratio(light_lum, bg)
    dark_ratio = _contrast_ratio(dark_lum, bg)
    use_light = light_ratio >= dark_ratio
    best = max(light_ratio, dark_ratio)
    scrim = best < MIN_CONTRAST
    if scrim:
        # Scrim darkens (for light text) or lightens (for dark text) the zone.
        scrim_lum = 0.05 if use_light else 0.92
        best = _contrast_ratio(light_lum if use_light else dark_lum, scrim_lum)
    return {
        "colour": LIGHT if use_light else DARK,
        "colour_name": "light" if use_light else "dark",
        "scrim": scrim,
        "contrast_ratio": round(best, 2),
        "zone_luminance": round(bg, 3),
    }


def zone_usability(
    image: Image.Image, rect: tuple[int, int, int, int]
) -> dict[str, Any]:
    """How calm the zone came back: 0.0 (flat, ideal) to 1.0 (busy). Combines
    luminance variance with a cheap edge-density estimate. The caller reports
    this so a too-busy run can be reordered rather than shipped."""
    # NEAREST: averaging filters would wash fine grain out and under-report
    # busy zones.
    crop = image.convert("L").crop(rect).resize((64, 64), Image.NEAREST)
    stat = ImageStat.Stat(crop)
    variance_score = min(stat.stddev[0] / 64.0, 1.0)
    px = crop.load()
    edges = 0
    for y in range(63):
        for x in range(63):
            if abs(px[x, y] - px[x + 1, y]) > 28 or abs(px[x, y] - px[x, y + 1]) > 28:
                edges += 1
    edge_score = min(edges / (63 * 63 * 0.25), 1.0)
    busy = round(0.5 * variance_score + 0.5 * edge_score, 3)
    return {"busy": busy, "usable": busy < 0.35}


# --------------------------------------------------------------------------- #
# Typesetting
# --------------------------------------------------------------------------- #


def typeset(
    image: Image.Image,
    zone_rect: tuple[int, int, int, int],
    *,
    headline: Any,
    standfirst: Any = None,
    label: Any = None,
    type_preset: str = DEFAULT_TYPE_PRESET,
) -> tuple[Image.Image, dict[str, Any]]:
    """Return (typeset image, metadata). The input image is never mutated."""
    if type_preset not in TYPE_PRESETS:
        raise ValueError(f"unknown type preset: {type_preset!r}")
    copy = validate_copy(headline, standfirst, label)
    preset = TYPE_PRESETS[type_preset]

    out = image.convert("RGBA")
    draw = ImageDraw.Draw(out)
    zx0, zy0, zx1, zy1 = zone_rect
    zone_w, zone_h = zx1 - zx0, zy1 - zy0
    pad_x = int(zone_w * 0.09)
    pad_y = int(zone_h * 0.12)
    text_w = zone_w - 2 * pad_x
    text_h = zone_h - 2 * pad_y

    contrast = choose_text_colour(image, zone_rect)
    ink = contrast["colour"]

    headline_text = copy["headline"]
    if preset["uppercase_headline"]:
        headline_text = headline_text.upper()
    font, lines = _fit_headline(draw, headline_text, type_preset, text_w, text_h)
    line_height = int(font.size * 1.15)
    tracking = float(preset["letter_tracking"])

    label_font = load_font(type_preset, max(12, int(font.size * 0.32)))
    stand_font = load_font("editorial_serif", max(12, int(font.size * 0.4)))
    if type_preset == "editorial_serif":
        stand_font = load_font(type_preset, max(12, int(font.size * 0.4)))

    label_text = copy["label"].upper() if copy["label"] else None
    label_h = int(font.size * 0.5) if label_text else 0
    stand_lines: list[str] = []
    stand_h = 0
    if copy["standfirst"]:
        stand_lines = _wrap(draw, copy["standfirst"], stand_font, text_w, 0.0)
        stand_h = int(stand_font.size * 1.3) * len(stand_lines)

    gap = int(font.size * 0.45)
    block_h = (
        label_h
        + (gap // 2 if label_text else 0)
        + line_height * len(lines)
        + (gap + stand_h if stand_lines else 0)
    )
    top = zy0 + pad_y + max(0, (text_h - block_h) // 2)

    if contrast["scrim"]:
        scrim_fill = (10, 10, 12, SCRIM_ALPHA) if ink == LIGHT else (252, 252, 250, SCRIM_ALPHA)
        overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
        ImageDraw.Draw(overlay).rectangle(
            [zx0, zy0, zx1, zy1], fill=scrim_fill
        )
        out = Image.alpha_composite(out, overlay)
        draw = ImageDraw.Draw(out)

    def _draw_tracked(x: int, y: int, text: str, fnt, trk: float) -> None:
        if not trk:
            draw.text((x, y), text, font=fnt, fill=ink + (255,))
            return
        cx = x
        for ch in text:
            draw.text((cx, y), ch, font=fnt, fill=ink + (255,))
            cx += draw.textlength(ch, font=fnt) + trk * fnt.size

    y = top
    if label_text:
        _draw_tracked(zx0 + pad_x, y, label_text, label_font, 0.06)
        y += label_h + gap // 2
    for ln in lines:
        _draw_tracked(zx0 + pad_x, y, ln, font, tracking)
        y += line_height
    if stand_lines:
        y += gap
        for ln in stand_lines:
            draw.text((zx0 + pad_x, y), ln, font=stand_font, fill=ink + (235,))
            y += int(stand_font.size * 1.3)

    metadata = {
        "type_preset": type_preset,
        "headline": copy["headline"],
        "standfirst": copy["standfirst"],
        "label": copy["label"],
        "headline_font_size_px": font.size,
        "headline_lines": len(lines),
        "ink": contrast["colour_name"],
        "scrim": contrast["scrim"],
        "contrast_ratio": contrast["contrast_ratio"],
        "zone_luminance": contrast["zone_luminance"],
        "font_family": preset["label"],
    }
    return out.convert("RGB"), metadata


def public_type_catalog() -> dict[str, Any]:
    """Safe for the UI: preset keys/labels and copy limits only."""
    return {
        "type_presets": [
            {"key": key, "label": TYPE_PRESETS[key]["label"]} for key in TYPE_PRESETS
        ],
        "headline_max_chars": HEADLINE_MAX_CHARS,
        "standfirst_max_chars": STANDFIRST_MAX_CHARS,
        "label_max_chars": LABEL_MAX_CHARS,
    }
