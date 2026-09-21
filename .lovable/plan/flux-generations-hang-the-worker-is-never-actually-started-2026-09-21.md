# Flux generations hang: the worker is never actually started

## Cause (confirmed)

`adapters/modal_comfyui.py` line 95 is still the **async** version from the 19 Sep edit:

```
async def submit_generation(...):
    call = await _dispatcher.spawn.aio(...)
```

But `api.py` calls it **without** awaiting (line 860). Calling an async function without awaiting it does not run it — it returns an unstarted object and nothing is dispatched. So:

- the GPU worker is never woken (the worker app shows 0 tasks);
- no dispatch reference exists, because `spawn` never ran;
- the follow-up write of `modal_call_id` / `dispatching` gets that unstartable object instead of an id and fails quietly, leaving the row at `queued` with no error;
- the app polls forever and you see a seven-minute spin.

This is why it broke on 19 Sep and why only Flux is affected — the hosted-provider modules (editorial layout, smart resize, product scene) use different adapters and all still work. The rollback to the synchronous shape was agreed at the time but this file never got it.

Everything else checks out: `api.py` has the full `dispatch_failed` handling, the worker app name matches exactly (`comfyui-generation-worker-v6`), and the app points at the right service.

## Plan

### 1. Restore the Flux hand-off to the working shape

In `adapters/modal_comfyui.py`, replace lines 95–109 with the synchronous version that `api.py` expects:

- `def submit_generation(...)` — no `async`;
- `call = _dispatcher.spawn(...)` — no `.aio`, no `await`;
- same keyword arguments, unchanged;
- return the call id as today.

Nothing else in the file changes, and `api.py` is not touched.

### 2. Guard against a silent no-dispatch

In `api.py`, the dispatch step rejects anything that is not a usable reference (including an un-awaited coroutine) and fails the job with `dispatch_failed` plus the real exception message in the log, instead of leaving it queued.

### 3. You deploy

```
cd ~/Desktop/modal-project/phase1-v6-staging
find . -name __pycache__ -type d -exec rm -rf {} +
python -c "import api; print('api import ok')"
python -m modal deploy api.py
```

### 4. Verify

One Flux text-to-image run from the test app: an image comes back, the job records a dispatch reference, and nothing is left queued. Then one hosted-module run to confirm nothing regressed.

### 5. Close out the three stuck runs

`ca39c3d0…`, `db1c837a…`, `7e9aa563…` marked failed with an explicit reason so the history is honest.

### 6. Prevent the seven-minute spin

A run holding no dispatch reference after a short grace period is failed automatically, so the app shows a clear error with a retry. Today's stale-job expiry only fires while a job is actively polled, which is why the 20 Sep run is still sitting in the queue.

## Out of scope

- No change to the hosted-provider modules, the registry, presets, pricing, or Studio exposure.
- No change to the request shape or the app's forms.
- No conversion of the other adapters to async — the synchronous shape is the one that runs reliably.

## Technical notes

- `adapters/modal_comfyui.py` is not tracked in this repo, so I will supply the exact replacement block for you to paste; every other file I can edit here directly.
- `modal_call_id IS NULL` on a `queued` row uniquely means `spawn` never returned.
- Both `flux_text_to_image:v1` and `:v2` hang, consistent with a dispatch-path fault rather than a registry row.
- Last good Flux run: 19 Sep 12:11 UTC, immediately before that afternoon's redeploy.
