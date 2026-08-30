# WP0 registry.py refactor — verified against your uploaded file

On approval I deliver a full refactored `backend/phase2b/registry.py` (drop-in for `modal-project/phase1-v6-staging/registry.py`), byte-identical to your upload except for the changes below.

## Correction to my previous plan

**Edit (a) "expose new columns" is NOT needed.** Your `load_registry()` fetches `select: *` and returns raw row dicts — `requires_source_asset`, `allowed_output_presets`, `input_envelope`, `artifact_pins`, `candidate_id`, `candidate_notes` already flow through automatically. No serialization mapping exists to update.

**Studio filtering already exists inline** in `list_visible_workflows` (lines 184–207), but it does not use the shared `advanced.studio_safe_row` predicate that README §4 mandates — so the refactor consolidates it.

## The one required change: route Studio reads through `advanced.studio_safe_row` (README §4)

1. Add `import advanced` to the imports.
2. In `list_visible_workflows`, replace the inline studio branch (lines 197–205) with the shared predicate, keeping the existing `status == "active"` requirement (which `studio_safe_row` intentionally does not include — it is a commercial/visibility predicate, not a lifecycle one):

```python
        if origin == "studio":
            if row.get("status") != "active" or not advanced.studio_safe_row(row):
                continue
```

Semantics check — identical-or-stricter than the current inline logic:
- `registry_visibility == "studio_safe"` ✓ (was `visibility != "studio_safe": continue`)
- `commercial_status != "research_only"` plus `commercial_status in COMMERCIAL_APPROVED` stays enforced downstream at dispatch; the view filter keeps the current effective behavior since no `studio_safe` row can be `research_only` per registry rules ✓
- `production_enabled` and `enabled_for_studio` must be true ✓ (current inline code only checks `enabled_for_studio`; adding `production_enabled` is stricter and matches §4)

3. Update the `list_visible_workflows` docstring to state that Studio filtering is delegated to `advanced.studio_safe_row` + active-status check.

## What deliberately does NOT change

- `resolve_workflow` / `get_workflow` / `assert_dispatch_allowed` stay unfiltered — server-internal dispatch must keep resolving advanced candidates so the flag/allow-list gates reject them with the correct error.
- `SAFE_FIELDS`, `safe_workflow_view`, `compute_config_hash`, `validate_inputs`, cache logic, aliases — untouched.
- `assert_dispatch_allowed` already blocks `status != "active"`; WP0 candidates are seeded `status = testing`, so even a hypothetical registry-visible candidate cannot dispatch.

## Then, per the previous plan (unchanged)

- `jobs.py`: add the four lineage fields to `job_to_response_dict`.
- Env flags: add the `.env({...false...})` block to the image in api.py (or set app env in dashboard); behaviorally confirmed by the suite's 403 `advanced_workflows_disabled` checks.
- Import check → `modal deploy api.py` (V6 only) → `/health` shows `advanced_framework: true` → run `test_wp0_framework.py` (28 checks) → I write the WP0 build manifest.
