# Fix the WP1 API import error

## Confirmed cause

`api.py` line 76 imports `modal_research_outpaint` from the `adapters` package, but that
file was never copied into `phase1-v6-staging/adapters/`. The traceback names
`adapters/__init__.py` as the resolution point, which means the package exists and only the
new module is missing. This is a missing-file problem, not a code problem — `api.py` is the
correct WP1 version (it already has the `outpaint_geometry.py` and `adapters/` image copy
layers).

Step 1 of the WP1 README lists two files for `phase1-v6-staging/` that are easy to miss:
`outpaint_geometry.py` and `adapters/modal_research_outpaint.py`. If the adapter is missing,
the geometry module is very likely missing too.

## Fix

Copy both missing files from the repo download into the staging folder:

- `backend/phase2b/adapters/modal_research_outpaint.py` → `phase1-v6-staging/adapters/modal_research_outpaint.py`
- `backend/phase2b/outpaint_geometry.py` → `phase1-v6-staging/outpaint_geometry.py`

Then clear stale caches so Python does not resolve an old package listing:

```bash
cd ~/Desktop/modal-project/phase1-v6-staging
rm -rf __pycache__ adapters/__pycache__
```

No edit to `api.py`, `adapters/__init__.py`, the worker, the registry, secrets, or V5 is
required.

## Re-verify before deploying

```bash
cd ~/Desktop/modal-project/phase1-v6-staging
source ../venv/bin/activate
ls adapters/            # expect modal_research_outpaint.py present
ls outpaint_geometry.py
python -c "import api, outpaint_geometry; import adapters.modal_research_outpaint; print('WP1 import graph OK')"
```

Expect the run to end with `WP1 import graph OK`. If a different `ModuleNotFoundError`
appears (for example `PIL`), install that package in the local venv — `modal deploy` imports
the whole graph locally before building the image.

## Deploy and confirm

```bash
modal deploy api.py
curl --fail-with-body --max-time 30 \
  https://brandverita--brandverita-api-v6-fastapi-app.modal.run/health
```

Expect in the health payload:

- `"outpaint_adapter": "modal_research_2b"`
- `"research_worker_app": "comfyui-research-worker-2b"`
- `"advanced_flags_enabled": false`

The deploy output should now list `outpaint_geometry.py` and the `adapters` directory among
the copied image layers.

## Then

Once `/health` reports those three markers, run the WP1 controlled test
(`backend/phase2b/tests/test_wp1_outpaint.py`, step 7 of the README) and paste the output so
the WP1 build manifest can be recorded. Flags stay false until the script tells you which two
to flip.

## Rollback

Nothing deployed changes state until `modal deploy api.py` succeeds. The already-deployed
`comfyui-research-worker-2b` is isolated and can be stopped independently; V5, V6 Flux, and
the Phase 1 worker are untouched.
