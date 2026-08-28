# V6 API still crash-looping on `No module named 'jwks_auth'`

## What the evidence shows

- The `api_image` definition you pasted copies `jwks_auth.py`, `supabase_rest.py`, `registry.py`, `jobs.py`, and `adapters/` into `/root` at build time with `copy=True`.
- `grep` confirms the endpoint does use it: `@app.function(image=api_image, secrets=[supabase_secret])` at line 517, directly above `@modal.asgi_app()` / `def fastapi_app()`; line 257 uses the same image.
- The container still fails at `/root/api.py` line 58 `import jwks_auth`.

The decorator is therefore correct, and the copy layers simply were not in the image that ran. Two candidates remain, in order of likelihood: (a) a second, later `api_image = ...` assignment in `api.py` overriding the good one, so the name bound at line 517 has no copy layers; (b) the deploy reused a cached image built before the copy layers were added. Both are cheap to rule out.

## Step 1 — Rule out a duplicate `api_image`, and confirm the files are where Modal looks

```bash
cd ~/Desktop/modal-project/phase1-v6-staging
grep -n "api_image" api.py
grep -n "add_local_file\|add_local_dir" api.py
ls -1 jwks_auth.py supabase_rest.py registry.py jobs.py adapters/__init__.py adapters/base.py adapters/modal_comfyui.py adapters/replicate.py adapters/bfl_api.py
```

Expect exactly one `api_image = (` assignment, five `add_local_*` lines, and all nine files present. If a later `api_image = ...` exists, delete it (or merge its layers into the single canonical definition) — that alone is the fix.

## Step 2 — Force a clean rebuild

```bash
cd ~/Desktop/modal-project/phase1-v6-staging
rm -rf __pycache__ adapters/__pycache__ ../__pycache__
modal deploy --force-build api.py
```

The build log must show layer steps for the four `add_local_file` copies and the `adapters` directory. If it shows only the automatic `api.py` mount, stop and send me the full build output before changing anything else.

## Step 3 — Make packaging observable instead of crash-only

Extend the `/health` payload with a `modules_present` object built from `os.path.exists("/root/jwks_auth.py")`, the other three module paths, and `os.path.isdir("/root/adapters")`. One curl then confirms packaging on every future deploy, rather than waiting for a crash trace. Read-only additive field; no behaviour change.

## Verification

```bash
curl --fail-with-body --max-time 30 \
  https://brandverita--brandverita-api-v6-fastapi-app.modal.run/health
```

Expect `version: v6`, `app_name: brandverita-api-v6`, `worker_app: comfyui-generation-worker-v6`, all `modules_present` true, and no `ModuleNotFoundError` in the Modal logs.

Then confirm V5 is untouched:

```bash
curl --fail-with-body --max-time 30 \
  https://brandverita--brandverita-api-fastapi-app.modal.run/health
```

After that: contract checks (unknown workflow → 400, `outpaint:v1` → 403, stub providers → 403, unauthenticated `GET /v1/workflows` → empty/401) and one authenticated end-to-end generation, confirming the job row records `provider`, `workflow_version`, `workflow_config_hash`, `worker_version`.

## Scope and rollback

Only `brandverita-api-v6` changes. The V5 API and `comfyui-generation-worker-v6` are untouched, and Image Lab stays on the V5 `VITE_GENERATION_API_URL` until all checks pass.
