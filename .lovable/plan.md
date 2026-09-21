# Stuck image generations: the Flux hand-off to the GPU worker

## What is confirmed

| Time (UTC) | Workflow | Status | Dispatch reference |
|---|---|---|---|
| 21 Sep 13:45 | Flux text-to-image (v1) | queued | none |
| 21 Sep 13:38 | Flux text-to-image (v2) | queued | none |
| 20 Sep 02:44 | Flux text-to-image (v2) | queued | none |
| 19 Sep 14:01 | Editorial layout | completed | present |

- Only **plain Flux text-to-image** hangs. It is the one workflow that runs on the self-hosted ComfyUI GPU worker. Every hosted-provider run (editorial layout, smart resize, product scene) completed normally.
- All three stuck rows sit at `queued`, progress 0, no start time, **no dispatch reference, and no error**. The hand-off to the GPU worker never completed and nothing was recorded about why.
- Worker naming is **not** the problem: the deployed app is exactly `comfyui-generation-worker-v6`, which is what the service looks up. The app is deployed with 0 tasks — it has never been woken by these jobs.
- The app is pointed at the right service (`brandverita-api-v6`), and that service's log shows the polling for these exact job ids, so the submissions did reach it.
- The last good Flux run was 19 Sep 12:11, shortly **before** that afternoon's redeploy.

## The likely cause (not yet confirmed)

The current `api.py` in this repo cannot produce what we are seeing. Its submit path wraps the hand-off in a failure handler that marks the job **failed** with `dispatch_failed` and prints a diagnostic line. A job left sitting at `queued` with no error means the running code does **not** contain that handler — the same situation as `advanced.py` last week: a stale local copy was deployed.

The second suspect is the Flux adapter itself. `adapters/modal_comfyui.py` exists only on your machine, never in this repo, and it is the file you hand-edited during the `await` incident on 19 Sep — the same day Flux last worked. A version that silently returns without spawning would produce exactly these rows.

Your empty `grep` over the logs does not by itself prove the handler is missing: `modal app logs` streams recent output, so an older submission may simply no longer be in it.

## Plan

### Step 1 — confirm, with two local checks

```
grep -n "dispatch_failed" api.py
grep -n "def submit_generation" -A 30 adapters/modal_comfyui.py
```

Paste both back. The first tells us whether the deployed service has the failure handler. The second shows whether the Flux adapter actually spawns the worker and returns a reference.

### Step 2 — live capture of one run

In one terminal: `python -m modal app logs brandverita-api-v6`. In the app, start one Flux generation. Paste the lines that appear during that run — that gives the real exception, if any.

### Step 3 — fix what Steps 1–2 name

- **Stale `api.py`** — deploy the current repo version (clear caches, import-check, deploy), which already fails the job loudly instead of leaving it queued.
- **Broken Flux adapter** — restore it to the known-good synchronous shape: `def submit_generation(...)` calling `_dispatcher.spawn(...)` and returning the call id, no `await`, with a hard failure if no reference comes back.
- **Worker refusing work** — redeploy the GPU worker app.

### Step 4 — make a silent stall impossible again

- A run holding no dispatch reference after a short grace period is failed automatically, so the app shows a clear error with a retry instead of spinning for seven minutes. The stale-job expiry added on 19 Sep only fires while a job is actively polled, which is why the 20 Sep run still sits in the queue.
- `/health` gains a real worker-reachability check rather than only reporting that dispatch is configured.
- The dispatch failure line logs the exception message, not just its type, so a future `grep` finds it.

### Step 5 — close out and verify

Mark the three stuck runs failed with an explicit reason, then run one Flux generation end to end: image returned, dispatch reference present, nothing left queued.

## Out of scope

- No change to the hosted-provider modules (editorial layout, smart resize, product scene) — all verified working.
- No registry, preset, pricing, or Studio-exposure changes.
- No change to the request shape or the app's forms.

## Technical notes

- Stuck job ids: `ca39c3d0-ffe5-4686-952b-a5eed88e38bd`, `db1c837a-5495-4a15-956c-317d426b0dd5`, `7e9aa563-3906-4afc-bcca-adb8e194721d`.
- `modal_call_id IS NULL` on a `queued` row uniquely means `spawn` never returned; every completed row carries a value.
- Both `flux_text_to_image:v1` and `:v2` hang, so this is the dispatch path, not one registry row.
- Repo `api.py` lines 856–904 already patch `status=failed, error_code=dispatch_failed` on any exception and print `dispatch_failed job=... type=...`; neither artefact is present in the data or logs.
- `adapters/modal_comfyui.py` is untracked here, so its current contents cannot be verified from this side — hence Step 1.
