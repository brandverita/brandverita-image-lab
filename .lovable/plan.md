# WP0 remaining edits — registry.py, jobs.py, and Modal env-var verification

api.py is done (swapped). Three items remain before redeploy + the 28-check suite.

## 1. `registry.py` — Studio-safe filter (README §4)

Two edits, both in `modal-project/phase1-v6-staging/registry.py`:

**a) Expose the new WP0 columns.** Wherever registry rows are serialized for the API (the row→dict mapping used by lookup/list), include the new fields so `api.py` and `advanced.py` can read them:

```python
"requires_source_asset": row.get("requires_source_asset", False),
"allowed_output_presets": row.get("allowed_output_presets"),
"input_envelope": row.get("input_envelope"),
"artifact_pins": row.get("artifact_pins"),
"candidate_id": row.get("candidate_id"),
"candidate_notes": row.get("candidate_notes"),
```

Also make sure the pre-existing gate fields are exposed if they aren't already: `status`, `commercial_status`, `registry_visibility`, `production_enabled`, `enabled_for_studio`, `allowed_envs`.

**b) Apply the Studio-safe filter to any Studio-shaped registry read** (list endpoints / anything a browser can enumerate):

```python
import advanced
rows = [r for r in rows if advanced.studio_safe_row(r)]
```

`advanced.studio_safe_row` keeps only rows with `registry_visibility='studio_safe'`, non-`research_only` commercial status, `production_enabled=true`, `enabled_for_studio=true`. Server-internal lookups (dispatch path in api.py) must NOT use this filter — advanced candidates must remain resolvable server-side so the flag/allow-list gates can reject them with the right error.

## 2. `jobs.py` — lineage echo (README §3)

In `job_to_response_dict` (the function that serializes a `generation_jobs` row for `GET /v1/generations/{job_id}`), add:

```python
"source_asset_id": job.get("source_asset_id"),
"output_asset_id": job.get("output_asset_id"),
"output_preset": job.get("output_preset"),
"request_params": job.get("request_params") or {},
```

No other change: Flux jobs return nulls/empty dict for these, which the extended `JobResponse` in api.py already accepts.

## 3. Confirm the five `*_ENABLED=false` env vars on the Modal V6 app

These are plain environment variables on the **API app only** (`brandverita-api-v6`), not the worker, and not Modal Secrets (they are non-sensitive kill-switches; flags must be readable via `os.environ` inside the handler, which is how `advanced._flag` reads them).

**Check current state (read-only):**

```bash
modal app list | grep brandverita-api-v6
```

Dashboard route: Modal dashboard → Apps → `brandverita-api-v6` → check the app's environment/config. Note: values set via the dashboard or `modal deploy` config persist; ad-hoc `modal run --env` does not.

**If not set, add them to the deployed app.** Since api.py builds the Modal app in code, the cleanest deterministic way is to define them in code, next to the image definition:

```python
app = modal.App(
    "brandverita-api-v6",
    secrets=[...existing...],
    # WP0 kill-switch flags — plain env, NOT secrets
)
```

then on the web endpoint function:

```python
@app.function(image=api_image, secrets=[...])
@modal.fastapi_endpoint(...)
def fastapi_app():
    ...
```

Set the env inside the container via the image:

```python
api_image = (
    modal.Image.debian_slim(python_version="3.11")
    .env({
        "ADVANCED_WORKFLOWS_ENABLED": "false",
        "OUTPAINT_EVAL_ENABLED": "false",
        "PRODUCT_SCENE_EVAL_ENABLED": "false",
        "PROVIDER_BFL_ENABLED": "false",
        "PROVIDER_REPLICATE_ENABLED": "false",
    })
    .pip_install(...)  # existing pins unchanged
    ...
)
```

Putting them in the image guarantees `advanced._flag()` reads `false` even if dashboard config is forgotten, and keeps every deploy reproducible. WP1/WP2 flip individual flags to `true` via a deliberate code change + redeploy — which matches the per-phase approval model.

**Confirm after deploy:**

```bash
curl -s https://brandverita--brandverita-api-v6-fastapi-app.modal.run/health
```

Expect `"advanced_framework": true`. The flags themselves are never echoed (by design), so behavioral confirmation comes from the test suite: checks that hit an advanced workflow must get 403 `advanced_workflows_disabled` — that response proves `ADVANCED_WORKFLOWS_ENABLED=false` is live in the container.

## 4. Final sequence

1. Apply edits 1–3 in `modal-project/phase1-v6-staging/`.
2. `rm -rf __pycache__` then `python -c "import api, registry, jobs, advanced"` — expect no output/errors.
3. `modal deploy api.py` (V6 API app only; worker and V5 untouched).
4. `/health` check above.
5. Run `backend/phase2b/tests/test_wp0_framework.py` with `V6`, `TOK_A`, `TOK_B`, `SUPABASE_URL` — paste the 28-check output; then I write the WP0 build manifest.

## Rollback

All edits additive. `jobs.py`/`registry.py` changes return extra null fields only. Flags default false, making every advanced path unreachable. Rollback = redeploy previous revision.
