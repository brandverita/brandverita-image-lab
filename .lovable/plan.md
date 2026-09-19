# Pre-deploy status — Module C editorial layout (brandverita-api-v6)

**Status: NOT ready to deploy yet.** Your readiness check caught two missing
items in `~/Desktop/modal-project/phase1-v6-staging/`. Fix them first, then the
deploy is safe. No code changes — you copy files and re-run one check.

## What your check confirmed is GOOD

- `import api` → `api import ok`: full top-level import graph resolves, **no
  SyntaxError**. (The editorial adapter IS imported at module load via
  `from adapters import (..., bfl_editorial_layout, ...)`, so it was exercised.)
- All four adapters are in the **safe sync shape** (`def submit_generation` +
  `_dispatcher.spawn(...)`), not the broken `async`/`await` version — the shape
  that completed jobs all along.
- Adapters directory is **complete**: `__init__.py`, `base.py`, `bfl_api.py`,
  `bfl_editorial_layout.py`, `bfl_outpaint.py`, `bfl_product_scene.py`,
  `modal_comfyui.py`, `modal_research_outpaint.py`, `replicate.py` all present.
- All 11 non-editorial modules present: jwks_auth, supabase_rest, registry,
  jobs, assets, usage, advanced, outpaint_geometry, scene_presets,
  prompt_layers, stale_jobs.

(The `zsh: command not found: #` / `No such file or directory` noise in Step 1
was just the inline `#` comments in my `ls` lines being pasted as commands —
harmless. The real `adapters/` listing above is complete and correct.)

## Blocker 1 — missing the two editorial modules

Step 1 and Step 2 both show:

```
MISSING editorial_presets.py
MISSING editorial_typography.py
ModuleNotFoundError: No module named 'editorial_presets'
```

`import api` passed only because these are imported *inside* the worker function,
not at module load. The first editorial job would crash on the live API without
them. Copy both from the project's `backend/phase2b/` into your staging dir:

```bash
# run from wherever your generation-test-ui repo/project copy lives
cp backend/phase2b/editorial_presets.py   ~/Desktop/modal-project/phase1-v6-staging/
cp backend/phase2b/editorial_typography.py ~/Desktop/modal-project/phase1-v6-staging/
```

## Blocker 2 — missing the `fonts/` directory

Step 1 showed `ls -1 fonts/ → No such file or directory`. The image bundles it
via `.add_local_dir("fonts", "/root/fonts", copy=True)` (api.py), so **`modal
deploy` itself fails at image build** if it's absent. Copy the whole folder
(three OFL typefaces) from `backend/phase2b/fonts/`:

```bash
cp -r backend/phase2b/fonts ~/Desktop/modal-project/phase1-v6-staging/
# must contain: LibreFranklin.ttf  LibreBaskerville.ttf  Oswald.ttf
```

## Re-run the check after copying

```bash
cd ~/Desktop/modal-project/phase1-v6-staging
rm -rf __pycache__ adapters/__pycache__
python -c "import api; import editorial_presets; print('presets OK')"
python -c "import editorial_typography; print('typography OK')"
```

Expected: `presets OK`, then `typography OK`.

Caveat on the typography line: `editorial_typography` imports PIL at top level.
If your `venv310` doesn't have Pillow, it fails **locally** with
`ModuleNotFoundError: No module named 'PIL'` — but that's a local-venv gap, NOT
a deploy problem (the Modal image `pip_install`s Pillow). Either
`pip install Pillow` to make the local check pass, or accept that line failing
locally and rely on the image. `editorial_presets` must import cleanly either
way (no third-party deps).

## Then deploy

```bash
modal deploy api.py
```

This replaces only the `brandverita-api-v6` revision. V5 and the
`comfyui-generation-worker-v6` worker are untouched.

## Post-deploy verification

```bash
curl --fail-with-body --max-time 30 \
  https://brandverita--brandverita-api-v6-fastapi-app.modal.run/health
```

Expect `version: v6`, `app_name: brandverita-api-v6`, and in `modules` both
`editorial_layout: true` and an `editorial_layout_adapter` entry. A 200 means
the new revision started without `ModuleNotFoundError`. Then watch the Modal
log for the new revision: no fresh `ModuleNotFoundError`, no `SyntaxError`.

## Rollback

If the new revision fails health, redeploy the last-known-good `api.py` (without
the editorial additions), or stop `brandverita-api-v6` and keep Image Lab on V5.
Do NOT touch V5 or the worker.

## After the deploy (separate, not part of this checklist)

- Run `editorial-registry-migration.sql` in the Supabase `comfy-ui` SQL editor.
- Set the config hash: `python backend/phase2b/tools/set_config_hash.py editorial_layout v1`
  (from the workspace that has `backend/phase2b/`; needs the service-role secret).
- Run a capped editorial evaluation batch, then close BFL disclosures and decide
  Studio exposure.
