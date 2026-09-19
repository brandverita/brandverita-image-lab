# Pre-deploy verification — Module C editorial layout (brandverita-api-v6)

Goal: confirm the local `phase1-v6-staging` directory is safe to deploy with the
new editorial module before running `modal deploy api.py`. No code changes —
read-only checks you run in your venv, then the deploy and a health check.

## Already confirmed (from your terminal + repo source)

- `python -c "import api"` → `api import ok`. Full top-level import graph
  resolves, **no SyntaxError**.
- The editorial adapter IS exercised at import time: `api.py` top-level does
  `from adapters import (..., bfl_editorial_layout, ...)`, so your local
  `adapters/__init__.py` and `bfl_editorial_layout.py` are present and importable.
- All four adapters are in the **sync shape** (`def submit_generation` +
  `_dispatcher.spawn(...)`), NOT the broken `async def`/`await .spawn.aio()`
  version. This is the shape that completed jobs all along.
- Profile `brandverita`; dir `~/Desktop/modal-project/phase1-v6-staging`;
  `APP_NAME = brandverita-api-v6`; worker refs `comfyui-generation-worker-v6` /
  `ComfyUIWorker`. All correct.

## What `import api` does NOT cover (the remaining checks)

The editorial worker body lazily imports `editorial_presets` and
`editorial_typography` *inside* `run_editorial_layout`, so a stale/missing
sibling file would pass `import api` and only fail at runtime on the first
editorial job. Run these in your venv before deploying:

### 1. Confirm every file the image bundles is present locally

The image (in `api.py`) bundles these via `add_local_file` / `add_local_dir`.
If any is missing, `modal deploy` itself fails at image build (not silent):

```bash
cd ~/Desktop/modal-project/phase1-v6-staging
for f in jwks_auth.py supabase_rest.py registry.py jobs.py assets.py usage.py \
         advanced.py outpaint_geometry.py scene_presets.py prompt_layers.py \
         stale_jobs.py editorial_presets.py editorial_typography.py; do
  test -f "$f" && echo "ok  $f" || echo "MISSING $f"
done
ls -1 adapters/        # must include: __init__.py base.py modal_comfyui.py
                       #   bfl_outpaint.py bfl_product_scene.py bfl_editorial_layout.py
                       #   (replicate.py bfl_api.py if your __init__ imports them)
ls -1 fonts/           # must include: LibreFranklin.ttf LibreBaskerville.ttf Oswald.ttf
```

### 2. Clear stale bytecode (so old `.pyc` can't mask a stale source file)

```bash
rm -rf __pycache__ adapters/__pycache__
```

### 3. Force-import the editorial modules (the check `import api` skips)

```bash
python -c "import api; import editorial_presets; import editorial_typography; import advanced; import jobs; import registry; import supabase_rest; import stale_jobs; print('editorial import graph OK')"
```

Expected: `editorial import graph OK`.

Caveat: `editorial_typography` does `from PIL import Image...` at top level. If
your local `venv310` does not have Pillow installed, this line fails **locally
even though it works on Modal** (the image `pip_install`s Pillow). If you see
`ModuleNotFoundError: No module named 'PIL'`, install it locally
(`pip install Pillow`) and re-run, OR skip importing `editorial_typography`
and rely on the image's pip_install — it is not a deploy blocker, only a
local-check limitation.

### 4. Confirm the two Modal secrets exist (runtime needs them; deploy does not)

```bash
modal secret list
```

Must include:
- `brandverita-supabase-comfy-ui` (Supabase service-role for job/asset REST)
- `bfl-research-2b` (BFL_API_KEY for the hosted editorial call)

These already exist from Module B, so this is a sanity check only.

## Deploy

All checks green →

```bash
modal deploy api.py
```

This replaces only the `brandverita-api-v6` revision. The V5 API and the
`comfyui-generation-worker-v6` worker are untouched.

## Post-deploy verification

```bash
# 1. Health — bounded so a startup crash isn't silent
curl --fail-with-body --max-time 30 \
  https://brandverita--brandverita-api-v6-fastapi-app.modal.run/health
```

Expect `version: v6`, `app_name: brandverita-api-v6`, and in the `modules`
object both `editorial_layout: true` and an `editorial_layout_adapter` entry.
A 200 here means the new revision started without a `ModuleNotFoundError`.

```bash
# 2. Editorial presets catalog — gated; 401 without auth, 200 with a valid
#    Studio/Supabase bearer token. Confirms the new endpoint is live.
curl -s -o /dev/null -w "%{http_code}\n" --max-time 30 \
  https://brandverita--brandverita-api-v6-fastapi-app.modal.run/v1/editorial-presets
# expect: 401
```

3. Watch the Modal log for the new app revision; confirm no fresh
   `ModuleNotFoundError` and no `SyntaxError`.

## Rollback

If the new revision fails its health check, the previous build is still the
one that served traffic until a successful deploy replaces it. To revert,
redeploy the last-known-good `api.py` (without the editorial additions), or
stop `brandverita-api-v6` and keep Image Lab pointed at V5 until resolved.
Do NOT touch V5 or the `comfyui-generation-worker-v6` worker.

## After the deploy (separate steps, not part of this checklist)

- Run the editorial registry migration (`editorial-registry-migration.sql`)
  in the Supabase `comfy-ui` SQL editor.
- Set the config hash: `python backend/phase2b/tools/set_config_hash.py editorial_layout v1`
  (run from the workspace containing `backend/phase2b/`; needs the
  service-role secret — a fresh Codespace lacks the backend files).
- Run a capped editorial evaluation batch, then close BFL disclosures and
  decide Studio exposure. These are unaffected by this deploy.
