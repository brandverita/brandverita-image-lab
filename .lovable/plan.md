# Fix: Smart Resize and Product Scene now fail with "worker could not be started"

## Cause (confirmed in the code)

Yesterday's fix added a strict check after the job is handed to a module: if the
hand-off does not return a text reference for the started worker, the run is
failed immediately with `dispatch_failed`.

The normal image generator returns a reference, or the word "spawned" when the
platform gives none — so it passes. The four hosted/research modules do **not**
have that fallback:

- `adapters/bfl_outpaint.py` line 153 (Smart Resize)
- `adapters/bfl_product_scene.py` line 72 (Product Scene)
- `adapters/bfl_editorial_layout.py` line 76 (Editorial Layouts)
- `adapters/modal_research_outpaint.py` line 61 (research Smart Resize)

Each returns "no reference" when the platform does not expose one. Before
yesterday that was harmless; now the new check treats it as a failed start and
returns `503 dispatch_failed` even though the worker was actually started.

This matches the diagnostics exactly: the Studio token, plan, modules and
workflow list are all fine — the refusal happens after dispatch, inside the
image service. Nothing is wrong with `greco@live.com` or Studio.

## Plan

1. **Give the four module hand-offs the same fallback** as the image generator:
   when the platform returns no reference, return `"spawned"` instead of
   nothing. The worker start itself is unchanged.
2. **Keep the protection that mattered.** The check stays, but it is narrowed to
   the real bug it was written for: a hand-off that returns an unstarted
   coroutine (an `async def` slipping back in) still fails loudly with the real
   reason in the log. A missing platform reference no longer kills a run that
   did start.
3. **Extend the tests** so each module hand-off is asserted to return a usable
   reference, and a coroutine-returning hand-off is still rejected. This gap is
   what let yesterday's change ship.
4. **Close out the failed runs** from this afternoon's Studio and UI tests with
   an honest reason (`dispatch_guard_false_positive`) so history is accurate.
5. **You deploy** (same routine as yesterday):
   ```
   cd ~/Desktop/modal-project/phase1-v6-staging
   # copy the 4 updated adapter files + api.py from the repo
   find . -name __pycache__ -type d -exec rm -rf {} +
   python -c "import api; print('api import ok')"
   python -m modal deploy api.py
   ```
6. **Verify**: one Smart Resize and one Product Scene run from the test UI, then
   one from Studio with the same account, plus one normal image to confirm no
   regression.

## Out of scope

No change to presets, prompts, registry rows, config hashes, pricing, Studio
exposure, credits, or the request shape. No async conversion of any adapter.

## Technical details

Files edited here: `backend/phase2b/adapters/bfl_outpaint.py`,
`bfl_product_scene.py`, `bfl_editorial_layout.py`,
`modal_research_outpaint.py`, `backend/phase2b/api.py` (guard narrowed to
coroutine/awaitable detection plus empty-string rejection), and the dispatch
tests. `adapters/modal_comfyui.py` on your machine needs no change.
