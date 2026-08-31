# WP1 first run: what "stuck after check 3" means and how to confirm

Check 3 passing means the API accepted the job and spawned the background outpaint function.
The script now polls `GET /v1/generations/{job_id}` every 3 seconds with a 900-second
deadline, printing nothing until the job reaches `completed` or `failed`. Silence here is the
expected output shape, not a hang in the script.

The first run is a full cold start on `comfyui-research-worker-2b`: container boot, A10G
allocation, ComfyUI server startup, and the SD-1.5-inpainting checkpoint loading from the
volume into VRAM. Several minutes is normal. The worker has a 1800s function timeout and a
60s scaledown window, so it will not be killed mid-run.

## Let it poll — no action for now

Give it the full 15 minutes. If it completes, the script continues to checks 5 through 12 on
its own and prints the latency line (the p95 ≤ 90s target applies to warm runs, not this one).

## While waiting, watch the two log streams

In separate terminals:

```bash
modal app logs brandverita-api-v6
modal app logs comfyui-research-worker-2b
```

What each stream should show, in order:

- API: the job moving to `processing`, then eventually `wp1_outpaint_completed job=... verified=True`
  and `wp1_temp_cleanup ... dir_exists=False`.
- Worker: ComfyUI boot lines, then the graph executing, then `wp1_worker_cleanup files=... dir_removed=1`.

Also useful, read-only:

```sql
select status, error_code, error_message, started_at, completed_at, worker_version
from generation_jobs order by created_at desc limit 1;
```

`status = processing` with no error confirms it is genuinely running.

## If it times out or fails

Do not re-run the script from the top. Capture, in this order:

1. The last 100 lines of each of the two log streams.
2. The `generation_jobs` row above (status, `error_code`, `error_message`).
3. The `transformation_eval_runs` row for that `job_id` — the failure path writes one with
   `status = failed` and an `error_message`.

The likely first-run failure modes, distinguishable from those three sources:

- worker log shows ComfyUI never reaching `system_stats` -> boot/checkpoint problem in the worker image
- API log shows `wp1_outpaint_failed ... source_region_integrity_failed` -> geometry/composite mismatch
- API log shows a Modal lookup error naming `ResearchOutpaintWorker` -> class/app name mismatch between adapter and worker
- job stays `queued` with nothing in either log -> the background function never spawned

Paste those three items and the fix will be scoped to whichever of the above it actually is.
No flags change and no redeploy while diagnosing; the flag-off step 12 still runs at the end.

## Flags reminder

Both flags are true right now. Whatever the outcome, set `ADVANCED_WORKFLOWS_ENABLED` and
`OUTPAINT_EVAL_ENABLED` back to `"false"` and redeploy before finishing for the day — the
steady state for WP1 is all five flags false.
