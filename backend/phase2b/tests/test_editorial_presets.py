"""Editorial preset tests — pure, offline, no API or provider calls.

Run:  python backend/phase2b/tests/test_editorial_presets.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import editorial_presets as ep  # noqa: E402

failures: list[str] = []


def check(name: str, condition: bool) -> None:
    if condition:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name}")
        failures.append(name)


# Look wording is byte-identical across people options, zones and shapes.
for look in ep.LOOK_ORDER:
    block = ep.EDITORIAL_LOOKS[look]["instruction"]
    same = all(
        block in ep.compose_instruction(look, people, zone, shape)
        for people in ep.PEOPLE_ORDER
        for shape in ep.OUTPUT_PRESETS
        for zone in ep.SHAPE_ZONES[shape]
    )
    check(f"look wording identical for {look}", same)

# Every shape's default zone is valid for that shape.
for shape, zone in ep.DEFAULT_ZONE.items():
    check(f"default zone valid for {shape}", zone in ep.SHAPE_ZONES[shape])

# Enum-only: unknown keys are refused, never silently defaulted.
def _rejects(fn, *args) -> bool:
    try:
        fn(*args)
        return False
    except ValueError:
        return True


check(
    "rejects unknown look",
    _rejects(ep.compose_instruction, "nope", None, "left_third", "1600x900"),
)
check(
    "rejects unknown people option",
    _rejects(ep.compose_instruction, "cover_shot", "crowd", "left_third", "1600x900"),
)
check(
    "rejects unknown zone",
    _rejects(ep.compose_instruction, "cover_shot", None, "middle", "1600x900"),
)
check(
    "rejects unknown shape",
    _rejects(ep.compose_instruction, "cover_shot", None, "left_third", "999x999"),
)

# Zone must fit the shape (right_third is not offered on square/tall).
try:
    ep.compose_instruction("cover_shot", None, "right_third", "1080x1080")
    check("rejects zone not available for shape", False)
except ValueError:
    check("rejects zone not available for shape", True)

# Zone geometry: fractional rect maps to the expected pixel region.
x0, y0, x1, y1 = ep.zone_rect("left_third", 1600, 900)
check("left_third rect", (x0, y0, x1, y1) == (0, 0, 544, 900))
x0, y0, x1, y1 = ep.zone_rect("upper_third", 1080, 1920)
check("upper_third rect", (x0, y0, x1, y1) == (0, 0, 1080, 653))

# Zone rects stay inside the canvas for every shape/zone pair.
inside = True
for shape, (w, h) in ep.OUTPUT_PRESETS.items():
    for zone in ep.SHAPE_ZONES[shape]:
        a, b, c, d = ep.zone_rect(zone, w, h)
        if not (0 <= a < c <= w and 0 <= b < d <= h):
            inside = False
check("all zone rects inside canvas", inside)

# No negation phrasing leaks into instructions (WP1b lesson).
NEGATIONS = (" no ", " not ", " never ", " without ", "don't", "do not")
clean = True
for text in (
    [v["instruction"] for v in ep.EDITORIAL_LOOKS.values()]
    + [v["instruction"] for v in ep.PEOPLE_OPTIONS.values()]
    + [v["instruction"] for v in ep.COPY_ZONES.values()]
):
    low = f" {text.lower()} "
    if any(n in low for n in NEGATIONS):
        clean = False
check("instructions are negation-free", clean)

# Fingerprints are deterministic and change with any input.
f1 = ep.fingerprint("cover_shot", None, "left_third", "1600x900")
f2 = ep.fingerprint("cover_shot", None, "left_third", "1600x900")
f3 = ep.fingerprint("cover_shot", "foreground_model", "left_third", "1600x900")
check("fingerprint deterministic", f1 == f2)
check("fingerprint changes with people", f1["instruction_sha256"] != f3["instruction_sha256"])
check("fingerprint carries version", f1["preset_table_version"] == ep.PRESET_TABLE_VERSION)

# Public catalog never exposes wording.
catalog = ep.public_catalog()
blob = repr(catalog).lower()
check("catalog has no instruction wording", "instruction" not in blob and "photographed subject" not in blob)
check("catalog lists looks/people/presets", bool(catalog["looks"]) and bool(catalog["people"]) and bool(catalog["output_presets"]))

# Aspect ratios are declared for every preset.
check("aspect for every preset", all(ep.aspect_ratio(k) for k in ep.OUTPUT_PRESETS))

# Default people option is the safe one.
check("default people is none", ep.DEFAULT_PEOPLE == "none")

# Composed instruction stays within the length ceiling for every combination.
fits = all(
    len(ep.compose_instruction(look, people, zone, shape)) <= ep.COMPOSED_INSTRUCTION_MAX_CHARS
    for look in ep.LOOK_ORDER
    for people in ep.PEOPLE_ORDER
    for shape in ep.OUTPUT_PRESETS
    for zone in ep.SHAPE_ZONES[shape]
)
check("all compositions within length ceiling", fits)

print()
if failures:
    print(f"{len(failures)} FAILED")
    sys.exit(1)
print("ALL TESTS PASSED")
