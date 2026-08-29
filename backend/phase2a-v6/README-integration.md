# Phase 2A — V6 API integration (staging only)

Copy `assets.py` and `usage.py` into `modal-project/phase1-v6-staging/`, then make
three small edits to `api.py`. The worker is **not** touched. V5 is **not** touched.

## 1. Add Pillow to the API image

```python
api_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        # ... existing pins ...
        "pillow==11.0.0",
    )
    .add_local_file("jwks_auth.py", "/root/jwks_auth.py", copy=True)
    .add_local_file("supabase_rest.py", "/root/supabase_rest.py", copy=True)
    .add_local_file("registry.py", "/root/registry.py", copy=True)
    .add_local_file("jobs.py", "/root/jobs.py", copy=True)
    .add_local_file("assets.py", "/root/assets.py", copy=True)   # NEW
    .add_local_file("usage.py", "/root/usage.py", copy=True)     # NEW
    .add_local_dir("adapters", "/root/adapters", copy=True)
)
```

Both new files **must** be added to the image, or the container will crash-loop with
`ModuleNotFoundError` exactly as it did during the Phase 1 packaging incident.

## 2. Mount the router

Inside the function that builds the FastAPI app, after the existing routes:

```python
from assets import build_assets_router

# `require_user_id` is the existing JWKS dependency that returns the verified
# `sub` claim and raises 401 on a missing/invalid token. Pass it in unchanged.
app.include_router(build_assets_router(require_user_id))
```

If the existing dependency returns a claims dict instead of a string, wrap it:

```python
def _current_user_id(claims: dict = Depends(verify_bearer_token)) -> str:
    return claims["sub"]

app.include_router(build_assets_router(_current_user_id))
```

## 3. Health marker

```python
return {
    ...,
    "assets": True,
    "assets_bucket": "generation-assets",
}
```

## 4. Deferred usage-ledger integration point

Add this comment next to the `generation_jobs` insert in `api.py` — **do not call it
in Phase 2A**:

```python
# PHASE 2B INTEGRATION POINT: informational usage reservation.
# from usage import reserve_usage, settle_usage, void_usage
# Requires atomic job-insert + reservation (and void on dispatch failure)
# before it can be enabled. No credits are ever deducted.
```

## 5. Deploy

```bash
cd modal-project/phase1-v6-staging
python -c "import api"            # local import check
modal deploy api.py               # brandverita-api-v6 only
curl -s https://brandverita--brandverita-api-v6-fastapi-app.modal.run/health
```

Expect `"version":"v6"`, `"assets":true`. The worker app
`comfyui-generation-worker-v6` is untouched, and V5 remains the rollback target.

## Server-authoritative limits implemented in `assets.py`

| Rule | Value |
| --- | --- |
| Allowed types | `image/png`, `image/jpeg`, `image/webp` only |
| Rejected types | SVG, GIF, TIFF, HEIC, PDF, AVIF, BMP, ICO, anything else |
| Max file size | 10 MB (10485760 bytes) |
| Max width / height | 4096 px each |
| Max pixels | 16,777,216 |
| Animated / multi-frame | rejected (animated WebP, APNG) |
| Decompression bombs | Pillow warning escalated to a validation error |
| Checks performed | magic bytes, decoded format vs declared MIME, dimensions, pixel count, real size, SHA256 |
| Pending asset TTL | 30 minutes |
| Ready asset TTL | 30 days |
| Signed upload URL TTL | 30 minutes, one exact object path |
| Signed read URL TTL | 5 minutes, issued only after ownership check |

No cleanup scheduler in this phase — expiry is recorded, enforcement is Phase 2B.
