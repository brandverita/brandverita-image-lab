# Deploy V6 side-by-side with the working V5 (no V5 downtime)

Goal: V6 becomes a second, independently named Modal deployment. V5 stays exactly as deployed and keeps serving the Image Lab until V6 is verified.

## Local structure check

Your `modal-project/` layout is correct for this. Two notes:

- `phase1-v6-staging/` is a flat package dir with `adapters/` inside — that matches how `api.py` imports (`import registry`, `import supabase_rest`, `from adapters import ...`). Deploy from inside that folder so the sibling modules resolve.
- `venv/` and `__pycache__/` should not sit where they get scanned as part of a deployment — keeping them as siblings (as you have) is fine. Delete the stale `__pycache__/` before deploying to avoid stale bytecode from the v5 files.
- Filenames confirmed correct (`supabase_rest.py`, not a misspelling), and `adapters/__init__.py` is present.

## Naming split

| Component | V5 (untouched) | V6 (new) |
|---|---|---|
| API app | `brandverita-api` | `brandverita-api-v6` |
| Worker app | `comfyui-generation-worker` | `comfyui-generation-worker-v6` |
| Worker class | `ComfyUIWorker` | `ComfyUIWorker` (unchanged) |

Secrets (`brandverita-supabase-comfy-ui`, `huggingface-secret`) are shared by name — no change needed, no duplication.

Each Modal app gets its own URL, so V6 will be served at a new `*-v6-fastapi-app.modal.run` endpoint while the V5 URL keeps working.

## Files to amend (3)

1. `phase1-v6-staging/api.py`
   - `app = modal.App("brandverita-api-v6")`
   - `/health` gains `app_name: "brandverita-api-v6"` alongside the existing `version: "v6"`, `worker_app`, `worker_class`, so you can confirm at a glance which deployment answered.

2. `phase1-v6-staging/modal_worker_v2.py`
   - `app = modal.App("comfyui-generation-worker-v6")`
   - No changes to pins, image build, GPU, or `ComfyUIWorker` behaviour. The image layers are content-addressed, so the pinned ComfyUI checkout and model downloads are reused from cache rather than re-downloaded.

3. `phase1-v6-staging/adapters/modal_comfyui.py`
   - `WORKER_APP = os.environ.get("WORKER_APP_NAME", "comfyui-generation-worker-v6")`
   - Env override so a V6 API can be pointed back at the V5 worker for an A/B check without editing code. Graph construction stays byte-identical (regression evidence from Phase 1 remains valid).

Nothing in `jobs.py`, `registry.py`, `jwks_auth.py`, `supabase_rest.py`, `adapters/base.py`, `bfl_api.py`, `replicate.py` changes.

Frontend: no change in this step. `VITE_GENERATION_API_URL` keeps pointing at V5 until you have verified V6, then it is switched in Netlify as a separate, instantly reversible step.

Note: both V5 and V6 write to the same staging `generation_jobs` table and `generation-outputs` bucket. That is intended for staging; V6 rows are distinguishable by `provider`, `workflow_version`, and `worker_version`.

## Deployment order (first instruction)

Worker first, then API — the API's dispatch looks the worker up by name.

```bash
cd modal-project/phase1-v6-staging
rm -rf ../__pycache__ __pycache__
modal deploy modal_worker_v2.py
```

Then send me the build log tail — specifically the `git rev-parse HEAD` assertion line and the `MANIFEST_RECORD` sha256 lines for `flux1-schnell.safetensors` and `ae.safetensors` (still unpinned placeholders, to be recorded from this build). After that we deploy `api.py` and verify `/health`.

## Verification once both are deployed

1. `curl https://brandverita--brandverita-api-v6-fastapi-app.modal.run/health` → `version: v6`, `app_name: brandverita-api-v6`, `worker_app: comfyui-generation-worker-v6`.
2. `curl https://brandverita--brandverita-api-fastapi-app.modal.run/health` → still `v5`, proving V5 is intact.
3. One end-to-end generation against the V6 URL; confirm the new job row carries `provider`, `workflow_version`, `workflow_config_hash`, `worker_version`.
4. Contract checks: unknown workflow → 400, `outpaint:v1` → 403, stub providers → 403, unauthenticated `GET /v1/workflows` → empty/401.

## Rollback

No V5 change to undo. If V6 misbehaves: leave (or point back) `VITE_GENERATION_API_URL` at the V5 URL; optionally `modal app stop brandverita-api-v6` and `modal app stop comfyui-generation-worker-v6`.
