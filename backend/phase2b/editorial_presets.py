"""
Module C — server-owned editorial layout presets (text-on-image).

Same discipline as `scene_presets.py`: the *only* things a client can send are
enum keys plus the copy (headline / standfirst / label) that is typeset locally
— never into the provider instruction. Every word of instruction text that
reaches the hosted provider is written here, in the server image, and is covered
by the workflow config hash. There is no free-text path into this module.

The module is split in two stages:

  * PICTURE — a subject-preserving edit that also reserves a quiet "copy zone"
    for type. Zone instructions are phrased positively (describe what the zone
    *is*), because negations in provider instructions behave like requests.
  * TYPE — drawn locally afterwards by `editorial_typography.py`, never by the
    picture model.

Adding or editing a preset is a code change plus a registry version bump, not a
runtime configuration change.
"""

from __future__ import annotations

import hashlib
from typing import Any

PRESET_TABLE_VERSION = "editorial-presets-1"

COMPOSED_INSTRUCTION_MAX_CHARS = 2200

# --------------------------------------------------------------------------- #
# Editorial looks — fixed, server-owned instructions
# --------------------------------------------------------------------------- #
#
# Wording rules (learned in WP1b): phrase everything positively. Never write
# "no X" — describe the desired scene instead. The subject clause mirrors the
# proven Product scene phrasing so fidelity behaviour carries over.

_SUBJECT_CLAUSE = (
    " Keep the photographed subject exactly as it is: same shape, same colours, "
    "same label text, same orientation and same position in frame."
)

EDITORIAL_LOOKS: dict[str, dict[str, str]] = {
    "cover_shot": {
        "label": "Cover shot",
        "instruction": (
            "Reframe the scene as a magazine cover photograph. Surround the "
            "subject with a deep, calm, softly graduated backdrop in a single "
            "muted tone, lit by one strong directional key light with a gentle "
            "falloff, in the manner of a studio cover portrait."
            + _SUBJECT_CLAUSE
        ),
    },
    "lifestyle_spread": {
        "label": "Lifestyle spread",
        "instruction": (
            "Reframe the scene as a candid editorial lifestyle photograph: a "
            "warm, naturally lit interior or terrace at a comfortable distance, "
            "soft daylight, gentle depth of field, lived-in and relaxed, in the "
            "manner of a Sunday supplement spread."
            + _SUBJECT_CLAUSE
        ),
    },
    "flat_lay": {
        "label": "Flat lay",
        "instruction": (
            "Reframe the scene as an overhead flat-lay editorial photograph: the "
            "subject resting on an even, matte surface with a few simple "
            "complementary objects arranged with generous breathing room, lit by "
            "soft, perfectly even daylight from above."
            + _SUBJECT_CLAUSE
        ),
    },
    "documentary": {
        "label": "Documentary",
        "instruction": (
            "Reframe the scene as a documentary editorial photograph: a real "
            "location with honest textures, cool natural window light, quiet and "
            "observational, in the manner of reportage photography."
            + _SUBJECT_CLAUSE
        ),
    },
}

LOOK_ORDER: tuple[str, ...] = (
    "cover_shot",
    "lifestyle_spread",
    "flat_lay",
    "documentary",
)

# --------------------------------------------------------------------------- #
# People switch — enum-only, server-owned phrasing
# --------------------------------------------------------------------------- #
#
# Generated people are allowed in editorial scenes; uploads containing
# identifiable people remain prohibited (unchanged Track C rule). Phrased
# positively again: the "none" option describes a still scene, not an absence.

PEOPLE_OPTIONS: dict[str, dict[str, str]] = {
    "none": {
        "label": "No people",
        "instruction": (
            " The scene is a still arrangement: only the subject, the setting "
            "and still-life props appear in frame."
        ),
    },
    "background_figures": {
        "label": "Background figures",
        "instruction": (
            " A few softly blurred, anonymous figures move through the far "
            "background, small in frame and turned away, adding life while the "
            "subject stays the clear centre of attention."
        ),
    },
    "foreground_model": {
        "label": "Foreground model",
        "instruction": (
            " A relaxed model interacts naturally with the scene beside the "
            "subject — hands, posture and gaze supporting it like in a magazine "
            "spread — with the subject remaining the sharp hero of the frame."
        ),
    },
}

PEOPLE_ORDER: tuple[str, ...] = ("none", "background_figures", "foreground_model")

DEFAULT_PEOPLE = "none"

# --------------------------------------------------------------------------- #
# Output presets — absolute sizes only (no client-supplied geometry)
# --------------------------------------------------------------------------- #

OUTPUT_PRESETS: dict[str, tuple[int, int]] = {
    "1600x900": (1600, 900),
    "1080x1080": (1080, 1080),
    "1080x1920": (1080, 1920),
    "800x2000": (800, 2000),
}

# The hosted edit model takes an aspect ratio, not a pixel size; the adapter
# resizes/crops to the exact preset afterwards so the API contract is exact
# regardless of provider output.
ASPECT_RATIOS: dict[str, str] = {
    "1600x900": "16:9",
    "1080x1080": "1:1",
    "1080x1920": "9:16",
    "800x2000": "9:16",
}

# --------------------------------------------------------------------------- #
# Copy zones — fixed geometry per shape, enum-only
# --------------------------------------------------------------------------- #
#
# Each zone is a fractional rectangle (x0, y0, x1, y1) of the canvas. The
# instruction describes the zone as a calm, even area for the layout to rest on
# — positive phrasing, never "keep empty".

