# V6 API still crash-looping on `No module named 'jwks_auth'`

## What the evidence shows

- The `api_image` definition you pasted is correct: it copies `jwks_auth.py`, `supabase_rest.py`, `registry.py`, `jobs.py`, and `adapters/` into `/root` at build time with `copy=True`.
- The container traceback still fails at `/root/api.py` line 58 `import jwks_auth`, and the interpreter is `/usr/local/lib/python3.11/...`.

Those two facts together mean the running container is almost certainly **not** using `api_image`. The most likely cause is that the web endpoint's decorator does not pass `image=api_image` (Modal then runs it on a default/other image, which has none of the copied files). A second possibility is that the deploy served a cached older revision. This diagnosis is unconfirmed until the decorator is read, so verification is step 1.

## Step 1 — Confirm which image the endpoint uses

In `phase1-v6-staging/api.py`, look at the decorator block directly above the ASGI entrypoint (the function wrapped with `@modal.asgi_app()`), and check whether `image=api_image` is present:

```bash
cd ~/Desktop/modal-project/phase1-v6-staging
grep -n "asgi_app\|@app.function\|@app.cls\|image=\|secrets=\|def fastapi_app" api.py
```

Send me that output. Expected correct form:

```python
@app.function(image=api_image, secrets=[...], timeout=..., min_containers=...)
@modal.asgi_app()
def fastapi_app():
    ...
```

## Step 2 — Fix, based on what step 1 shows

Case A — `image=api_image` is missing or names a different image:
add `image=api_image` to that `@app.function(...)` decorator, leaving every other argument (secrets, timeout, scaling, concurrency) untouched. This is the whole fix; no other file changes.

Case B — `image=api_image` is already there:
then the copy step is not taking effect for this revision. Force a clean rebuild and confirm from the deploy output that the files are added:

```bash
cd ~/Desktop/modal-project/phase1-v6-staging
rm -rf __pycache__ adapters/__pycache__ ../__pycache__
modal deploy --force-build api.py
```

The build log must show layer steps for the four `add_local_file` copies and the `adapters` directory. If it shows only `api.py`, send me the full build output before anything else changes.

Also confirm the files exist where Modal looks for them (relative to the deploy directory):

```bash
ls -1 jwks_auth.py supabase_rest.py registry.py jobs.py adapters/__init__.py adapters/base.py adapters/modal_comfyui.py adapters/replicate.py adapters/bfl_api.py
```

## Step 3 — Prove the image contents inside the container

Rather than guessing again, verify directly. Add a temporary read-only diagnostic to the top of `fastapi_app`'s module import path — or simpler, hit a health field: extend `/health` with a `modules_present` list built from `os.path.exists("/root/jwks_auth.py")` and `os.path.isdir("/root/adapters")`. That makes the packaging state observable from a single curl on every future deploy, instead of only via a crash trace.

## Verification

```bash
curl --fail-with-body --max-time 30 \
  https://brandverita--brandverita-api-v6-fastapi-app.modal.run/health
```

Expect `version: v6`, `app_name: brandverita-api-v6`, `worker_app: comfyui-generation-worker-v6`, and no `ModuleNotFoundError` in the Modal logs.

Then confirm V5 is untouched:

```bash
curl --fail-with-body --max-time 30 \
  https://brandverita--brandverita-api-fastapi-app.modal.run/health
```

After that: contract checks (unknown workflow → 400, `outpaint:v1` → 403, stub providers → 403, unauthenticated `GET /v1/workflows` → empty/401) and one authenticated end-to-end generation, confirming the job row records `provider`, `workflow_version`, `workflow_config_hash`, `worker_version`.

## Scope and rollback

Only `brandverita-api-v6` changes. V5 API and `comfyui-generation-worker-v6` are untouched, and Image Lab stays on the V5 `VITE_GENERATION_API_URL` until all checks pass.
