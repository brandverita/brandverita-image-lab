"""
Brand-consistency prompt layers for text-to-image (flux_text_to_image).

Three layers, one composed prompt:

    [LAYER 1 — SEASONAL ATMOSPHERE]  when + mood        (varies per picture)
    [LAYER 2 — SETTING & VISUAL DNA] where + look       (the brand anchor)
    [LAYER 3 — SUBJECT HERO]         what is being sold (varies per picture)
    [UNIVERSAL QUALITY TAIL]         fixed, per aspect note only

Consistency rules enforced here, not in any client:

* Layer 2 wording is a server constant, emitted byte-for-byte identical for
  every run of that world. Nothing in a request can re-word it.
* The quality tail is identical for every combination; only the framing note
  follows the chosen canvas shape.
* The client sends enum keys plus one short subject line. It never sends,
  receives, or edits the layer text.

Editing shipped wording means bumping LAYER_TABLE_VERSION, so an older picture
can still be traced to the exact text that produced it.
"""

from __future__ import annotations

import hashlib
from typing import Any

LAYER_TABLE_VERSION = "prompt-layers-1"

SUBJECT_MAX_CHARS = 200
COMPOSED_PROMPT_MAX_CHARS = 2000

# --------------------------------------------------------------------------- #
# Layer 1 — seasonal atmosphere (when + mood)
# --------------------------------------------------------------------------- #

SEASON_PRESETS: dict[str, dict[str, str]] = {
    "autumn": {
        "label": "Autumn",
        "hint": "Golden afternoon light, harvest tones",
        "text": (
            "A golden, hazy autumn afternoon scene, slow-falling leaves and warm "
            "amber light, hints of woodsmoke and ripe harvest, palette of rust, "
            "ochre, and deep burgundy, reflective and cozy mood."
        ),
    },
    "sales": {
        "label": "Sales",
        "hint": "Bright, confident, offer-ready",
        "text": (
            "A bright, confident daytime scene with crisp clean light, a sense of "
            "fresh arrivals and generous abundance, uncluttered space around the "
            "subject, palette of clean white, warm sand, and a single saturated "
            "accent, upbeat and decisive mood."
        ),
    },
    "promotion": {
        "label": "Promotion",
        "hint": "Energetic, launch moment",
        "text": (
            "An energetic late-morning scene with lively directional light, a sense "
            "of a launch moment and momentum, glints and highlights catching edges, "
            "palette of bright cream, warm coral, and deep ink, optimistic and "
            "attention-catching mood."
        ),
    },
    "christmas": {
        "label": "Christmas",
        "hint": "Warm evening, string lights",
        "text": (
            "A warm, nostalgic Christmas evening scene, delicate string lights "
            "glowing softly, hints of evergreen and cinnamon, palette of deep "
            "emerald, warm gold, and creamy white, intimate and celebratory mood."
        ),
    },
    "halloween": {
        "label": "Halloween",
        "hint": "Dusk, candlelight, playful shadow",
        "text": (
            "A dusky, playfully eerie Halloween evening scene, low candlelight and "
            "long soft shadows, hints of dry leaves and spiced smoke, palette of "
            "burnt orange, charcoal, and pale bone, mischievous and atmospheric mood."
        ),
    },
    "spring": {
        "label": "Spring",
        "hint": "Fresh morning, soft blossom",
        "text": (
            "A fresh, airy spring morning scene, soft blossom and new green growth, "
            "hints of cool dew and light florals, palette of pale green, blush pink, "
            "and clear white, light-hearted and hopeful mood."
        ),
    },
}

# Order the picker shows them in.
SEASON_ORDER: tuple[str, ...] = (
    "autumn",
    "sales",
    "promotion",
    "christmas",
    "halloween",
    "spring",
)

# --------------------------------------------------------------------------- #
# Layer 2 — setting & visual DNA (the brand anchor; never varies)
# --------------------------------------------------------------------------- #

WORLD_PRESETS: dict[str, dict[str, str]] = {
    "coastal_terrace": {
        "label": "Coastal terrace",
        "hint": "Mediterranean stone, sea horizon",
        "text": (
            "Set on a sun-bleached Mediterranean stone terrace overlooking a calm "
            "sea, featuring rustic whitewashed walls with cascading ivy, a weathered "
            "oak table with visible grain, a cluster of pillar candles and scattered "
            "natural props, and a distant horizon where the sea meets an open sky. "
            "The lighting is warm, diffused golden light creating gentle shadows and "
            "glowing highlights on surfaces. The color palette is earthy and marine: "
            "warm stone, cream, muted terracotta, and soft sea blue. The atmosphere "
            "feels serene and elegant."
        ),
    },
    "forest_cabin": {
        "label": "Forest cabin",
        "hint": "Timber, firelight, dried botanicals",
        "text": (
            "Set inside a rustic timber cabin with exposed beams, featuring a "
            "rough-hewn wooden table, a stone fireplace, dried botanicals hanging "
            "from the rafters, and a window framing dense forest. The lighting is "
            "warm firelight mixed with cool window light, creating deep soft shadows "
            "and warm rim highlights. The color palette is deep brown, moss green, "
            "and amber. The atmosphere feels cozy and grounded."
        ),
    },
    "urban_loft": {
        "label": "Urban loft",
        "hint": "Concrete, steel, city window light",
        "text": (
            "Set in a minimalist industrial loft with polished concrete floors, "
            "featuring a raw steel table, a single large monstera plant, exposed "
            "brick walls, and floor-to-ceiling windows overlooking a city skyline. "
            "The lighting is cool directional daylight creating sharp defined shadows "
            "and clean specular highlights. The color palette is grey, white, and "
            "green. The atmosphere feels modern and clean."
        ),
    },
}

