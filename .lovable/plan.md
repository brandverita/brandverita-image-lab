# Stuck image generations: the Flux worker is never picking jobs up

## What the records show (verified)

Your two runs today are recorded, but they never left the queue:

| Time (UTC) | Workflow | Status | Dispatch reference |
|---|---|---|---|
| 21 Sep 13:45 | Flux text-to-image (v1) | queued | none |
| 21 Sep 13:38 | Flux text-to-image (v2) | queued | none |
| 20 Sep 02:44 | Flux text-to-image (v2) | queued | none |
| 19 Sep 14:01 | Editorial layout | completed | present |

Confirmed:

- All three stuck runs are **plain Flux text-to-image**, handled by the self-hosted GPU worker — not BFL.
- Every BFL-backed run (editorial layout, smart resize, product scene) completed normally, the most recent on 19 Sep at 14:01.
- All three stuck rows have **no dispatch reference at all**, `progress` 0, and no start time: the hand-off to the GPU worker never returned. No error was recorded either, which is why the app just spins.
- The last successful Flux run was 19 Sep 12:11, shortly **before** that afternoon's redeploy. Everything Flux since then has hung.

From your two commands:

- The GPU worker app is **deployed** but running **0 tasks** — it has never been woken by these jobs.
- The service log for the stall window contains **only the app's own status checks** (`GET /v1/generations/...` and `/health`). There is no record of the submission itself and no dispatch or error line at all.

So this is not a BFL problem and not a prompt or preset problem. The Flux hand-off is failing silently, and the service records nothing when it does.

## Still to confirm (one short step)

Two candidates remain, and the log excerpt you pasted cannot separate them:

1. **Name mismatch.** The app list truncated both worker names to `comfyui-generation-wo…`. There are two of them, created 15 Aug and 27 Aug. If the one the service looks up (`comfyui-generation-worker-v6`) isn't the exact name of either, every lookup fails.
2. **A swallowed error.** The hand-off raises, the service catches it, leaves the job queued and logs nothing.

### What to run (two commands)

```
python -m modal app list --json | grep -i comfyui
python -m modal app logs brandverita-api-v6 | grep -iE "spawn|dispatch|worker|Error|Traceback|POST /v1/generations"
```

Paste back the full worker names and any matching lines. If the second command returns nothing at all, that itself confirms candidate 2 — the failure is being swallowed.

## Plan

### 1. Fix the dispatch

- **Name mismatch** — point the service at the exact deployed worker app name and redeploy the service. No code-shape change.
- **Swallowed error** — the hand-off gets a real failure path: on any exception the job is marked failed with a specific error code and a human-readable message, and the exception is logged. Then the next run shows the actual reason instead of hanging.

### 2. Make a silent stall impossible to miss

- A run still holding no dispatch reference after a short grace period is failed automatically, so the app shows a clear error with a retry instead of spinning for seven minutes. The stale-job expiry added on 19 Sep only fires while a job is being actively polled, which is why the 20 Sep run is still sitting in the queue.
- `/health` gains a real worker-reachability check instead of only reporting that dispatch is configured.

### 3. Close out the three stuck runs

Marked failed with an explicit reason so the history is honest.

### 4. Verify

One Flux text-to-image run end to end from the test app: image returned, dispatch reference present, no queued leftovers.

## Out of scope

- No change to the BFL modules (editorial layout, smart resize, product scene) — all verified working.
- No registry, preset, pricing, or Studio-exposure changes.
- No change to the request shape or the app's forms.

## Technical notes

- Stuck job ids: `ca39c3d0-ffe5-4686-952b-a5eed88e38bd`, `db1c837a-5495-4a15-956c-317d426b0dd5`, `7e9aa563-3906-4afc-bcca-adb8e194721d`.
- `modal_call_id IS NULL` on a `queued` row is the unique signal that `spawn` never returned; every completed row carries a value.
- Both `flux_text_to_image:v1` and `:v2` hang, so it is the dispatch path, not a single registry row.
- Service reads `WORKER_APP_NAME` (default `comfyui-generation-worker-v6`) and `ComfyUIWorker` via `modal.Cls.from_name`; a wrong name fails only at call time, which is consistent with a healthy `/health`.
- `/health` reports `dispatch: true` from configuration alone, so it cannot detect this class of failure today.
