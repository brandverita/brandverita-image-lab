"""Editorial typography tests — pure, offline, no API or provider calls.

Run:  python backend/phase2b/tests/test_editorial_typography.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image  # noqa: E402

import editorial_typography as et  # noqa: E402
import editorial_presets as ep  # noqa: E402

failures: list[str] = []


def check(name: str, condition: bool) -> None:
    if condition:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name}")
        failures.append(name)


def flat(w, h, rgb):
    return Image.new("RGB", (w, h), rgb)


def noisy(w, h):
    import random

    random.seed(7)
    img = Image.new("RGB", (w, h))
    img.putdata([(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)) for _ in range(w * h)])
    return img


ZONE = ep.zone_rect("left_third", 1600, 900)

# Fonts load for every preset.
for key in et.TYPE_PRESETS:
    check(f"font loads for {key}", et.load_font(key, 40) is not None)

# Basic typeset returns a same-size image and metadata.
img = flat(1600, 900, (40, 42, 48))
out, meta = et.typeset(img, ZONE, headline="The autumn edit", type_preset="display_sans")
check("typeset keeps canvas size", out.size == (1600, 900))
check("metadata records copy", meta["headline"] == "The autumn edit")
check("typeset actually drew pixels", list(out.getdata()) != list(img.getdata()))

# Dark zone -> light ink; light zone -> dark ink.
_, meta_dark = et.typeset(flat(1600, 900, (30, 30, 34)), ZONE, headline="Hello there")
_, meta_light = et.typeset(flat(1600, 900, (235, 232, 226)), ZONE, headline="Hello there")
check("dark zone uses light ink", meta_dark["ink"] == "light")
check("light zone uses dark ink", meta_light["ink"] == "dark")

# Mid-tone zone -> scrim kicks in to reach the contrast floor.
_, meta_mid = et.typeset(flat(1600, 900, (128, 128, 128)), ZONE, headline="Hello there")
check("scrim applied on mid-tone zone", meta_mid["scrim"] is True)
check("scrim reaches contrast floor", meta_mid["contrast_ratio"] >= et.MIN_CONTRAST)

# Long headline wraps and shrinks to fit the zone.
_, meta_long = et.typeset(
    flat(1600, 900, (40, 42, 48)),
    ZONE,
    headline="A considerably longer seasonal headline that must wrap across several lines to fit",
)
check("long headline wraps", meta_long["headline_lines"] > 1)
check("long headline shrinks", meta_long["headline_font_size_px"] < 200)

# Determinism: same inputs, same layout.
_, m1 = et.typeset(flat(1600, 900, (40, 42, 48)), ZONE, headline="Repeatable")
_, m2 = et.typeset(flat(1600, 900, (40, 42, 48)), ZONE, headline="Repeatable")
check("typesetting is deterministic", m1 == m2)

# Copy validation.
def _rejects(fn, **kw) -> bool:
    try:
        fn(**kw)
        return False
    except ValueError:
        return True


check("rejects missing headline", _rejects(et.validate_copy, headline=""))
check("rejects over-long headline", _rejects(et.validate_copy, headline="x" * 91))
check("rejects over-long standfirst", _rejects(et.validate_copy, headline="ok", standfirst="x" * 201))
check("collapses whitespace", et.validate_copy(headline="  a   b \n c ")["headline"] == "a b c")

# Unknown type preset is refused.
try:
    et.typeset(img, ZONE, headline="Hi", type_preset="nope")
    check("rejects unknown type preset", False)
except ValueError:
    check("rejects unknown type preset", True)

# Full layered call with all copy fields.
out_full, meta_full = et.typeset(
    noisy(1600, 900),
    ZONE,
    headline="Cover lines",
    standfirst="A short standfirst that sits under the headline.",
    label="Issue 12",
    type_preset="editorial_serif",
)
check("layered call works on busy picture", out_full.size == (1600, 900) and meta_full["label"] == "Issue 12")

# Zone usability: flat is calm, noise is busy.
check("flat zone is usable", et.zone_usability(flat(1600, 900, (200, 200, 200)), ZONE)["usable"])
check("noisy zone is busy", not et.zone_usability(noisy(1600, 900), ZONE)["usable"])

# Public catalog exposes no font internals beyond labels.
catalog = et.public_type_catalog()
check("type catalog lists presets", len(catalog["type_presets"]) == len(et.TYPE_PRESETS))
check("catalog exposes limits", catalog["headline_max_chars"] == 90)

# Works on the tall banner shape too.
tall_zone = ep.zone_rect("upper_third", 800, 2000)
out_tall, meta_tall = et.typeset(flat(800, 2000, (36, 38, 44)), tall_zone, headline="Tall story")
check("tall banner typeset", out_tall.size == (800, 2000) and meta_tall["ink"] == "light")

print()
if failures:
    print(f"{len(failures)} FAILED")
    sys.exit(1)
print("ALL TESTS PASSED")
