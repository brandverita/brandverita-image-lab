"""
Phase 2B WP2 — server-owned product scene presets (Module B).

The whole point of this module: the *only* thing a client can send is an enum.
Every word of instruction text that reaches the hosted provider is written here,
in the server image, and is covered by the workflow config hash. There is no
free-text path into Module B — `prompt`, `negative_prompt`, `image_url` and
friends are already in advanced.FORBIDDEN_KEYS and are rejected before this
module is consulted.

Adding or editing a preset is a code change plus a registry version bump, not a
runtime configuration change.
"""

from __future__ import annotations

from typing import Any

# --------------------------------------------------------------------------- #
# Scene directions — fixed, server-owned instructions
# --------------------------------------------------------------------------- #

SCENE_PRESETS: dict[str, dict[str, Any]] = {
    "clean_studio": {
        "label": "Clean studio",
        "instruction": (
            "Replace the background with a clean, seamless studio backdrop in a "
            "light neutral grey. Keep the product exactly as it is: same shape, "
            "same colours, same label text, same orientation and same position "
            "in frame. Add a soft, even studio light from the upper left and a "
            "subtle contact shadow directly under the product. No props, no "
            "text, no logos, no people, no reflections of other objects."
        ),
    },
    "premium_neutral": {
        "label": "Premium neutral",
        "instruction": (
            "Replace the background with a premium, minimal set: a smooth matte "
            "surface in a warm off-white tone with a gentle gradient falloff "
            "behind the product. Keep the product completely unchanged in shape, "
            "colour, label text, orientation and position. Soft directional key "
            "light, restrained shadow. No props, no text, no logos, no people."
        ),
    },
    "warm_lifestyle": {
        "label": "Warm lifestyle",
        "instruction": (
            "Place the product on a warm, softly lit interior surface with a "
            "gently blurred domestic background. Keep the product completely "
            "unchanged in shape, colour, label text, orientation and position. "
            "Natural window light from the left, shallow depth of field. No "
            "recognisable brands other than the product, no text overlays, no "
            "people, no hands."
        ),
    },
    "natural_surface": {
        "label": "Natural surface",
        "instruction": (
            "Place the product on a natural stone or light wood surface with a "
            "softly out-of-focus neutral background. Keep the product completely "
            "unchanged in shape, colour, label text, orientation and position. "
            "Even daylight, realistic contact shadow. No props, no text, no "
            "logos, no people."
        ),
    },
}

# Optional lighting/finish modifier. Also an enum; also server-owned text.
BACKGROUND_STYLES: dict[str, str] = {
    "neutral": "",
    "soft_shadow": " Emphasise a soft, diffuse shadow beneath the product.",
    "high_key": " Bright high-key lighting with minimal shadow.",
    "editorial": " Slightly moodier editorial lighting with a single soft key light.",
}

DEFAULT_BACKGROUND_STYLE = "neutral"

# --------------------------------------------------------------------------- #
# Output presets — absolute sizes only (no client-supplied geometry)
# --------------------------------------------------------------------------- #

OUTPUT_PRESETS: dict[str, tuple[int, int]] = {
    "1080x1080": (1080, 1080),
    "1080x1350": (1080, 1350),
    "1200x627": (1200, 627),
    "1600x900": (1600, 900),
}

# BFL takes an aspect ratio, not a pixel size; the adapter resizes to the exact
# preset afterwards so the API contract is exact regardless of provider output.
ASPECT_RATIOS: dict[str, str] = {
    "1080x1080": "1:1",
    "1080x1350": "4:5",
    "1200x627": "16:9",
    "1600x900": "16:9",
}


def resolve_output_preset(preset: str) -> tuple[int, int]:
    if preset not in OUTPUT_PRESETS:
        raise ValueError(f"unknown product_scene output preset: {preset!r}")
    return OUTPUT_PRESETS[preset]


def aspect_ratio(preset: str) -> str:
    return ASPECT_RATIOS.get(preset, "1:1")


def build_instruction(scene_direction: str, background_style: str | None) -> str:
    """The complete provider instruction. Assembled from server constants only."""
    if scene_direction not in SCENE_PRESETS:
        raise ValueError(f"unknown scene_direction: {scene_direction!r}")
    style = background_style or DEFAULT_BACKGROUND_STYLE
    if style not in BACKGROUND_STYLES:
        raise ValueError(f"unknown background_style: {style!r}")
    return SCENE_PRESETS[scene_direction]["instruction"] + BACKGROUND_STYLES[style]


def fingerprint(scene_direction: str, background_style: str | None) -> dict[str, Any]:
    """Recorded in provenance so a result can be traced to exact preset text."""
    import hashlib

    instruction = build_instruction(scene_direction, background_style)
    return {
        "scene_direction": scene_direction,
        "background_style": background_style or DEFAULT_BACKGROUND_STYLE,
        "instruction_sha256": hashlib.sha256(instruction.encode()).hexdigest(),
        "instruction_chars": len(instruction),
        "preset_table_version": "wp2-scene-presets-1",
    }


def public_catalog() -> list[dict[str, str]]:
    """Safe for the Lab UI: labels and keys only, never the instruction text."""
    return [
        {"scene_direction": key, "label": value["label"]}
        for key, value in SCENE_PRESETS.items()
    ]
