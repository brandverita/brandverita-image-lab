# Fix the deploy SyntaxError and silence the Modal async warning properly

## What happened (confirmed)

- The deploy failed at import time: `'await' outside async function` in `adapters/modal_comfyui.py:99`. The previous deploy is still live, so the service is not down.
- Root cause: `submit_generation(job, inputs, row)` is a **plain `def`**, not `async def`, in every adapter (`modal_comfyui.py`, `modal_research_outpaint.py`, `bfl_outpaint.py`, `bfl_product_scene.py`), and `api.py` calls it synchronously (`provider_ref = adapter.submit_generation(...)`, no `await`). An `await` inside it can never parse.
- So the one-line change I suggested was wrong as given — it only works if the whole call chain becomes async. This plan does that correctly.

## The fix — make the dispatch chain async (4 small edits)

1. **`adapters/modal_comfyui.py`** — `def submit_generation(` → `async def submit_generation(`, and keep `call = await _dispatcher.spawn.aio(job_id=..., user_id=...)` (the line already changed).

2. **`adapters/modal_research_outpaint.py`** — same: `def submit_generation(` → `async def submit_generation(` and `call = _dispatcher.spawn(...)` → `call = await _dispatcher.spawn.aio(...)`.
   - Do NOT touch the `worker.outpaint.spawn(...)` inside `run_outpaint` — that runs in the background Modal function (sync context), it is fine and produces no warning.

3. **`adapters/bfl_outpaint.py` and `adapters/bfl_product_scene.py`** — `def submit_generation(` → `async def submit_generation(` only. Their bodies use `.spawn(...)`? If they call `.spawn`, switch to `await ...spawn.aio(...)` the same way; if not, no body change needed. (Their signatures must match so the shared call site can `await` them.)

4. **`api.py`** (one line, ~line 818) — the call site becomes:
   ```python
   provider_ref = await adapter.submit_generation(
   ```
   `start_generation` is already `async def`, so this is valid.

Nothing else changes: no registry, no workflow envelopes, no frontend, no behavior — `.spawn.aio()` queues the background job exactly like `.spawn()`, just without blocking the event loop.

## Pre-deploy check (in modal-project/phase1-v6-staging)

```bash
grep -n "async def submit_generation" adapters/*.py   # must list all 4 adapters
grep -n "await adapter.submit_generation" api.py       # must print 1 line
rm -rf __pycache__ adapters/__pycache__
python -c "import api; print('import OK')"
modal deploy api.py
```

## Verification after deploy

1. `curl https://brandverita--brandverita-api-v6-fastapi-app.modal.run/health` → 200.
2. Run one normal free-text generation; confirm it completes end to end and the Modal log shows **no** `AsyncUsageWarning`.
3. Confirm the failed deploy attempt left no damage: the currently live app is still the previous working build until this deploy succeeds.

## Rollback

If anything misbehaves: revert the 5 edits (back to `def` + `.spawn(` + non-awaited call site) and redeploy — that is exactly the build that has been completing jobs all along.

## Out of scope

- No changes to stale-job expiry (`stale_jobs.py` — already prepared separately and unaffected), frontend, Studio, registry, or worker apps.
