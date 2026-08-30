"""
BrandVerita Generation API (Modal + FastAPI) — v6.

Phase 1 modularization. This file is now a THIN ENTRY POINT: Modal app
definition, web routes, request parsing, and dispatch. All logic lives in:

    supabase_rest.py          — Supabase REST helpers (httpx only)
    jwks_auth.py              — ES256 JWKS token verification (comfy-ui issuer)
    registry.py               — workflow registry: gates, hashing, safe views
    jobs.py                   — job state machine + background orchestration
    assets.py                 — Phase 2A: private generation-asset lifecycle
    advanced.py               — Phase 2B WP0: shared Image Transformation
                                Framework v1 (param parsing, asset gates,
                                eval-run writer). No candidate dispatch in WP0.
    adapters/modal_comfyui.py — Flux graph (verbatim from v5) + worker dispatch
    adapters/replicate.py     — Phase 2 stub, refuses dispatch
    adapters/bfl_api.py       — interface-only stub, refuses dispatch

Deploy the whole folder (all sibling modules are bundled automatically):

    modal deploy api.py

WHAT V6 ADDS
------------
- Workflow registry: dispatch is resolved and gated through
  public.workflow_definitions (status, allowed_envs, commercial_status,
  allowed_dimensions, input_schema). Unknown workflow -> 400
  unsupported_workflow; inactive/non-approved -> 403 workflow_unavailable /
  workflow_not_commercially_approved.
- Backward compatibility: the legacy request shape (flat fields, workflow_id
  "flux-schnell-txt2img-v1") maps to registry key flux_text_to_image:v1 and
  behaves exactly as v5. The new structured shape ({workflow_id,
  workflow_version, inputs}) is also accepted.
- Jobs are stamped with workflow_version, provider, provider_model,
  workflow_config_hash, worker_version, queued_at/started_at.
- Job state machine gains dispatching / uploading_output (failed jobs also
  carry error_category + internal_error_ref).
- Identity: ES256 access tokens are verified locally against the comfy-ui
  JWKS; any failure falls back to the v5 Supabase Auth REST check.
- GET /v1/workflows: safe, server-filtered registry view (no raw graphs,
  provider references, model paths, or deployment internals).
- Phase 2B WP0: POST /v1/generations accepts source_asset_id / output_preset /
  params ONLY for registry rows with requires_source_asset=true. Every such
  request is gated through advanced.resolve_advanced_request (flags, allow-
  list, asset ownership/readiness/expiry, strict enum params). No candidate
  exists in WP0, so advanced dispatch always stops at a gate failure; the
  Flux text-to-image path is byte-equivalent to Phase 2A.
- Job lineage: source_asset_id, output_preset, request_params are persisted
  on the job row and echoed by GET /v1/generations/{job_id}.

Behavior preserved from v5: CORS error handling, idempotency replay, signed
result URLs, dispatch failure marking the job failed with a 503.

Requires the Modal secret `brandverita-supabase-comfy-ui` containing:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import modal
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

import advanced
import assets
import jwks_auth
import jobs
import registry
import supabase_rest
from adapters import bfl_api, modal_comfyui, replicate

APP_NAME = os.environ.get("MODAL_APP_NAME", "brandverita-api-v6")
app = modal.App(APP_NAME)

supabase_secret = modal.Secret.from_name("brandverita-supabase-comfy-ui")

# httpx only — no supabase-py, so nothing here can fail at import/construction time.
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
        "pillow==11.0.0",
    )
    .add_local_file("jwks_auth.py", "/root/jwks_auth.py", copy=True)
    .add_local_file("supabase_rest.py", "/root/supabase_rest.py", copy=True)
    .add_local_file("registry.py", "/root/registry.py", copy=True)
    .add_local_file("jobs.py", "/root/jobs.py", copy=True)
    .add_local_file("assets.py", "/root/assets.py", copy=True)
    .add_local_file("usage.py", "/root/usage.py", copy=True)
    .add_local_file("advanced.py", "/root/advanced.py", copy=True)
    .add_local_dir("adapters", "/root/adapters", copy=True)
)


ALLOWED_ORIGINS = [
    "https://brandverita-image-lab.netlify.app",
    "https://lab.brandverita.com",
    "http://localhost:8080",
]

API_VERSION = "v6"

ADAPTERS = {
    "modal_comfyui": modal_comfyui,
    "replicate": replicate,
    "bfl_api": bfl_api,
}

web_app = FastAPI(title="BrandVerita Generation API")

web_app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


def _cors_headers(request: Request) -> dict:
    """CORS headers for hand-built error responses.

    Starlette's CORSMiddleware cannot decorate a response produced by an
    unhandled exception, which is exactly how the browser lost the real status
    before. Errors below therefore carry the headers themselves.
    """
    origin = request.headers.get("origin")
    if origin in ALLOWED_ORIGINS:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }
    return {}


@web_app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_message": str(exc.detail)},
        headers=_cors_headers(request),
    )


@web_app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Log the type only — never prompts, tokens, or payloads.
    print(f"unhandled_error path={request.url.path} type={type(exc).__name__}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "internal_error",
            "error_code": "internal_error",
            "error_message": "Service temporarily unavailable. Please retry in a moment.",
        },
        headers=_cors_headers(request),
    )


class GenerationInputs(BaseModel):
    """Normalized workflow inputs — identical limits for legacy and structured
    request shapes; the registry's input_schema is enforced on top."""

    prompt: str = Field(min_length=1, max_length=2000)
    negative_prompt: str = Field(default="", max_length=1000)
    width: int = 1024
    height: int = 1024
    seed: Optional[int] = None
    idempotency_key: str = Field(min_length=1, max_length=200)


