# Fix: ModuleNotFoundError: No module named 'jwt' on `modal deploy api.py`

## Root cause (confirmed)
The error is **local**, not in the Modal container. `modal deploy api.py` imports `api.py` in your local Python (on the Mac) to build the app graph *before* it builds the remote image. `api.py` top-level-imports `jwks_auth`, which imports `jwt`. The `jwt` module is provided by the **PyJWT** PyPI package. Your local venv (`modal-project/venv`) does not have PyJWT installed, so the local import fails and the deploy aborts.

The remote `api_image` is already correct — it pip-installs `PyJWT==2.10.1` and `cryptography==44.0.0`. The image definition block you pasted confirms this. No change to `api.py` or the image is needed.

## The fix — install the runtime deps in the local venv
`modal deploy` must be able to import every module reachable from `api.py` in the local Python. Install the same set of importable third-party packages locally that the API graph pulls in:

```bash
cd modal-project
source venv/bin/activate
pip install PyJWT==2.10.1 cryptography==44.0.0
```

Notes:
- Install **PyJWT** (case-insensitive; `pyjwt` works too). Do NOT install the bare `jwt` package — it is a different, unmaintained library that shadows the correct one.
- If `modal deploy` then fails on the next import (e.g. `httpx`, `pydantic`), install those locally too (`pip install httpx pydantic`). The goal is: every top-level `import` reachable from `api.py` resolves in the local venv. `modal`, `fastapi`, `uvicorn`, `pydantic`, `httpx`, `PyJWT`, `cryptography` are the full set per the image block. `supabase-py` is deliberately NOT used (the comment in api.py says httpx only), so it is not required.
- `modal` itself is already installed locally (the CLI ran), but the `modal` Python package used inside `api.py` for `modal.Cls.from_name` may be a separate import — if `import modal` fails locally, `pip install modal` in the venv.

## Redeploy
```bash
cd modal-project/phase1-v6-staging
rm -rf __pycache__ ../__pycache__
modal deploy api.py
```

## Verify
1. `curl https://brandverita--brandverita-api-v6-fastapi-app.modal.run/health`
   → expect `version: v6`, `app_name: brandverita-api-v6`, `worker_app: comfyui-generation-worker-v6`.
2. `curl https://brandverita--brandverita-api-fastapi-app.modal.run/health`
   → still `v5`, proving V5 intact.
3. One end-to-end generation against the V6 URL → confirm the job row carries `provider`, `workflow_version`, `workflow_config_hash`, `worker_version`.
4. Contract checks: unknown workflow → 400, `outpaint:v1` → 403, stub providers → 403, unauthenticated `GET /v1/workflows` → empty/401.

## Rollback
No V5 change is involved. If the redeployed V6 API misbehaves, leave `VITE_GENERATION_API_URL` pointed at V5; optionally `modal app stop brandverita-api-v6`.
