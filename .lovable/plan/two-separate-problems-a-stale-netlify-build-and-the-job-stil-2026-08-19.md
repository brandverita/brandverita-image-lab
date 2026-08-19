# Two separate problems: a stale Netlify build, and the job still never reaching the worker

## 1. The 403 from Supabase is a stale deployed bundle, not a code bug

The failing request is the recent-jobs query and Supabase's reply is exact: `No API key found in request`.

I ran that same query against the current source in the live preview. The outgoing request carried both headers (`apikey: true`, `authorization: true`) and returned successfully with no error. So the current `src/integrations/supabase/client.ts` — which attaches `apikey` through a custom fetch — is correct.

The bundle running on `brandverita-image-lab.netlify.app` predates that fix, so its Supabase client sends no `apikey` header. Fix: trigger a fresh Netlify build of the current `main`. No frontend code change is needed for this.

## 2. The generation is still never dispatched — confirmed from the database

Row for the job you just ran (`2f933030-…`):

```text
status         queued
progress       0
modal_call_id  NULL
output_path    NULL
error_code     NULL
completed_at   NULL
created_at     06:01:04.811
updated_at     06:01:05.502
```

That row was touched once, right after insert, and never again. In `api_v3.py` the POST handler writes `modal_call_id` immediately after `run_generation.spawn(...)`, and `run_generation` sets `status: running, progress: 10` as its very first action. Neither happened, and `error_code` is empty so the `dispatch_failed` path did not fire either (which would also have made the POST return 503 rather than 200).

Your Modal log excerpt only shows the web-route function (`fastapi_app`): `/health`, `OPTIONS`, `POST`, and the 2s `GET` polls. A `run_generation` invocation is a **separate function** in the same app and would appear under its own entry, not in that route list.

The evidence is consistent with the deployed `api.py` still being the v2 file (no dispatch at all). It is also consistent with `run_generation` being deployed but dying before its first write. Those two are indistinguishable from the row alone, so the plan verifies which one it is instead of assuming.

## Fix plan

**Step 1 — establish which API build is live (no guessing).**
Add a version marker to the API so this can never be ambiguous again:

- `GET /health` returns `{"status": "ok", "service": "brandverita-api", "version": "v3", "dispatch": true}`.

After deploying, open the `/health` URL. If it does not report `version: v3`, the deployed file is the old one and the redeploy is the entire fix.

**Step 2 — make dispatch observable in the row itself.**
In `start_generation`, after `spawn` returns, write both `modal_call_id` and `status: "dispatched"`-equivalent evidence:

- always write `modal_call_id` (fall back to a literal `"spawned"` when `object_id` is unavailable, so a NULL can only ever mean "spawn never returned")
- keep the existing `try/except` that marks the row `failed` with `error_code: dispatch_failed`

This makes the three states distinct on the next run: no dispatch (`modal_call_id` NULL), dispatched but worker never started (`modal_call_id` set, `status` still `queued`), or dispatch rejected (`status` `failed`).

**Step 3 — pin `modal` in the API image.**
`api_image` installs only `fastapi`, `uvicorn`, `pydantic`, `httpx`. The module does `import modal` at the top and calls `modal.Cls.from_name` inside `run_generation`. Modal normally injects its own client, but pinning it explicitly removes an entire class of silent failure at dispatch time.

**Step 4 — confirm the worker call signature stays correct.**
Verified against your deployed `modal_worker.py`: app `comfyui-generation-worker`, class `ComfyUIWorker`, method `generate_image(workflow_json: dict) -> bytes`. The v3 orchestrator's `modal.Cls.from_name("comfyui-generation-worker", "ComfyUIWorker")().generate_image.remote(workflow)` matches it, so no change is needed there.

**Step 5 — retest and read the right log.**
After `modal deploy`, check `/health` first, then run one generation and open the **`run_generation`** function's logs in the Modal dashboard (not the web-route list). That log will either show the ComfyUI cold start or the exception that stops it.

## What you'll need to do

1. Redeploy the Netlify site (fixes the 403 recent-jobs error).
2. Deploy the `api.py` I hand you, then paste the `/health` response and, if the job still stays queued, the `run_generation` function log.

## Technical notes

- No frontend changes in this plan. The 12-minute poll deadline and the "Still queued — no worker has picked this job up yet" message after 90s are already correct and were the diagnostics that surfaced this.
- No schema changes; `modal_call_id`, `progress`, `output_path`, `error_code`, `error_message` all exist.
- No secrets move into the frontend; all dispatch and storage work stays inside Modal with the service-role key.
