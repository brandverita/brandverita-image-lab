# Unstick the post-redeploy generation + silence the Modal async warning

## What actually happened (confirmed)

- The stuck job is `4394c3b7-824c-4b70-a414-048d381a444b` (created 15:59:05 UTC): it reached `uploading_output` at 16:00:12 and has not moved since. The GPU render finished — the row froze at the upload step.
- Timeline matches the redeploy: `modal deploy` replaces the running API app, which terminates the background orchestrator (`run_generation`) mid-flight. The worker finished rendering, but the function responsible for uploading the result and marking the job `completed` was killed. The job is orphaned, not still working.
- The `AsyncUsageWarning` at `adapters/modal_comfyui.py:99` is a **warning, not the cause**. `_dispatcher.spawn(...)` is called from the async request handler; Modal flags the blocking call but it still works (all four earlier jobs today completed through the same code path).
- `prompt_layers.py` and the new `api.py` are not implicated: dispatch, spawn, and the job row all behaved normally until the second deploy cut the container.

## Steps

1. **Close the orphaned job (one data fix).**
   Mark `4394c3b7…` as `failed` with a clear error (`error_code: orphaned_by_deploy`, human message that a retry is safe). Its idempotency already consumed; a fresh Generate click creates a new key, so no credit/job duplication concern.

2. **Verify the service is healthy.**
   Run one normal free-text generation and confirm it completes end to end (expected ~60–70s warm, per today's earlier runs). Also confirm `GET /v1/prompt-layers` now answers 200 with the catalogue (validates the new deploy).

3. **Fix the async warning properly (Modal-side file, one-line change).**
   In `modal-project/phase1-v6-staging/adapters/modal_comfyui.py` line ~99, change the blocking spawn to Modal's async interface:
   ```python
   call = await _dispatcher.spawn.aio(job_id=job["job_id"], user_id=job["user_id"])
   ```
   (Exact call signature kept as-is; only `.spawn(` → `await .spawn.aio(`.) The same pattern in `modal_research_outpaint.py` (`_dispatcher.spawn` and `worker.outpaint.spawn`) gets the same treatment where the caller is async. Then redeploy once. This removes the event-loop blocking the warning describes — the real latent risk if the API is ever under concurrent load.

4. **Harden against the next redeploy (small, optional but recommended).**
   Extend the existing stale-job expiry so a job stuck in `uploading_output` (and `processing`/`dispatching`) longer than a threshold (e.g. 10 min past `updated_at`) is marked `expired` with a retry-safe message. Today only some non-terminal states appear to be covered, which is why this orphan sat at "processing" in the UI instead of failing cleanly. One focused change in the jobs/expiry module plus a test in the existing suite.

## Deliberately out of scope

- No changes to the frontend, Branding/StylePicker UI, Smart Resize, Product Scene, Studio, or myaccount.
- No registry changes — the workflow envelope is unchanged.
- No rework of the dispatch architecture; the orchestrator-in-API design stays.

## Technical details

- Stuck row: `generation_jobs.id = 4394c3b7-824c-4b70-a414-048d381a444b`, `modal_call_id fc-01M2B5G1G1E22CQ7Z7DN930EHJ`, `status uploading_output`, last update 16:00:12 UTC.
- Fix lives partly in the Modal project copy (`modal-project/phase1-v6-staging/adapters/modal_comfyui.py`), which is outside this repo — step 3 is applied by you there; I prepare the exact diff here.
- Steps 1 and 4 touch this repo: a one-off SQL update and the stale-job expiry extension in `backend/` with tests.
