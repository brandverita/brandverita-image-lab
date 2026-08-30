# WP0 close-out: write the build manifest

28/28 passed. WP0 (shared Image Transformation Framework v1) is functionally complete in staging. The only remaining step is recording the build so WP1/WP2 have a fixed baseline to roll back to.

## What I will do

Create `backend/phase2b/wp0-build-manifest.md` containing:

- **Deployed surface** — Modal app `brandverita-api-v6`, `/health` payload as returned (`advanced_framework: true`, `assets: true`, worker `comfyui-generation-worker-v6`), worker untouched by WP0.
- **Code inventory** — `advanced.py` (new), and the refactored `api.py`, `registry.py`, `jobs.py` edits, each with the specific WP0 change it carries.
- **Flag state** — all five `*_ENABLED` flags false (`ADVANCED_WORKFLOWS_ENABLED`, `OUTPAINT_EVAL_ENABLED`, `PRODUCT_SCENE_EVAL_ENABLED`, plus the two module dispatch flags), which is why every advanced request ends at a 403 gate.
- **Migrations applied** — registry columns + immutability trigger replacement, `generation_jobs` lineage columns, `transformation_eval_runs` table with grants/RLS, and the `outpaint:v1` data update (`requires_source_asset = true`, `status = testing`, five absolute presets, input envelope).
- **Registry state snapshot** — the three rows and their status/commercial_status/visibility values.
- **Acceptance record** — 28/28 with the check list, plus which checks are deferred/manual (10, 11, 21, 22, 23, 25, 28) and what defers them to WP1.
- **Rollback** — drop the new columns/table, restore the prior immutability function body, revert the `outpaint:v1` row to `draft` / `requires_source_asset = false`, redeploy the previous V6 revision.
- **Explicitly out of scope in WP0** — no Modal research worker, no BFL adapter or secret, no Image Lab UI panel, no dispatch, no production deployment.

No code, service, registry, or deployment changes — this step is documentation only.

## After the manifest

WP1 (Modal research worker + outpaint graph) and WP2 (BFL review → adapter + secret) each still need your separate approval before any implementation.
