# V6 side-by-side rollout — worker deployed, API next

V5 (`brandverita-api`, `comfyui-generation-worker`) stays untouched and keeps serving the Image Lab. V6 lives as `brandverita-api-v6` + `comfyui-generation-worker-v6`.

## Done
- V6 worker deployed: `comfyui-generation-worker-v6` (image `im-oweHTBQbMa88vvzYbmCXPP`, torch 2.5.1/cu121, all Flux models downloaded and verified, 605s build).
- The build log tail shows the model download step succeeded, but the excerpt did not include the `git rev-parse HEAD` assertion line or the `MANIFEST_RECORD` sha256 lines for `flux1-schnell.safetensors` and `ae.safetensors`. These are still needed to complete the build manifest (the sha256 placeholders recorded in Phase 1 must be filled from this build).

## Next: deploy the V6 API

```bash
cd modal-project/phase1-v6-staging
modal deploy api.py
```

The API resolves the worker by name (`comfyui-generation-worker-v6`, overridable via `WORKER_APP_NAME`), so the worker had to exist first — it now does.

## Verification after API deploy
1. `curl https://brandverita--brandverita-api-v6-fastapi-app.modal.run/health`
   → expect `version: v6`, `app_name: brandverita-api-v6`, `worker_app: comfyui-generation-worker-v6`.
2. `curl https://brandverita--brandverita-api-fastapi-app.modal.run/health`
   → still `v5`, proving V5 intact.
3. Record the missing manifest data from the worker build log:
   - `git rev-parse HEAD` output (must equal `344b43989e8c56b5bb4a66cf028c834192ab59dd`)
   - `MANIFEST_RECORD` sha256 for `flux1-schnell.safetensors` and `ae.safetensors`
   (If the lines scrolled past, re-run the build log via `modal app logs comfyui-generation-worker-v6` or rebuild logs.)
4. One end-to-end generation against the V6 URL (temporarily, e.g. via curl with a staging token, or by pointing a local Lab build at it) → confirm the new job row carries `provider`, `workflow_version`, `workflow_config_hash`, `worker_version`.
5. Contract checks against V6 URL: unknown workflow → 400, `outpaint:v1` → 403, stub providers (replicate/bfl) → 403, unauthenticated `GET /v1/workflows` → empty/401.

## Frontend cutover (separate, reversible step — after verification)
- Switch `VITE_GENERATION_API_URL` in Netlify to the V6 URL, trigger a fresh build, run one generation from the Image Lab, confirm the developer panel shows `provider` / `workflow_version` / `workflow_config_hash` / `worker_version`.
- Reverting the env var instantly restores V5.

## Rollback
No V5 change to undo. If V6 misbehaves: leave `VITE_GENERATION_API_URL` at the V5 URL; optionally `modal app stop brandverita-api-v6` and `modal app stop comfyui-generation-worker-v6`.