WORLD_ORDER: tuple[str, ...] = ("coastal_terrace", "forest_cabin", "urban_loft")

# --------------------------------------------------------------------------- #
# Layer 3 — subject hero (the only free text, wrapped in fixed framing)
# --------------------------------------------------------------------------- #

SUBJECT_PREFIX = "At the center of the frame, "
SUBJECT_SUFFIX = (
    ", positioned as the clear hero of the composition, captured in sharp focus "
    "with shallow depth of field, the scene light wrapping the subject and "
    "catching a single warm highlight on its edge."
)

# --------------------------------------------------------------------------- #
# Universal quality tail — identical everywhere except the framing note
# --------------------------------------------------------------------------- #

QUALITY_TAIL_HEAD = "Hyper-detailed, 8k resolution, cinematic composition"
QUALITY_TAIL_FOOT = (
    "razor-sharp focus on the subject with soft bokeh background, harmonious "
    "color grading consistent with the stated palette."
)

ASPECT_NOTES: dict[str, str] = {
    "square": "square 1:1 framing",
    "landscape": "16:9 landscape framing",
    "portrait": "4:5 portrait framing",
}


def aspect_for_size(width: int, height: int) -> str:
    if width > height:
        return "landscape"
    if height > width:
        return "portrait"
    return "square"


def quality_tail(width: int, height: int) -> str:
    aspect = aspect_for_size(width, height)
    return f"{QUALITY_TAIL_HEAD}, {ASPECT_NOTES[aspect]}, {QUALITY_TAIL_FOOT}"


# --------------------------------------------------------------------------- #
# Composition
# --------------------------------------------------------------------------- #


def _clean_subject(subject: Any) -> str:
    if not isinstance(subject, str):
        raise ValueError("subject must be text")
    collapsed = " ".join(subject.split())
    if not collapsed:
        raise ValueError("subject is required")
    if len(collapsed) > SUBJECT_MAX_CHARS:
        raise ValueError(f"subject must be {SUBJECT_MAX_CHARS} characters or fewer")
    return collapsed.rstrip(".")


def world_text(world: str) -> str:
    """Layer 2, byte-for-byte identical for every run of this world."""
    if world not in WORLD_PRESETS:
        raise ValueError(f"unknown world: {world!r}")
    return WORLD_PRESETS[world]["text"]


def season_text(season: str) -> str:
    if season not in SEASON_PRESETS:
        raise ValueError(f"unknown season: {season!r}")
    return SEASON_PRESETS[season]["text"]


def compose(season: str, world: str, subject: str, width: int, height: int) -> str:
    """The complete prompt. Assembled from server constants plus one subject line."""
    layers = [
        season_text(season),
        world_text(world),
        SUBJECT_PREFIX + _clean_subject(subject) + SUBJECT_SUFFIX,
        quality_tail(width, height),
    ]
    prompt = "\n\n".join(layers)
    if len(prompt) > COMPOSED_PROMPT_MAX_CHARS:
        raise ValueError("composed prompt is too long; shorten the subject")
    return prompt


def fingerprint(season: str, world: str, width: int, height: int) -> dict[str, Any]:
    """Recorded in provenance so a picture traces back to exact layer wording."""
    world_block = world_text(world)
    return {
        "season": season,
        "world": world,
        "aspect": aspect_for_size(width, height),
        "world_sha256": hashlib.sha256(world_block.encode()).hexdigest(),
        "season_sha256": hashlib.sha256(season_text(season).encode()).hexdigest(),
        "quality_tail_sha256": hashlib.sha256(quality_tail(width, height).encode()).hexdigest(),
        "layer_table_version": LAYER_TABLE_VERSION,
    }


def public_catalog() -> dict[str, Any]:
    """Safe for the UI: keys, labels and hints only — never the layer wording."""
    return {
        "seasons": [
            {
                "key": key,
                "label": SEASON_PRESETS[key]["label"],
                "hint": SEASON_PRESETS[key]["hint"],
            }
            for key in SEASON_ORDER
            if key in SEASON_PRESETS
        ],
        "worlds": [
            {
                "key": key,
                "label": WORLD_PRESETS[key]["label"],
                "hint": WORLD_PRESETS[key]["hint"],
            }
            for key in WORLD_ORDER
            if key in WORLD_PRESETS
        ],
        "subject_max_chars": SUBJECT_MAX_CHARS,
        "layer_table_version": LAYER_TABLE_VERSION,
    }