COPY_ZONES: dict[str, dict[str, Any]] = {
    "left_third": {
        "label": "Left third",
        "rect": (0.0, 0.0, 0.34, 1.0),
        "instruction": (
            " The left third of the frame is a calm, even, softly lit area of "
            "gentle uniform tone with very low detail, like a clean studio wall, "
            "ready to carry printed text."
        ),
    },
    "right_third": {
        "label": "Right third",
        "rect": (0.66, 0.0, 1.0, 1.0),
        "instruction": (
            " The right third of the frame is a calm, even, softly lit area of "
            "gentle uniform tone with very low detail, like a clean studio wall, "
            "ready to carry printed text."
        ),
    },
    "upper_third": {
        "label": "Upper third",
        "rect": (0.0, 0.0, 1.0, 0.34),
        "instruction": (
            " The upper third of the frame is a calm, even, softly lit area of "
            "gentle uniform tone with very low detail, like open sky or a clean "
            "wall, ready to carry printed text."
        ),
    },
    "lower_third": {
        "label": "Lower third",
        "rect": (0.0, 0.66, 1.0, 1.0),
        "instruction": (
            " The lower third of the frame is a calm, even, softly lit area of "
            "gentle uniform tone with very low detail, like a smooth tabletop in "
            "soft focus, ready to carry printed text."
        ),
    },
}

# Which zones make sense for each canvas shape.
SHAPE_ZONES: dict[str, tuple[str, ...]] = {
    "1600x900": ("left_third", "right_third", "lower_third"),
    "1080x1080": ("lower_third", "upper_third"),
    "1080x1920": ("upper_third", "lower_third"),
    "800x2000": ("upper_third", "lower_third"),
}

DEFAULT_ZONE: dict[str, str] = {
    "1600x900": "left_third",
    "1080x1080": "lower_third",
    "1080x1920": "upper_third",
    "800x2000": "upper_third",
}


def resolve_output_preset(preset: str) -> tuple[int, int]:
    if preset not in OUTPUT_PRESETS:
        raise ValueError(f"unknown editorial output preset: {preset!r}")
    return OUTPUT_PRESETS[preset]


def aspect_ratio(preset: str) -> str:
    return ASPECT_RATIOS.get(preset, "1:1")


def zone_rect(zone: str, width: int, height: int) -> tuple[int, int, int, int]:
    """Absolute pixel rectangle for a zone on a width x height canvas."""
    if zone not in COPY_ZONES:
        raise ValueError(f"unknown copy zone: {zone!r}")
    fx0, fy0, fx1, fy1 = COPY_ZONES[zone]["rect"]
    return (
        int(round(fx0 * width)),
        int(round(fy0 * height)),
        int(round(fx1 * width)),
        int(round(fy1 * height)),
    )


# --------------------------------------------------------------------------- #
# Composition
# --------------------------------------------------------------------------- #


def look_instruction(look: str) -> str:
    """Look wording, byte-for-byte identical for every run of that look."""
    if look not in EDITORIAL_LOOKS:
        raise ValueError(f"unknown editorial look: {look!r}")
    return EDITORIAL_LOOKS[look]["instruction"]


def people_instruction(people: str | None) -> str:
    chosen = people or DEFAULT_PEOPLE
    if chosen not in PEOPLE_OPTIONS:
        raise ValueError(f"unknown people option: {people!r}")
    return PEOPLE_OPTIONS[chosen]["instruction"]


def zone_instruction(zone: str, output_preset: str) -> str:
    if output_preset not in OUTPUT_PRESETS:
        raise ValueError(f"unknown editorial output preset: {output_preset!r}")
    if zone not in SHAPE_ZONES[output_preset]:
        raise ValueError(f"copy zone {zone!r} is not available for {output_preset}")
    return COPY_ZONES[zone]["instruction"]


def compose_instruction(
    look: str,
    people: str | None,
    copy_zone: str,
    output_preset: str,
) -> str:
    """The complete provider instruction. Assembled from server constants only."""
    text = (
        look_instruction(look)
        + people_instruction(people)
        + zone_instruction(copy_zone, output_preset)
    )
    if len(text) > COMPOSED_INSTRUCTION_MAX_CHARS:
        raise ValueError("composed instruction is too long")
    return text


def fingerprint(
    look: str,
    people: str | None,
    copy_zone: str,
    output_preset: str,
) -> dict[str, Any]:
    """Recorded in provenance so a layout traces back to exact preset text."""
    instruction = compose_instruction(look, people, copy_zone, output_preset)
    return {
        "look": look,
        "people": people or DEFAULT_PEOPLE,
        "copy_zone": copy_zone,
        "output_preset": output_preset,
        "instruction_sha256": hashlib.sha256(instruction.encode()).hexdigest(),
        "instruction_chars": len(instruction),
        "preset_table_version": PRESET_TABLE_VERSION,
    }


def public_catalog() -> dict[str, Any]:
    """Safe for the UI: keys, labels and geometry only — never the wording."""
    return {
        "looks": [
            {"key": key, "label": EDITORIAL_LOOKS[key]["label"]} for key in LOOK_ORDER
        ],
        "people": [
            {"key": key, "label": PEOPLE_OPTIONS[key]["label"]} for key in PEOPLE_ORDER
        ],
        "output_presets": [
            {
                "key": key,
                "width": OUTPUT_PRESETS[key][0],
                "height": OUTPUT_PRESETS[key][1],
                "copy_zones": [
                    {"key": z, "label": COPY_ZONES[z]["label"]}
                    for z in SHAPE_ZONES[key]
                ],
            }
            for key in OUTPUT_PRESETS
        ],
        "preset_table_version": PRESET_TABLE_VERSION,
    }
