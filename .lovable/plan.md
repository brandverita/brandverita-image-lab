# WP0 acceptance: resolve the 3 remaining failures (25/28 → 28/28)

All three failures are assertion/ordering issues, not safety holes. Every advanced request is still refused, nothing dispatchable leaked, and Flux is unchanged.

## Failure 3 — right refusal, wrong error code

`api.py` calls `registry.assert_dispatch_allowed(row, origin="lab")` (line 382) before the advanced gate (line 391). The outpaint row is `status = draft`, so the generic lifecycle check fires first and returns `403 workflow_unavailable: workflow 'outpaint:v1' is not active`, never reaching `advanced.resolve_advanced_request`, which is what emits `workflow_not_available`.

Fix (api.py only): move the advanced branch above the dispatch assertion for asset workflows.

```text
resolve_workflow(...)
if row.requires_source_asset:      # advanced gate first -> workflow_not_available
    advanced.resolve_advanced_request(...)
else:
    assert_dispatch_allowed(row, origin="lab")
    reject stray source_asset_id
```

`resolve_advanced_request` already enforces a stricter superset for advanced rows (flags, module flag, research_only, staging env, internal visibility, `status in (draft, testing)`), so no gate is lost. The Flux path keeps `assert_dispatch_allowed` exactly as today.

## Failures 17 and 18 — the test asserts against a Lab-origin read

`GET /v1/workflows` calls `list_visible_workflows(origin="lab")`. By design an allow-listed Lab user sees internal rows, so the outpaint research row appearing there is correct behavior — the test wrongly assumed either no list endpoint or a Studio-shaped one. Check 18 also fails because the safe view has no `registry_visibility` field (`SAFE_FIELDS` deliberately omits it).

Fix in two parts:

1. `api.py`: accept an optional `?origin=studio|lab` query param on `GET /v1/workflows` (default `lab`, anything else than `studio` treated as `lab`) and pass it through to `list_visible_workflows`. No filtering logic changes; `registry.py` and `advanced.studio_safe_row` stay as delivered.
2. `backend/phase2b/tests/test_wp0_framework.py`: rewrite checks 17–18 to assert the security property that actually matters:
   - 17: `GET /v1/workflows?origin=studio` returns zero rows with `commercial_status == "research_only"` and zero rows whose key is a known advanced candidate.
   - 18: the same Studio read returns only rows with `enabled_for_studio` and `production_enabled` true and `status == "active"` (fields already present in `SAFE_FIELDS`), and the Lab read is additionally asserted to expose the research row *only* as non-dispatchable (Lab visibility is intentional and documented).

Optional registry hygiene (separate, needs your go-ahead): the approved decision set `status = testing` for candidates, but the seeded outpaint row is `status = draft`. Both are accepted by the advanced gate, so this changes nothing functionally; I can leave it or align it in a tiny migration.

## Deliverables

- Updated `backend/phase2b/api.py` (gate reorder + `origin` query param) — you copy into `modal-project/phase1-v6-staging/` and `modal deploy api.py`.
- Updated `backend/phase2b/tests/test_wp0_framework.py` (checks 17–18 rewritten).
- Then re-run the suite; expected 28/28. I write `backend/phase2b/wp0-build-manifest.md` on your confirmation.

## Rollback

Both edits are confined to `api.py` request routing and the test file. Reverting to the previous `api.py` revision restores current behavior; flags stay `false`, so no advanced path is reachable either way.
