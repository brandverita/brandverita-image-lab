# Fix the 5-minute timeout: the job is never handed to the GPU worker

## What the log proves

Auth and the API are now healthy. In `modal-log.txt`:

- `POST /v1/generations` succeeded and created job `c3f77339-…`
- every 2s poll `GET /v1/generations/c3f77339-…` returned `200 OK` for the full 5 minutes
- there is not a single error, traceback, 401 or 500 in the whole log

So the row was created with `status: "queued"` and nothing ever moved it. The frontend polled correctly and then hit its own 5-minute deadline — the timeout message is accurate reporting, not a frontend bug.

## Root cause

In the deployed `api.py` (matching `api_v2.py` lines 360-370), the call that starts the ComfyUI worker is still commented out:

```text
# worker = modal.Cls.from_name("comfyui-generation-worker", "ComfyUIWorker")
# worker().generate_image.spawn(...)
```

The API inserts the queued row and returns. No GPU work is ever requested, so the status stays `queued` forever.

## The fix (backend only, no frontend changes needed)

1. Uncomment and correct the worker dispatch in `start_generation`, so it runs immediately after the queued row is inserted, wrapped in a `try/except` that marks the job `failed` with a readable `error_message` if dispatch throws — a dispatch failure must never leave a job stuck in `queued` again.
2. Add `modal` to the API image dependencies. The current image installs only `fastapi`, `httpx`, `pydantic`, `uvicorn`, so `import modal` inside the web app would fail at dispatch time.
3. Match the exact deployed worker names. Before wiring, confirm from your Modal dashboard (or `modal app list`) the app name, class name, and method name of the worker you deployed from `modal_worker.py`, plus the exact keyword arguments its method accepts. The placeholder names above are guesses and are the one thing that must be verified rather than assumed.
4. Confirm the worker writes back to `generation_jobs`: `status` transitions (`running` → `completed`/`failed`), `progress`, `output_path`, and `completed_at`, keyed on the `job_id` the API passes in. If it only returns a value instead of updating the row, the polling contract still breaks; in that case the API dispatch should be a `spawn` plus the worker updating the row via the service-role key it already has as a Modal secret.

I will deliver an updated `api.py` for you to `modal deploy`.

## Optional frontend follow-up (only if you want it)

Right now a stuck job looks identical to a slow job for 5 minutes. If useful, the status panel can surface "still queued — no worker has picked this up" once a job stays `queued` for more than ~60 seconds, so this failure mode is obvious in seconds rather than minutes. Say the word and I'll include it.

## What I need from you

Upload or paste the current `modal_worker.py` (the version you deployed), so the dispatch call uses its real app/class/method names and argument signature instead of placeholders.

## Technical notes

- No schema changes: `prompt`, `negative_prompt`, `width`, `height`, `seed`, `idempotency_key`, `progress`, `output_path` already exist on `public.generation_jobs`.
- No secrets move into the frontend; dispatch happens entirely inside the Modal API function.
- The frontend's 5-minute poll deadline and 2s interval stay as they are.
