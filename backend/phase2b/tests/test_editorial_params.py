"""Module C framework-integration tests — strict param parsing and module
routing, offline (registry lookups stubbed; no API, provider or database).

Run:  python backend/phase2b/tests/test_editorial_params.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# `assets` is deployment-only (not committed to this repo); stub the pieces
# advanced.py touches at import/parse time.
import types  # noqa: E402

_assets_stub = types.ModuleType("assets")
_assets_stub.BUCKET = "generation-assets"
_assets_stub.ValidationResult = dict
sys.modules["assets"] = _assets_stub

import advanced  # noqa: E402
import editorial_presets as ep  # noqa: E402

failures: list[str] = []


def check(name: str, condition: bool) -> None:
    if condition:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name}")
        failures.append(name)


ROW = {"input_schema": {}}


def parse(params, preset="1600x900", row=None):
    return advanced.parse_params("editorial_layout", params, row or ROW, preset)


def rejects(name, params, preset="1600x900", row=None):
    try:
        parse(params, preset, row)
        check(name, False)
    except Exception as exc:  # HTTPException via advanced_error
        detail = str(getattr(exc, "detail", exc))
        check(name, "invalid_request" in detail or "workflow_not_available" in detail)


# Happy path: enums + copy validate, defaults fill in.
ok = parse({"look": "cover_shot", "headline": "The autumn edit"})
check("valid request parses", ok["look"] == "cover_shot")
check("people defaults to none", ok["people"] == "none")
check("copy zone defaults per shape", ok["copy_zone"] == ep.DEFAULT_ZONE["1600x900"])
check("type preset defaults", ok["type_preset"] == "display_sans")
check("copy passes through", ok["headline"] == "The autumn edit")

ok2 = parse(
    {
        "look": "flat_lay",
        "people": "foreground_model",
        "copy_zone": "lower_third",
        "type_preset": "condensed_caps",
        "headline": "Studio notes",
        "standfirst": "A short line under the headline.",
        "label": "Issue 3",
    },
    preset="1080x1080",
)
check("full request parses", ok2["people"] == "foreground_model" and ok2["label"] == "Issue 3")

# Enum discipline.
rejects("rejects unknown look", {"look": "grunge", "headline": "Hi"})
rejects("rejects unknown people option", {"look": "cover_shot", "headline": "Hi", "people": "crowd"})
rejects("rejects unknown type preset", {"look": "cover_shot", "headline": "Hi", "type_preset": "comic"})
rejects("rejects zone wrong for shape", {"look": "cover_shot", "headline": "Hi", "copy_zone": "left_third"}, preset="1080x1080")
rejects("rejects unknown output preset", {"look": "cover_shot", "headline": "Hi"}, preset="999x999")

# Free text is only ever copy — instruction-affecting keys are refused.
rejects("rejects prompt key", {"look": "cover_shot", "headline": "Hi", "prompt": "make it pop"})
rejects("rejects unknown key", {"look": "cover_shot", "headline": "Hi", "mood": "dark"})

# Copy limits enforced at the framework boundary too.
rejects("rejects missing headline", {"look": "cover_shot"})
rejects("rejects over-long headline", {"look": "cover_shot", "headline": "x" * 91})
rejects("rejects over-long standfirst", {"look": "cover_shot", "headline": "Hi", "standfirst": "x" * 201})
rejects("rejects over-long label", {"look": "cover_shot", "headline": "Hi", "label": "x" * 41})

# Registry row narrowing: an enum outside the row's list is refused.
narrow_row = {"input_schema": {"look_enum": ["cover_shot"]}}
ok3 = parse({"look": "cover_shot", "headline": "Hi"}, row=narrow_row)
check("row-allowed look parses", ok3["look"] == "cover_shot")
rejects("row-narrowed look refused", {"look": "flat_lay", "headline": "Hi"}, row=narrow_row)

# Module routing.
check("module flag name wired", advanced.module_flag("editorial_layout") in (True, False))
check("editorial is a score module", "editorial_layout" in advanced.SCORE_MODULES)

print()
if failures:
    print(f"{len(failures)} FAILED")
    sys.exit(1)
print("ALL TESTS PASSED")
