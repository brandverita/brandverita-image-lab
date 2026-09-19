# Pre-deploy status — Module C editorial layout (brandverita-api-v6)

**Status: code is ready; the deploy is blocked by the `modal` command running
on the wrong Python.** Your two earlier blockers (missing files) are now fixed.
One environment fix remains, then the deploy works. No code changes.

## Now confirmed GOOD

- `editorial_presets.py`, `editorial_typography.py`, and `fonts/` are copied in —
  `presets OK` and `typography OK` both pass.
- `import api` → clean, **no SyntaxError**; adapters in the safe sync shape.
- Your adapters dir and all 11 other modules are present.

## The deploy failure — root cause

The traceback's top line is the key:

```
/Users/andreasmacbook/Desktop/modal-project/venv/lib/python3.8/site-packages/modal/...
```

That is your **old `venv` on Python 3.8**, NOT the `venv310` (Python 3.10) you
activated. The failing import chain is:

```
api.py:73  import advanced
advanced.py:36  import assets
assets.py:33  from PIL import Image   →  ModuleNotFoundError: No module named 'PIL'
```

The old py3.8 `venv` does not have Pillow. Your import checks passed because
those ran under `venv310`, which DOES have Pillow. So the situation is:

- `python` → venv310 (py3.10, has Pillow) ✅
- `modal` → old `venv` (py3.8, no Pillow) ❌

`venv310` doesn't have the Modal CLI installed, so `modal` falls through on your
PATH to the old py3.8 `venv`. The "Modal will soon drop support for Python 3.8"
warning you saw earlier confirms `modal` has been running on py3.8 all along.

Why this matters: `modal deploy` must *import `api.py` locally* to discover the
app and image definition. The local CLI Python therefore needs api.py's
import-time deps (fastapi, pydantic, and now Pillow via `advanced → assets`).
It does NOT need to match the remote image (the image is py3.11 and pip_installs
its own Pillow) — it only needs Pillow in whichever Python runs the CLI.

## The fix — make `modal` run under venv310

Install the Modal CLI into `venv310` so it runs on Python 3.10, where everything
(including Pillow) already works:

```bash
cd ~/Desktop/modal-project/phase1-v6-staging
source ~/Desktop/modal-project/venv310/bin/activate
python -m pip install modal
which modal             # MUST show a path inside venv310, e.g. .../venv310/bin/modal
modal profile current   # should still show: brandverita  (auth is user-level, carries over)
modal deploy api.py
```

The important verification is `which modal` — it must point inside `venv310`.
If it still shows the old `venv` path, the old venv's `bin` is ahead on your
PATH; run `hash -r` (zsh) and re-check, or invoke it directly as
`~/Desktop/modal-project/venv310/bin/modal deploy api.py`.

## Fallback (only if `pip install modal` on py3.10 hits your old-hardware issues)

Install just the one missing package into the py3.8 venv the CLI is already
using, then deploy:

```bash
~/Desktop/modal-project/venv/bin/python -m pip install Pillow
cd ~/Desktop/modal-project/phase1-v6-staging
modal deploy api.py
```

Prefer the venv310 route — Modal is dropping Python 3.8, so the old venv will
stop working for deploys regardless.

## Post-deploy verification

```bash
curl --fail-with-body --max-time 30 \
  https://brandverita--brandverita-api-v6-fastapi-app.modal.run/health
```

Expect `version: v6`, `app_name: brandverita-api-v6`, and in `modules` both
`editorial_layout: true` and an `editorial_layout_adapter` entry. Then watch the
Modal log for the new revision: no fresh `ModuleNotFoundError`, no `SyntaxError`.

## Rollback

If the new revision fails health, redeploy the last-known-good `api.py` (without
the editorial additions), or stop `brandverita-api-v6` and keep Image Lab on V5.
Do NOT touch V5 or the `comfyui-generation-worker-v6` worker.

## After the deploy (separate, not part of this checklist)

- Run `editorial-registry-migration.sql` in the Supabase `comfy-ui` SQL editor.
- Set the config hash: `python backend/phase2b/tools/set_config_hash.py editorial_layout v1`
  (from the workspace that has `backend/phase2b/`; needs the service-role secret).
- Run a capped editorial evaluation batch, then close BFL disclosures and decide
  Studio exposure.

## Note

A `roadmap.md` entry for this blocker could not be written — plan mode locks
all files except this plan. It's recorded here; I can add it to the roadmap once
you switch to build mode.
