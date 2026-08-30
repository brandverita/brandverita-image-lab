# Execute Phase 2B — WP0 (shared Image Transformation Framework v1)

Full specification: `backend/phase2b/wp0-implementation-plan.md` (already approved). This plan is the execution sequence for WP0 only. No candidate dispatch, no Modal research worker, no BFL adapter or secret, no Image Lab panel.

## Order of work

1. **Migration (tool-applied, needs your approval in the migration card)**
   - Registry columns: `requires_source_asset`, `allowed_output_presets`, `input_envelope`, `artifact_pins`, `candidate_id`, `candidate_notes` + partial unique index on `candidate_id`.
   - Replace `enforce_workflow_definitions_immutability()` to also freeze the new fields once `status in ('active','deprecated','disabled')`.
   - Job link columns on `generation_jobs`: `source_asset_id`, `output_asset_id`, `output_preset`, `request_params` + two indexes.
   - New `transformation_eval_runs` table (module, candidate/provider/timing/cost fields, reviewer_scores, legal_status) with GRANT select→authenticated, all→service_role, RLS scoped to `operator_user_id = auth.uid()` + allow-list. No client write policies.
   - Types regenerate automatically after the migration runs.

2. **V6 API code (delivered as files for you to copy into `modal-project/phase1-v6-staging/`)**
   - **new `advanced.py`**: strict allow-list param parser (outpaint `anchor_directional` enums incl. valid direction/anchor pairs; product_scene `scene_direction` enum; rejects prompt/workflow/nodes/image_url/unknown keys), registry + flag gate (`ADVANCED_WORKFLOWS_ENABLED`, `OUTPAINT_EVAL_ENABLED`, `PRODUCT_SCENE_EVAL_ENABLED`, read inside the handler), asset ownership/readiness/expiry checks, byte-based adapter interface, output validation/write helper, eval-run writer.
   - **edits to `registry.py`** (expose new fields, Studio-safe filter), **`jobs.py`** (persist link columns), **`assets.py`** (reuse signed-URL/upload helpers; add output validation), **`api.py`** (include advanced router, `add_local_file("advanced.py", ...)`, `/health` marker `advanced_framework: true`).
   - `POST /v1/generations` extended only for `requires_source_asset=true` rows; `GET /v1/generations/{id}` echoes lineage fields. Flux path untouched.

3. **Test suite — new `backend/phase2b/tests/test_wp0_framework.py`** (28 checks: auth/flags/asset gates/enum rejection/no-dispatch safety/lineage constraints/registry filtering/Flux + V5 regression).

4. **You deploy**: copy the Modal files, `python -c "import api"`, `modal deploy api.py` (brandverita-api-v6 only — worker untouched), verify `/health` shows `"advanced_framework":true`, then run the test script with `V6`, `TOK_A`, `TOK_B`, `SUPABASE_URL`.

5. **Close-out**: I record the build manifest (`backend/phase2b/wp0-build-manifest.md`) once your test output confirms 28/28.

## Technical notes

- Migration is additive; rollback = drop new columns/table + restore prior immutability function body.
- With `ADVANCED_WORKFLOWS_ENABLED=false` the whole framework returns 403 — safe to deploy before any candidate exists.
- No secret is created, no Netlify deploy, no frontend change in WP0.
- WP1 (Modal research worker + outpaint graph) and WP2 (BFL review → adapter + secret) each need your separate approval after WP0 passes.
