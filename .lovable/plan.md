# Phase 1 V6 — verification + Image Lab cutover

## Status so far (confirmed by you, 2026-08-29)

- V6 API healthy: `version: v6`, `app_name: brandverita-api-v6`, `dispatch: true`, `registry_ok: true`, `worker_app: comfyui-generation-worker-v6`, workflows `flux_text_to_image:v1` / `flux_text_to_image:v1-commercial-candidate` / `outpaint:v1`.
- V5 API untouched and healthy: `version: v5`, `worker_app: comfyui-generation-worker`.
- V6 worker `comfyui-generation-worker-v6` deployed with pinned ComfyUI SHA + artifact hashes.
- The module-packaging fix (`.add_local_file` / `.add_local_dir` into `/root`) is live; no fresh `ModuleNotFoundError`.

The deployment work is done. What remains is the verification checklist that gates the frontend cutover, then the cutover itself.

## Frontend compatibility (verified, no code change needed)

`src/lib/generationApi.ts` sends `workflow_id: "flux-schnell-txt2img-v1"`. The V6 `registry.py` carries a legacy alias mapping `"flux-schnell-txt2img-v1" → ("flux_text_to_image", "v1")`, so the existing Image Lab frontend works against V6 unchanged. Cutover is purely an environment-variable change, not a code change.

## Step 1 — contract checks against V6 (run from your terminal, authenticated)

Run these against `https://brandverita--brandverita-api-v6-fastapi-app.modal.run`. The 401/403/400 checks need a valid Supabase access token (the same JWT the Image Lab sends). Export it first, e.g. from a signed-in browser's Supabase session, then:

```bash
V6=https://brandverita--brandverita-api-v6-fastapi-app.modal.run
TOK="<your-supabase-access-token>"

# 1a. Unknown workflow → 400
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$V6/v1/generations" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOK" \
  -d '{"workflow_id":"bogus:v1","prompt":"x","width":1024,"height":1024,"idempotency_key":"11111111-1111-1111-1111-111111111111"}'

# 1b. outpaint:v1 → 403 (research_only, dispatch refused)
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$V6/v1/generations" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOK" \
  -d '{"workflow_id":"outpaint:v1","prompt":"x","width":1024,"height":1024,"idempotency_key":"22222222-2222-2222-2222-222222222222"}'

# 1c. Stub providers (replicate / bfl) → 403
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$V6/v1/generations" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOK" \
  -d '{"workflow_id":"flux-schnell-txt2img-v1","prompt":"x","width":1024,"height":1024,"provider":"replicate","idempotency_key":"33333333-3333-3333-3333-333333333333"}'

# 1d. Unauthenticated GET /v1/workflows → 401 (or empty)
curl -s -o /dev/null -w "%{http_code}\n" "$V6/v1/workflows"
```

Expected: `400`, `403`, `403`, `401` (or empty body). If any of these differs, stop and report — the registry gate is not enforcing as intended and the cutover must not proceed.

## Step 2 — one authenticated end-to-end generation against V6

```bash
curl -s "$V6/v1/generations" -H "Content-Type: application/json" -H "Authorization: Bearer $TOK" \
  -d '{"workflow_id":"flux-schnell-txt2img-v1","prompt":"a clean product shot of a matte ceramic mug on a soft neutral background, studio lighting","width":1024,"height":1024,"idempotency_key":"'"$(uuidgen)"'"}'
```

Take the returned `job_id`, then poll `GET /v1/generations/{job_id}` (every 2s, up to ~12 min — a cold V6 worker has to boot ComfyUI + load Flux weights) until `completed` or `failed`.

Then confirm the new `generation_jobs` row carries the Phase 1 columns by querying the staging Supabase:

```sql
select id, workflow_id, workflow_version, provider, provider_model,
       workflow_config_hash, worker_version, status, result_url, modal_call_id,
       queued_at, started_at, completed_at
from generation_jobs
order by created_at desc limit 1;
```

Pass criteria: `status = completed`, a real `result_url`, and non-null `workflow_version`, `provider`, `workflow_config_hash`, `worker_version`. If `provider`/`workflow_version`/`worker_version` are null, V6 is not populating the new columns and the cutover must not proceed.

## Step 3 — Image Lab cutover (reversible)

No code change. Change one env var on the Image Lab Netlify site, then trigger a redeploy:

- Netlify → Image Lab site → Site settings → Environment variables:
  - `VITE_GENERATION_API_URL` → `https://brandverita--brandverita-api-v6-fastapi-app.modal.run`
  - keep `VITE_GENERATION_ENABLED=true`
- Trigger a new deploy (or push an empty commit) so Netlify rebuilds with the new value.
- Smoke test in the live Image Lab: sign in, run one generation, confirm the image renders, the dev panel shows `provider`/`workflow_version`/`config-hash`, and the footer reports the API as live.

Optional — this Lovable preview: add the same `VITE_GENERATION_API_URL` + `VITE_GENERATION_ENABLED=true` to the project `.env` if you want to verify V6 from the preview before touching production Image Lab. Currently the preview has neither, so generation is disabled there.

## Step 4 — optional hardening (low priority, separate deploy)

Add a `modules_present` object to the V6 `/health` payload from `os.path.exists("/root/jwks_auth.py")` (plus the other three modules) and `os.path.isdir("/root/adapters")`. One curl then verifies packaging on every future deploy instead of waiting for a crash trace. This is a V6 `api.py` edit + redeploy of `brandverita-api-v6` only; do it after the cutover so it doesn't block verification.

## Rollback

V5 is untouched throughout. If V6 misbehaves after cutover: flip `VITE_GENERATION_API_URL` back to the V5 URL on the Image Lab Netlify site and redeploy. V5 keeps serving. If you want to silence a bad V6 entirely: `modal app stop brandverita-api-v6` (and optionally `modal app stop comfyui-generation-worker-v6`); V5 is unaffected.

## What I will do in this project when approved

- Optionally add `VITE_GENERATION_API_URL` + `VITE_GENERATION_ENABLED=true` to `.env` so the preview can hit V6.
- No other source changes — the frontend is already V6-compatible via the registry legacy alias.

Steps 1–3 are terminal/Netlify actions on your side; I can't run them from here because they need your authenticated Supabase token and your Netlify console. Send me the contract-check status codes and the end-to-end job row, and I'll confirm go/no-go for the production cutover.