class JobResponse(BaseModel):
    job_id: str
    status: str
    workflow_id: str
    workflow_version: Optional[str] = None
    provider: Optional[str] = None
    provider_model: Optional[str] = None
    workflow_config_hash: Optional[str] = None
    progress: Optional[int] = None
    result_url: Optional[str] = None
    output_path: Optional[str] = None
    modal_call_id: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    seed: Optional[int] = None
    queued_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    # Phase 2B WP0 lineage fields (null for Flux text-to-image jobs).
    source_asset_id: Optional[str] = None
    output_asset_id: Optional[str] = None
    output_preset: Optional[str] = None
    request_params: Optional[dict] = None


# ---------------------------------------------------------------------------
# Auth: JWKS first, Supabase Auth REST fallback (v5 behavior)
# ---------------------------------------------------------------------------

def _verify_via_auth_api(token: str, url: str, key: str) -> str:
    import httpx

    try:
        response = httpx.get(
            f"{url}/auth/v1/user",
            headers={"apikey": key, "Authorization": f"Bearer {token}"},
            timeout=15.0,
        )
    except Exception as exc:
        print(f"auth_transport_error type={type(exc).__name__}")
        raise HTTPException(
            status_code=500,
            detail="auth_backend_unavailable: could not reach Supabase auth",
        )

    if response.status_code in (401, 403):
        raise HTTPException(status_code=401, detail="token_invalid: token rejected by Supabase")
    if response.status_code >= 500:
        raise HTTPException(
            status_code=500,
            detail="auth_backend_unavailable: Supabase auth returned an error",
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail=f"auth_backend_unavailable: unexpected auth status {response.status_code}",
        )

    try:
        user_id = response.json().get("id")
    except Exception:
        user_id = None
    if not user_id:
        raise HTTPException(status_code=401, detail="token_invalid: no user for this token")
    return str(user_id)


