# Stuck image generations: the Flux worker is never picking jobs up

## What the records show (verified)

Your two runs today are recorded, but they never left the queue:

| Time (UTC) | Workflow | Status | Dispatch reference |
|---|---|---|---|
| 21 Sep 13:45 | Flux text-to-image (v1) | queued | none |
| 21 Sep 13:38 | Flux text-to-image (v2) | queued | none |
| 20 Sep 02:44 | Flux text-to-image (v2) | queued | none |
| 19 Sep 14:01 | Editorial layout | completed | present |

Facts confirmed from the records:

- All three stuck runs are **plain Flux text-to-image**, handled by the self-hosted GPU worker — not BFL.
- Every BFL-backed run (editorial layout, smart resize, product scene) completed normally, the most recent on 19 Sep at 14:01.
- All three stuck rows have **no dispatch reference at all**, `progress` 0, and no start time. That means the hand-off to the GPU worker never returned — the job was recorded, then nothing happened. No error was recorded either, which is why the app just spins.
- The last successful Flux run was 19 Sep 12:11, shortly **before** the redeploy that afternoon. Everything Flux since then has hung.

So this is not a BFL problem and not a prompt/preset problem. The self-hosted Flux worker stopped accepting work after the 19 Sep redeploy, and the service does not notice or report it.

## Unconfirmed part

Why the hand-off silently fails is not yet confirmed — the records cannot show it. The most likely causes, in order:

1. The GPU worker app the service points at (`comfyui-generation-worker-v6`) is no longer deployed, was renamed, or its class lookup now fails.
2. The hand-off call raises an error that the service swallows instead of recording on the job.

Step 1 of the plan is to confirm which, from the live logs, before changing anything.

## Plan

### 1. Confirm the cause (you, one command each)

Run in the activated Python 3.10 environment:

```
python -m modal app list
python -m modal app logs brandverita-api-v6
```

What to look for and paste back:
- whether `comfyui-generation-worker-v6` appears in the app list and is **deployed** (not stopped);
- the log lines from 13:38 and 13:45 today — specifically any `NotFoundError`, `Cls.from_name`, `lookup`, or `spawn` error.

### 2. Fix according to what the logs say

- **Worker app not deployed / stopped** — redeploy the GPU worker from the worker project, then re-run one Flux generation to confirm.
- **Name mismatch** — align the worker app/class name the service looks up with the deployed worker; no code shape change.
- **Hand-off error being swallowed** — the dispatch step gets a proper failure path: the job is marked failed with a real error code and message instead of sitting in the queue forever.

### 3. Make this visible next time (small, safe change)

Two gaps this incident exposed:

- A run with no dispatch reference should be failed automatically after a short grace period, so the app shows a clear error and a retry instead of spinning for 7 minutes. The stale-job expiry added on 19 Sep only triggers while a job is actively being polled, which is why the 20 Sep run is still sitting in the queue.
- The three currently stuck rows get closed out with an explicit reason so history is honest.

## Out of scope

- No change to BFL modules (editorial layout, smart resize, product scene) — all verified working.
- No registry, preset, pricing, or Studio-exposure changes.
- No change to the image-service request shape or the app's forms.

## Technical notes

- Stuck job ids: `ca39c3d0-ffe5-4686-952b-a5eed88e38bd`, `db1c837a-5495-4a15-956c-317d426b0dd5`, `7e9aa563-3906-4afc-bcca-adb8e194721d`.
- `modal_call_id IS NULL` on a `queued` row is the unique signal that `spawn` never returned; every completed row has a value.
- Both `flux_text_to_image:v1` and `:v2` hang, so it is the dispatch path, not a single registry row.
- `/health` reports `dispatch: true`, which only reflects configuration, not a live worker lookup — hence no warning in the UI.
