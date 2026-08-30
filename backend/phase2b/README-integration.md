# Phase 2B WP0 — V6 API integration (staging only)

Copy `advanced.py` into `modal-project/phase1-v6-staging/`, then make the
edits below. The worker is **not** touched. V5 is **not** touched. No
candidate row is created — every advanced request resolves to a gate failure,
which the negative test suite asserts.

Prerequisite: the WP0 additive migration has been applied
(registry columns, job lineage columns, `transformation_eval_runs`).

## 1. Add `advanced.py` to the API image

```python
api_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        # ... existing pins ... (pillow already present since Phase 2A)
    )
    .add_local_file("jwks_auth.py", "/root/jwks_auth.py", copy=True)
    .add_local_file("supabase_rest.py", "/root/supabase_rest.py", copy=True)
    .add_local_file("registry.py", "/root/registry.py", copy=True)
    .add_local_file("jobs.py", "/root/jobs.py", copy=True)
    .add_local_file("assets.py", "/root/assets.py", copy=True)
    .add_local_file("usage.py", "/root/usage.py", copy=True)
    .add_local_file("advanced.py", "/root/advanced.py", copy=True)   # NEW
    .add_local_dir("adapters", "/root/adapters", copy=True)
)
```

Same rule as Phase 2A: if the file is not added, the container crash-loops
with `ModuleNotFoundError`.

## 2. `POST /v1/generations` extension

Accept three optional body fields **in addition to the existing ones**:

```
source_asset_id : uuid (optional — required only when the resolved registry
                  row has requires_source_asset = true)
output_preset   : string (optional)
params          : object (optional; validated strictly, enums only)
```

Add this at the top of the handler, after JWKS auth and allow-list checks and
before any dispatch:

```python
import advanced

# ... existing auth + workflow-key resolution ...

registry_row = registry.lookup(workflow_id, workflow_version)  # existing call

if registry_row.get("requires_source_asset"):
    resolved = advanced.resolve_advanced_request(
        workflow_key=workflow_id,
        workflow_version=workflow_version,
        source_asset_id=body.source_asset_id,
        output_preset=body.output_preset,
        params=body.params or {},
        user_id=user_id,
        environment="staging",
    )
    # No candidate exists in WP0: dispatch always stops here because no
    # 'testing'/'research_only' row is reachable. When WP1/WP2 add rows,
    # resolved["request_params"] / ["output_preset"] / ["asset"] feed the job.
else:
    # Flux and other non-asset workflows: an asset must never be attached.
    if body.source_asset_id:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "invalid_request",
                    "error_message": "This workflow does not accept a source asset."},
        )
```

Job insert: persist `source_asset_id`, `output_preset`, and
`request_params` (the **validated** dict, never the raw body) alongside the
existing fields. Leave `output_asset_id` null until dispatch completes.

Keep the existing Phase 2B deferred-usage comment next to the insert; the
usage ledger stays unwired in WP0 — cost data lives in
`transformation_eval_runs` (written via `advanced.write_eval_run` at dispatch
and completion, starting in WP1/WP2).

## 3. `GET /v1/generations/{job_id}` extension

Add to the response (values from the job row):

```python
"source_asset_id": job.get("source_asset_id"),
"output_asset_id": job.get("output_asset_id"),
"output_preset": job.get("output_preset"),
"request_params": job.get("request_params") or {},
```

Signed output read URL: only when the caller owns the job, the output asset
is `ready`, TTL 5 minutes, via the existing `assets.storage_signed_read_url`.
Never return: provider keys, provider input authorization, graph JSON, model
paths, internal prompts, source signed URLs, raw provider errors.

## 4. Studio-safe registry filter (`registry.py`)

Any Studio-shaped registry read filters rows at the API layer:

```python
rows = [r for r in rows if advanced.studio_safe_row(r)]
```

(i.e. keep only `registry_visibility='studio_safe'`, non-`research_only`,
`production_enabled=true`, `enabled_for_studio=true`.)

## 5. Flags (Modal env / secrets — plain env vars, NOT secrets store)

Define on the V6 API app only, all defaulting to false:

```
ADVANCED_WORKFLOWS_ENABLED=false
OUTPAINT_EVAL_ENABLED=false
PRODUCT_SCENE_EVAL_ENABLED=false
PROVIDER_BFL_ENABLED=false        # flag exists; nothing behind it in WP0
PROVIDER_REPLICATE_ENABLED=false  # flag exists; nothing behind it in WP0
```

Flags are read inside the request handler (`advanced._flag`), never at module
scope, and their state is never echoed to the browser.

## 6. Health marker

```python
return {
    ...,
    "version": "v6",
    "assets": True,
    "advanced_framework": True,   # NEW
}
```

## 7. Deploy

```bash
cd modal-project/phase1-v6-staging
python -c "import api"            # local import check
modal deploy api.py               # brandverita-api-v6 only
curl -s https://brandverita--brandverita-api-v6-fastapi-app.modal.run/health
```

Expect `"version":"v6"`, `"assets":true`, `"advanced_framework":true`.
The worker app `comfyui-generation-worker-v6` is untouched; V5 remains the
rollback target.

## 8. Acceptance

Run `backend/phase2b/tests/test_wp0_framework.py` (28 checks) with `V6`,
`TOK_A`, `TOK_B`, `SUPABASE_URL` set — see the file header.
