"""Brand-consistency layer tests — pure, offline, no API or provider calls.

Run:  python backend/phase2b/tests/test_prompt_layers.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import prompt_layers as pl  # noqa: E402

failures: list[str] = []


def check(name: str, condition: bool) -> None:
    if condition:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name}")
        failures.append(name)


# Layer 2 is byte-identical across every season, subject and aspect.
for world in pl.WORLD_ORDER:
    block = pl.WORLD_PRESETS[world]["text"]
    same = all(
        block in pl.compose(season, world, subject, w, h)
        for season in pl.SEASON_ORDER
        for subject in ("a candle", "a bottle of olive oil")
        for (w, h) in ((1024, 1024), (1280, 1024), (1024, 1280))
    )
    check(f"layer 2 identical for {world}", same)

# The quality tail depends only on the canvas shape.
check(
    "quality tail identical per aspect",
    len({pl.quality_tail(1024, 1024), pl.quality_tail(768, 768), pl.quality_tail(512, 512)}) == 1
    and pl.quality_tail(1280, 1024) != pl.quality_tail(1024, 1280),
)

# Enum-only: unknown keys are refused, never silently defaulted.
for bad in ({"season": "nope", "world": "urban_loft"}, {"season": "autumn", "world": "nope"}):
    try:
        pl.compose(bad["season"], bad["world"], "a mug", 1024, 1024)
        check(f"rejects unknown {bad}", False)
    except ValueError:
        check(f"rejects unknown {bad}", True)

# Subject limits.
try:
    pl.compose("autumn", "forest_cabin", "", 1024, 1024)
    check("rejects empty subject", False)
except ValueError:
    check("rejects empty subject", True)

try:
    pl.compose("autumn", "forest_cabin", "x" * (pl.SUBJECT_MAX_CHARS + 1), 1024, 1024)
    check("rejects over-long subject", False)
except ValueError:
    check("rejects over-long subject", True)

check(
    "newlines collapsed in subject",
    "\n" not in pl.compose("autumn", "forest_cabin", "a\nmug\n\nset", 1024, 1024).split("\n\n")[2],
)

# Composed prompt stays inside the workflow's prompt limit.
longest = max(
    len(pl.compose(s, w, "x" * pl.SUBJECT_MAX_CHARS, 1280, 1024))
    for s in pl.SEASON_ORDER
    for w in pl.WORLD_ORDER
)
check(f"composed prompt within limit ({longest} chars)", longest <= pl.COMPOSED_PROMPT_MAX_CHARS)

# Same choices compose identically (deterministic wording).
check(
    "composition deterministic",
    pl.compose("sales", "coastal_terrace", "a linen apron", 1024, 1024)
    == pl.compose("sales", "coastal_terrace", "a linen apron", 1024, 1024),
)

# The public catalog never leaks wording.
catalog = pl.public_catalog()
leaks = [
    entry
    for entry in catalog["seasons"] + catalog["worlds"]
    if set(entry.keys()) != {"key", "label", "hint"}
]
check("catalog exposes keys/labels/hints only", not leaks)
check(
    "catalog wording withheld",
    all(
        pl.WORLD_PRESETS[w]["text"] not in str(catalog) for w in pl.WORLD_ORDER
    )
    and all(pl.SEASON_PRESETS[s]["text"] not in str(catalog) for s in pl.SEASON_ORDER),
)

# Fingerprint pins the exact wording used.
fp = pl.fingerprint("autumn", "urban_loft", 1024, 1280)
check(
    "fingerprint carries hashes and version",
    fp["layer_table_version"] == pl.LAYER_TABLE_VERSION
    and len(fp["world_sha256"]) == 64
    and fp["aspect"] == "portrait",
)

total = len(failures)
print(f"\n{'FAILED' if total else 'OK'} — {total} failure(s)")
sys.exit(1 if total else 0)
