# V6 API: the module-copy layers were never saved into api.py

## Confirmed cause

`grep` settles it:

- Line 70: `api_image = modal.Image.debian_slim(python_version="3.11").pip_install(` — the original one-line definition.
- `grep -n "add_local_file\|add_local_dir" api.py` returned **nothing**.

So the amended `api_image` block (the one you pasted to me) exists only in your clipboard/editor buffer, not in the deployed `api.py`. The decorators are already correct (`image=api_image` at lines 257 and 517), and all nine module files are present on disk. The container therefore ran an image with no `/root/jwks_auth.py`, exactly as the traceback says.

## The fix — one edit in `api.py`

Replace the single `api_image = ...` assignment starting at line 70 with the chained version, keeping the existing `pip_install` pin list byte-identical and appending the copy layers:

```python
api_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastapi==0.115.6",
        "uvicorn==0.34.0",
        "pydantic==2.10.4",
        "httpx==0.28.1",
        "modal",
        "PyJWT==2.10.1",
        "cryptography==44.0.0",
    )
    .add_local_file("jwks_auth.py", "/root/jwks_auth.py", copy=True)
    .add_local_file("supabase_rest.py", "/root/supabase_rest.py", copy=True)
    .add_local_file("registry.py", "/root/registry.py", copy=True)
    .add_local_file("jobs.py", "/root/jobs.py", copy=True)
    .add_local_dir("adapters", "/root/adapters", copy=True)
)
```

Delete the old assignment entirely — do not leave a second `api_image = ...` anywhere in the file, or whichever runs last wins. Nothing else changes: no decorators, secrets, app names, registry logic, Flux graph, or V5.

## Pre-deploy check

```bash
cd ~/Desktop/modal-project/phase1-v6-staging
grep -c "^api_image = " api.py          # must print 1
grep -c "add_local_file\|add_local_dir" api.py   # must print 5
source ../venv/bin/activate
rm -rf __pycache__ adapters/__pycache__ ../__pycache__
python -c "import api; print('V6 import graph OK')"
```

## Deploy

```bash
modal deploy api.py
```

The build output must now show the four `add_local_file` copies and the `adapters` directory layer, not just the automatic `api.py` mount.

## Optional hardening

Add a `modules_present` object to the `/health` payload from `os.path.exists("/root/jwks_auth.py")` (plus the other three) and `os.path.isdir("/root/adapters")`. One curl then verifies packaging on every future deploy instead of waiting for a crash trace.

## Verification

```bash
curl --fail-with-body --max-time 30 \
  https://brandverita--brandverita-api-v6-fastapi-app.modal.run/health
```

Expect `version: v6`, `app_name: brandverita-api-v6`, `worker_app: comfyui-generation-worker-v6`, and no fresh `ModuleNotFoundError` in the Modal logs.

Then confirm V5 is untouched:

```bash
curl --fail-with-body --max-time 30 \
  https://brandverita--brandverita-api-fastapi-app.modal.run/health
```

After that: contract checks (unknown workflow → 400, `outpaint:v1` → 403, stub providers → 403, unauthenticated `GET /v1/workflows` → empty/401), then one authenticated end-to-end generation confirming the job row records `provider`, `workflow_version`, `workflow_config_hash`, and `worker_version`.

## Scope and rollback

Only `brandverita-api-v6` changes. The V5 API and `comfyui-generation-worker-v6` stay as deployed, and Image Lab remains on the V5 `VITE_GENERATION_API_URL` until every check passes.
