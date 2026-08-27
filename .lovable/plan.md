# Fix: ModuleNotFoundError: No module named 'jwt' on `modal deploy api.py`

## Root cause (confirmed)
`phase1-v6-staging/jwks_auth.py` line 19 runs `import jwt`. The `jwt` namespace is provided by the **PyJWT** package on PyPI (not the unrelated legacy `jwt` package). The Modal image that backs the V6 API app does not pip-install PyJWT, so container startup fails at import time — before the server even binds. This is a missing build dependency, not a code bug.

## The one-line fix
Add `PyJWT` to the pip-install list of the API app's Modal image in `phase1-v6-staging/api.py`.

In `api.py` there is an image definition of the form:

```python
image = modal.Image.debian_slim().pip_install(
    "fastapi",
    "httpx",
    ...   # other deps
)
```

Add `"PyJWT"` to that list. If the file pins versions (e.g. `"httpx==0.27.2"`), pin consistently, e.g. `"PyJWT==2.9.0"`. PyJWT 2.x is required because `jwks_auth.py` uses JWKS/JWKClient APIs only present in 2.x.

```python
image = modal.Image.debian_slim().pip_install(
    "fastapi",
    "httpx",
    "PyJWT==2.9.0",
    ...   # rest unchanged
)
```

Notes:
- Install `PyJWT` (case-insensitive on PyPI; `pyjwt` also works). Do **not** install the bare `jwt` package — it is a different, unmaintained library and will shadow the correct one.
- If `api.py` reuses the worker image (`modal_worker_v2.py`'s image) instead of defining its own, add `PyJWT` to whichever image object the API `@app.function(image=...)` actually references. The worker image also lacks PyJWT, so the same addition applies there. Either way the package must end up in the image the API function runs in.
- No change to `jwks_auth.py`, `jobs.py`, `registry.py`, `supabase_rest.py`, or the adapters. The import is correct; only the image dependency list is incomplete.

## Deploy
```bash
cd modal-project/phase1-v6-staging
rm -rf __pycache__ ../__pycache__
modal deploy api.py
```
The image rebuilds (small layer addition; Flux model layers are cached and won't re-download since this is the API image, not the worker image).

## Verify
1. `curl https://brandverita--brandverita-api-v6-fastapi-app.modal.run/health`
   → expect `version: v6`, `app_name: brandverita-api-v6`, `worker_app: comfyui-generation-worker-v6`.
2. `curl https://brandverita--brandverita-api-fastapi-app.modal.run/health`
   → still `v5`, proving V5 intact.
3. One end-to-end generation against the V6 URL → confirm the job row carries `provider`, `workflow_version`, `workflow_config_hash`, `worker_version`.
4. Contract checks: unknown workflow → 400, `outpaint:v1` → 403, stub providers → 403, unauthenticated `GET /v1/workflows` → empty/401.

## Rollback
No V5 change is involved. If the redeployed V6 API still fails, leave `VITE_GENERATION_API_URL` pointed at V5; optionally `modal app stop brandverita-api-v6`.

## Confirmation needed
Paste the `image = modal.Image...` block from your `api.py` (and confirm whether the API references its own image or the worker's) so the exact edit can be applied verbatim. The fix above is correct for either case.
