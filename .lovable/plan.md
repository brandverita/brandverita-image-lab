# Fix the V6 API remote module packaging failure

## Confirmed diagnosis

The V6 app definition deployed successfully, but its web container fails while importing `/root/api.py`:

```text
ModuleNotFoundError: No module named 'jwks_auth'
```

The deployment output shows Modal created only the `api.py` source mount. The local Python 3.10 environment now has the third-party packages needed to construct the Modal app, and `api_image.pip_install(...)` already installs the remote third-party dependencies. The remaining issue is that the V6 sibling source modules were not included in the remote API image.

This affects only the new `brandverita-api-v6` deployment. The working V5 API and the separately deployed `comfyui-generation-worker-v6` do not need to be changed.

## Amendment

In `phase1-v6-staging/api.py`, extend the existing `api_image` chain after `.pip_install(...)` so it copies the complete V6 API module set into `/root` at image-build time:

- `jwks_auth.py` → `/root/jwks_auth.py`
- `supabase_rest.py` → `/root/supabase_rest.py`
- `registry.py` → `/root/registry.py`
- `jobs.py` → `/root/jobs.py`
- `adapters/` → `/root/adapters/`, including `__init__.py`, `base.py`, `modal_comfyui.py`, `replicate.py`, and `bfl_api.py`

Use Modal image source-copy methods with `copy=True` (`add_local_file` for each top-level module and `add_local_dir` for `adapters`). This explicit allow-list avoids packaging `modal_worker_v2.py`, caches, the venv, or unrelated local files.

Do not change imports, API behavior, secrets, app names, workflow logic, registry enforcement, the Flux graph, or V5.

## Pre-deploy check

From the staging package directory, confirm the entire import graph resolves locally:

```bash
cd ~/Desktop/modal-project/phase1-v6-staging
source ../venv/bin/activate
rm -rf __pycache__ adapters/__pycache__ ../__pycache__
python -c "import api, jwks_auth, supabase_rest, registry, jobs; import adapters.modal_comfyui, adapters.replicate, adapters.bfl_api; print('V6 import graph OK')"
```

Expected output ends with `V6 import graph OK`.

## Redeploy

Redeploy the same V6 app; this replaces only its broken revision:

```bash
modal deploy api.py
```

The build/deploy output should now show the sibling files/directory being added to the API image rather than only the automatic `api.py` mount.

## Verification

1. Check V6 with a bounded request so a startup failure does not look indefinitely silent:

```bash
curl --fail-with-body --max-time 30 \
  https://brandverita--brandverita-api-v6-fastapi-app.modal.run/health
```

Expect `version: v6`, `app_name: brandverita-api-v6`, and `worker_app: comfyui-generation-worker-v6`.

2. Confirm V5 remains available and identifies itself as V5:

```bash
curl --fail-with-body --max-time 30 \
  https://brandverita--brandverita-api-fastapi-app.modal.run/health
```

3. Confirm the Modal dashboard no longer reports `fastapi_app` as crash-looping and no fresh `ModuleNotFoundError` appears.

4. Run the Phase 1 contract checks, followed by one authenticated V6 end-to-end generation. Confirm the resulting row records `provider`, `workflow_version`, `workflow_config_hash`, and `worker_version`.

5. Keep the Image Lab `VITE_GENERATION_API_URL` on V5 until all checks pass. Frontend cutover remains a separate, reversible action.

## Rollback

No V5 rollback is required because V5 is untouched. If the corrected V6 revision still fails, keep Image Lab on V5 and stop only `brandverita-api-v6` while reviewing the new container log. Do not redeploy or stop either V5 app or the working V6 worker.
