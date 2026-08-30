# Verify uploaded api.py against the WP0 README-integration edits

## Verdict: partially applied — 1 of 4 api.py edits present, 3 missing

The uploaded `api.py` (535 lines) was checked line-by-line against `backend/phase2b/README-integration.md`.

## Present

- **§1 Image packaging (done):** `advanced.py` is in the image via `.add_local_file("advanced.py", "/root/advanced.py", copy=True)` (line 89), and `pillow==11.0.0` is pinned. All Phase 2A files (`assets.py`, `usage.py`) are still there.

## Missing (must be added before deploy)

1. **`import advanced`** — not imported anywhere; the module is packaged but never loaded.

2. **§2 `POST /v1/generations` extension** — the handler has none of the WP0 logic:
   - No parsing of `source_asset_id`, `output_preset`, `params` from the request body.
   - No `if registry_row.get("requires_source_asset"): advanced.resolve_advanced_request(...)` gate.
   - No 400 rejection when `source_asset_id` is sent to a non-asset workflow (Flux).
   - Job insert does not persist `source_asset_id`, `output_preset`, `request_params`.

3. **§3 `GET /v1/generations/{job_id}` extension** — `JobResponse` (lines 172–191) has no `source_asset_id` / `output_asset_id` / `output_preset` / `request_params` fields. (`jobs.py` also needs to echo these — separate file, not verifiable from this upload.)

4. **§6 health marker** — `/health` returns `"assets": True` and `"assets_bucket"` but not `"advanced_framework": True`.

## Not verifiable from this file (out of scope of the upload)

- §4 Studio-safe filter — lives in `registry.py` (`advanced.studio_safe_row` filter).
- §5 Flags — Modal env vars `ADVANCED_WORKFLOWS_ENABLED=false`, `OUTPAINT_EVAL_ENABLED=false`, `PRODUCT_SCENE_EVAL_ENABLED=false`, `PROVIDER_BFL_ENABLED=false`, `PROVIDER_REPLICATE_ENABLED=false` on the V6 app.
- `jobs.py` lineage echo in `job_to_response_dict`.

## Cosmetic note (safe, no fix required)

- Lines 81 and 321–322 use tab indentation inside implicit continuation (brackets/braces), which Python tolerates. No TabError risk as written, but worth normalizing to spaces.

## Fix plan

I will deliver a corrected full `api.py` that is byte-identical to the upload except for:

1. Add `import advanced` next to the other sibling imports (line ~62).
2. Add the §2 gate at the top of `start_generation`, after registry resolution (`row`) and before idempotency/dispatch:
   - `requires_source_asset=true` → `advanced.resolve_advanced_request(workflow_key, workflow_version, source_asset_id, output_preset, params or {}, user_id, environment="staging")`; WP0 always stops here with a gate failure since no reachable candidate exists.
   - else if `source_asset_id` present → 400 `invalid_request` ("This workflow does not accept a source asset.").
3. Persist `source_asset_id`, `output_preset`, `request_params` (validated dict, never raw body) in the job-insert payload.
4. Extend `JobResponse` with the four lineage fields.
5. Add `"advanced_framework": True` to the `/health` payload.
6. Normalize the tab-indented lines to spaces.

No other logic, routes, CORS, auth, adapter, or Flux behavior changes. The Flux text-to-image path stays byte-equivalent.

## Rollback

Purely additive to the request/response surface; with `ADVANCED_WORKFLOWS_ENABLED=false` the new code path is unreachable (all advanced requests fail the flag gate with 403). Rollback = redeploy the previous api.py revision.
