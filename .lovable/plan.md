# WP1 test run — you are running the old test script

## What the output actually shows

Two lines identify the file as the pre-revision copy:

- `FAIL 1 flags off -> 403 workflow_not_available` — that check no longer exists.
- `>>> ACTION REQUIRED: set ADVANCED_WORKFLOWS_ENABLED and OUTPAINT_EVAL_ENABLED to true` — the flag-flip pause was removed when staging research flags started shipping ON in the `api_image`.

The current `backend/phase2b/tests/test_wp1_outpaint.py` in this repo has check 1 as `1 unknown source_asset_id -> 4xx, no dispatch` and contains no `input()` pause.

So the 404 `asset_not_found` you saw is not a defect — under the current script that response is exactly what check 1 asserts. Your API is behaving correctly; the assertion in your local copy is stale.

## Action

1. Press Ctrl-C to stop the paused run.
2. Re-download `backend/phase2b/tests/test_wp1_outpaint.py` from the repo, overwriting your local copy in `tests/`.
3. Delete `tests/__pycache__`.
4. Re-run, unchanged env:

```bash
V6=https://brandverita--brandverita-api-v6-fastapi-app.modal.run \
TOK_A=<staging JWT> \
SUPABASE_URL=https://thspgkedjkiltrcimond.supabase.co \
ASSET=/path/to/brandverita-square-source.png \
python test_wp1_outpaint.py
```

It runs straight through with no pauses. Checks 6 and 9 print SQL/log lines for you to confirm manually.

## Before re-running, confirm the deploy is current

`curl -s $V6/health` should show:

- `advanced_flags_enabled: true`
- `outpaint_adapter: modal_research_2b`
- `research_worker_app: comfyui-research-worker-2b`

If `advanced_flags_enabled` is false, your `api.py` is also the older copy — re-download `backend/phase2b/api.py` and `backend/phase2b/adapters/modal_research_outpaint.py` and redeploy. Same for the worker pair (`research_worker.py`, `outpaint_graph.py`) if `modal deploy research_worker.py` did not pull ~4.3 GB and print a digest check — that build-time fetch is what the fix added.

## Then

Paste the full run output plus the two SQL result sets it prints (the `generation_assets` row and the `transformation_eval_runs` row) and the WP1 build manifest gets recorded in `backend/phase2b/module-a.md`.