def get_verified_user_id(authorization: Optional[str] = Header(default=None)) -> str:
    """Resolve the caller's user id, keeping the three failure kinds distinct.

    401 token_missing            — no Authorization: Bearer header arrived.
    401 token_invalid            — the token could not be verified.
    500 auth_backend_unavailable — this service cannot reach or configure Supabase.

    Verification order: local JWKS check against the comfy-ui ES256 issuer
    first; any failure (legacy HS256 tokens, JWKS fetch issues) falls back to
    the Supabase /auth/v1/user check so existing sessions keep working.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="token_missing: no bearer token in request")

    token = authorization[len("Bearer "):].strip()
    if not token:
        raise HTTPException(status_code=401, detail="token_missing: empty bearer token")

    url, key = supabase_rest.supabase_config()

    user_id = jwks_auth.verify_via_jwks(token, url)
    if user_id:
        return user_id
    return _verify_via_auth_api(token, url, key)


# ---------------------------------------------------------------------------
# Background orchestrator (Modal-wrapped; injected into the adapter)
# ---------------------------------------------------------------------------

@app.function(image=api_image, secrets=[supabase_secret], timeout=3600)
def run_generation(
    job_id: str,
    user_id: str,
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    seed: Optional[int],
    provider: str = "modal_comfyui",
) -> None:
    jobs.run_generation(
        job_id=job_id,
        user_id=user_id,
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        seed=seed,
        provider=provider,
    )


modal_comfyui.set_dispatcher(run_generation)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@web_app.get("/health")
def health_check():
    # `version` and `dispatch` make it impossible to be unsure which build is
    # live: a deployed file without worker dispatch cannot report dispatch=True.
    registry_ok = True
    workflow_keys = []
    try:
        workflow_keys = sorted(
            f"{row['key']}:{row['version']}" for row in registry.load_registry()
        )
    except Exception as exc:  # noqa: BLE001
        registry_ok = False
        print(f"health_registry_error type={type(exc).__name__}")

    return {
        "status": "ok",
        "service": "brandverita-api",
        "app_name": APP_NAME,
        "version": API_VERSION,
        "dispatch": True,
        "environment": registry.ENVIRONMENT,
        "registry_ok": registry_ok,
        "workflows": workflow_keys,
        "worker_app": modal_comfyui.WORKER_APP,
        "worker_class": modal_comfyui.WORKER_CLASS,
        "assets": True,
        "assets_bucket": "generation-assets",
        "advanced_framework": True,
    }


@web_app.get("/v1/auth/check")
def auth_check(user_id: str = Depends(get_verified_user_id)):
    """Cheap end-to-end auth probe: 200 means the bearer token verified."""
    return {"authenticated": True, "user_id": user_id}


@web_app.get("/v1/workflows")
def list_workflows(origin: str = "lab", user_id: str = Depends(get_verified_user_id)):
    """Safe, server-filtered registry view for authenticated users.

    origin=lab (default) returns the internal Lab view for this environment.
    origin=studio applies the shared studio-safe predicate plus an
    active-status check, so research_only / internal / not-production-enabled
    rows can never appear. Raw graphs, provider workflow references, model
    file paths, deployment references, and infrastructure internals are never
    returned for either origin.
    """
    resolved_origin = "studio" if str(origin).lower() == "studio" else "lab"
    return {
        "environment": registry.ENVIRONMENT,
        "origin": resolved_origin,
        "workflows": registry.list_visible_workflows(origin=resolved_origin),
    }



@web_app.post("/v1/generations", response_model=JobResponse)
async def start_generation(request: Request, user_id: str = Depends(get_verified_user_id)):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_request: body must be JSON")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="invalid_request: body must be a JSON object")

    # Two shapes, one normalized input set:
    #   legacy     — flat fields, workflow_id "flux-schnell-txt2img-v1" (v5 clients)
    #   structured — {"workflow_id", "workflow_version"?, "inputs": {...}}
    workflow_id = body.get("workflow_id", "flux-schnell-txt2img-v1")
    workflow_version = body.get("workflow_version")
    raw_inputs = body.get("inputs") if isinstance(body.get("inputs"), dict) else body

    row = registry.resolve_workflow(str(workflow_id), workflow_version)
    registry.assert_dispatch_allowed(row, origin="lab")

    # ------------------------------------------------------------------
    # Phase 2B WP0: shared Image Transformation Framework gate.
    # Runs BEFORE GenerationInputs parsing — advanced requests carry
    # source_asset_id / output_preset / params instead of a prompt, and no
    # candidate exists in WP0, so this gate always resolves to a refusal.
    # ------------------------------------------------------------------
    resolved_advanced = None
    if row.get("requires_source_asset"):
        resolved_advanced = advanced.resolve_advanced_request(
            workflow_key=row["key"],
            workflow_version=row["version"],
            source_asset_id=body.get("source_asset_id"),
            output_preset=body.get("output_preset"),
            params=body.get("params") or {},
            user_id=user_id,
            environment=registry.ENVIRONMENT,
        )
    else:
        # Flux and other non-asset workflows: an asset must never be attached.
        if body.get("source_asset_id"):
            raise HTTPException(
                status_code=400,
                detail="invalid_request: This workflow does not accept a source asset.",
            )

    try:
        inputs = GenerationInputs(**raw_inputs)
    except ValidationError as exc:
        first = exc.errors()[0]
        raise HTTPException(status_code=400, detail=f"invalid_request: {first.get('msg', 'invalid inputs')}")

    registry.validate_inputs(row, inputs)

    # Immutability tripwire: the DB trigger blocks edits to activated configs;
    # if a config_hash ever disagrees with a recompute, someone bypassed it.
    if registry.compute_config_hash(row) != row.get("config_hash"):
        print(f"config_hash_mismatch workflow={row.get('key')}:{row.get('version')}")

    existing = supabase_rest.rest_get(
        "generation_jobs",
        {
            "select": "*",
            "user_id": f"eq.{user_id}",
            "idempotency_key": f"eq.{inputs.idempotency_key}",
            "limit": 1,
        },
    )
    if existing:
        # Idempotent replay: return the current state, not a fresh "queued".
        return jobs.job_to_response_dict(existing[0])

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "id": job_id,
        "user_id": user_id,
        "workflow_id": row["key"],
        "workflow_version": row["version"],
        "status": "queued",
        "progress": 0,
        "prompt": inputs.prompt,
        "negative_prompt": inputs.negative_prompt,
        "width": inputs.width,
        "height": inputs.height,
        "seed": inputs.seed,
        "idempotency_key": inputs.idempotency_key,
        "provider": row.get("provider"),
        "provider_model": row.get("provider_model"),
        "workflow_config_hash": row.get("config_hash"),
        "worker_version": row.get("worker_version"),
        "inputs": {
            "prompt": inputs.prompt,
            "negative_prompt": inputs.negative_prompt,
            "width": inputs.width,
            "height": inputs.height,
            "seed": inputs.seed,
        },
        "queued_at": now,
        "created_at": now,
    }
    if resolved_advanced is not None:
        # Persist the VALIDATED values returned by the framework gate, never
        # the raw request body. output_asset_id stays null until dispatch
        # completes (WP1/WP2).
        payload["source_asset_id"] = resolved_advanced.get("source_asset_id")
        payload["output_preset"] = resolved_advanced.get("output_preset")
        payload["request_params"] = resolved_advanced.get("request_params") or {}
    inserted = supabase_rest.rest_insert("generation_jobs", payload)
    if not inserted:
        raise HTTPException(status_code=500, detail="Could not create generation job")

    adapter = ADAPTERS.get(row.get("provider"))
    if adapter is None:
        jobs.patch_job(
            job_id,
            {
                "status": "failed",
                "error_code": "dispatch_failed",
                "error_category": "configuration",
                "error_message": "The image worker could not be started. Please retry.",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        raise HTTPException(
            status_code=503,
            detail="dispatch_failed: no adapter is registered for this workflow's provider.",
        )

    # Hand the job to the provider adapter only after the queued row exists. A
    # dispatch failure must mark the row failed — leaving it queued is exactly
    # what made the frontend poll for five minutes and then time out.
    try:
        provider_ref = adapter.submit_generation(
            {"job_id": job_id, "user_id": user_id},
            {
                "prompt": inputs.prompt,
                "negative_prompt": inputs.negative_prompt,
                "width": inputs.width,
                "height": inputs.height,
                "seed": inputs.seed,
            },
            row,
        )
        jobs.patch_job(
            job_id,
            # A literal fallback keeps NULL meaningful: after this deploy, a NULL
            # modal_call_id can only mean spawn never returned at all.
            {"modal_call_id": provider_ref, "status": "dispatching"},
        )
    except HTTPException:
        jobs.patch_job(
            job_id,
            {
                "status": "failed",
                "error_code": "dispatch_failed",
                "error_category": "configuration",
                "error_message": "The image worker could not be started. Please retry.",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"dispatch_failed job={job_id} type={type(exc).__name__}")
        jobs.patch_job(
            job_id,
            {
                "status": "failed",
                "error_code": "dispatch_failed",
                "error_category": "dispatch",
                "error_message": "The image worker could not be started. Please retry.",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        raise HTTPException(
            status_code=503,
            detail="dispatch_failed: the image worker could not be started. Please retry.",
        )

    return jobs.job_to_response_dict(inserted[0])


@web_app.get("/v1/generations/{job_id}", response_model=JobResponse)
def get_generation(job_id: str, user_id: str = Depends(get_verified_user_id)):
    rows = supabase_rest.rest_get(
        "generation_jobs",
        {"select": "*", "id": f"eq.{job_id}", "user_id": f"eq.{user_id}", "limit": 1},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="This generation job could not be found.")
    return jobs.job_to_response_dict(rows[0])


@web_app.get("/v1/generations/{job_id}/result")
def refresh_result_url(job_id: str, user_id: str = Depends(get_verified_user_id)):
    rows = supabase_rest.rest_get(
        "generation_jobs",
        {
            "select": "id,status,output_path",
            "id": f"eq.{job_id}",
            "user_id": f"eq.{user_id}",
            "limit": 1,
        },
    )
    if not rows:
        raise HTTPException(status_code=404, detail="This generation job could not be found.")

    job = rows[0]
    if job["status"] != "completed" or not job.get("output_path"):
        raise HTTPException(status_code=409, detail="Generation result is not available.")

    signed_url = supabase_rest.sign_output_path(job["output_path"])
    if not signed_url:
        raise HTTPException(status_code=500, detail="Could not create result URL.")
    return {"job_id": job_id, "result_url": signed_url}


# Phase 2A asset routes
web_app.include_router(
    assets.build_assets_router(get_verified_user_id)
)


@app.function(image=api_image, secrets=[supabase_secret])
@modal.asgi_app()
def fastapi_app():
    return web_app
