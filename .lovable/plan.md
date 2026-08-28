# Fix: ModuleNotFoundError / pydantic-core build failure on `modal deploy api.py`

## Root cause (confirmed)
Two facts together:
1. `modal deploy api.py` imports `api.py` in the **local** Python (on the Mac) to build the app graph before building the remote image. Every top-level third-party import reachable from `api.py` (`jwks_auth` → `jwt`, plus `httpx`, `pydantic`, `fastapi`, `uvicorn`, `modal`) must resolve in the local venv.
2. The current local venv (`modal-project/venv`) was created with **Python 3.14**. The pinned `pydantic==2.10.4` pulls `pydantic-core==2.27.2`, which has no prebuilt wheel for Python 3.14, so pip tries to compile it from Rust via maturin/PyO3 0.22.6 — and PyO3 0.22.6 rejects Python 3.14 (max supported: 3.13). Hence `Failed building wheel for pydantic-core`.

The remote `api_image` is already correct — it is pinned to `python_version="3.11"` and pip-installs `PyJWT==2.10.1`, `cryptography==44.0.0`, `httpx`, `pydantic==2.10.4`, `fastapi`, `uvicorn`, `modal`. No change to `api.py` or the image is needed.

## The fix — recreate the local venv with Python 3.10
Recreate the local venv on Python 3.10, which has prebuilt wheels for every package in the pinned set (no Rust compilation):

```bash
cd ~/Desktop/modal-project
rm -rf venv
"$(brew --prefix python@3.10)/bin/python3.10" -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install PyJWT==2.10.1 cryptography==44.0.0 httpx==0.28.1 pydantic==2.10.4 fastapi==0.115.6 uvicorn==0.34.0 modal
```

Why this is safe:
- The local venv is used **only** to build the app graph and drive the Modal CLI. It has no effect on the remote container, which stays on Python 3.11 via the pinned `api_image`.
- Python 3.10 also matches `modal_worker_v2.py`'s environment expectations for local imports.
- Install the **full set at once** to avoid a whack-a-mole of `ModuleNotFoundError` on each successive import.

Notes:
- Install **PyJWT** (case-insensitive; `pyjwt` works too). Do NOT install the bare `jwt` package — it is a different, unmaintained library that shadows the correct one.
- `supabase-py` is deliberately NOT used (httpx only, per the comment in api.py), so do not install it.
- Prerequisite: `python@3.10` must be installed via Homebrew (`brew install python@3.10`) if `"$(brew --prefix python@3.10)"` does not resolve.
- Alternative (not chosen): keep Python 3.14 and bump to `pydantic>=2.11` (which ships 3.14 wheels). Rejected because the local pins should match the remote image pins exactly, eliminating any version-drift surprises.

## Redeploy
```bash
cd ~/Desktop/modal-project/phase1-v6-staging
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
