# Review of modal_worker.py and api.py

Both files were reviewed against the live `comfy-ui` database and the frontend contract. `modal_worker.py` will **not** work as uploaded — there is one hard deploy/runtime bug, four missing database columns, and a missing storage bucket.

## 1. Blocking bug in modal_worker.py

Line 286: the result-refresh endpoint is registered as `@app.get("/v1/generations/{job_id}/result")`. `app` is the `modal.App`, not FastAPI — this raises `AttributeError: 'App' object has no attribute 'get'` at import time, so `modal deploy` fails.

Fix: `@web_app.get("/v1/generations/{job_id}/result")`.

## 2. Missing database columns (insert would 500)

`public.generation_jobs` currently has: `id, user_id, workflow_id, status, prompt_hash, idempotency_key, modal_call_id, output_path, result_url, width, height, seed, error_message, created_at, updated_at, completed_at`.

The API writes/reads four columns that do not exist yet:

- `prompt` (text)
- `negative_prompt` (text)
- `progress` (integer, default 0)
- `error_code` (text)

`width`, `height`, `seed`, `idempotency_key` already exist — no change needed there.

Migration to run (this is the only change inside this Lovable project):

- Add the four columns as nullable / defaulted so existing rows stay valid.
- Add a unique index on `(user_id, idempotency_key)` so the idempotency check can't race and double-insert.
- No new RLS policies: reads stay `auth.uid() = user_id AND is_email_allowed(auth.uid())`, writes stay `service_role`-only.

Note on privacy: storing the raw `prompt` alongside `prompt_hash` means prompts are now readable by anyone with database access. That matches your request; say the word if you'd rather keep hashes only.

## 3. Missing storage bucket

`/v1/generations/{job_id}/result` signs from bucket `generation-outputs`, which does not exist in the project — every result refresh would 500. It needs to be created as a **private** bucket. The frontend never reads it directly; only signed URLs from the API.

## 4. Other modal_worker.py notes (non-blocking)

- The idempotent-replay branch returns only `job_id/status/workflow_id/progress`; add `result_url`, `width`, `height`, `completed_at` so a resubmit of a finished job returns the image instead of looking queued.
- `progress` is read back with `job.get("progress")` — covered once the column exists.
- `/debug/config` is safe as written (booleans plus host only), but it is unauthenticated; worth removing before this is shared more widely.
- The worker invocation is still commented out, so jobs stay `queued` forever and the frontend will hit its 5-minute poll timeout. Expected for this step — just don't read a timeout as an API failure.
- Confirm the Modal secret is named exactly `brandverita-supabase-comfy-ui` and contains `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`; `get_supabase_client()` uses `os.environ[...]` and will crash on a name mismatch.
- CORS list is correct for the Netlify origin. The Lovable preview origin is not in it, so browser tests must run against the Netlify URL (or add the preview origin).

## 5. api.py — do not deploy it

`api.py` declares `modal.App("brandverita-api")` — the **same app name** as `modal_worker.py`. Deploying it replaces the real API with an unauthenticated stub that returns fake job IDs and never writes to the database. It also uses `allow_origins=["*"]` and has no bearer-token check.

Recommendation: keep `modal_worker.py` as the single deployable entrypoint and delete `api.py` (or rename its app to something like `brandverita-api-scratch` if you want to keep it for experiments). It carries no logic worth merging.

## Work in this project

1. Migration adding `prompt`, `negative_prompt`, `progress`, `error_code` to `generation_jobs`, plus the unique `(user_id, idempotency_key)` index.
2. Create the private `generation-outputs` storage bucket.
3. No frontend code changes — the existing client already handles `progress`, `error_code`, and the `/result` refresh.

The two Python fixes (line 286, richer replay response) are yours to apply in your local `modal_worker.py` before redeploying; that file lives outside this repo.
