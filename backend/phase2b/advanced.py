"""
Phase 2B WP0 — shared Image Transformation Framework v1 (STAGING ONLY).

Drop this file next to `api.py` in `modal-project/phase1-v6-staging/` and wire
it per `backend/phase2b/README-integration.md`. It is self-contained: it talks
to Supabase over REST with the service-role key (server-side only) and reuses
`assets.py` for storage access.

WP0 scope: gating, validation, lineage columns and eval-run records ONLY.
There is no candidate row, no adapter behind any provider flag, and no worker
change — every `requires_source_asset` request resolves to a gate failure
(nothing is dispatchable yet), which the negative test suite asserts.

Security invariants:
  * flags are read inside the handler, never at module scope
  * flag state is never echoed to the browser (only opaque error codes)
  * params are validated by a strict allow-list parser: any unknown key or any
    prompt/graph/URL-shaped field is rejected before anything else runs
  * source assets are resolved server-side (owner, kind=input, status=ready,
    not expired, bucket=generation-assets); the browser never receives a
    provider/worker input authorization, and it is never persisted or logged
  * a `ready` output row is written only after bytes are validated, uploaded
    and hashed (also enforced by the generation_assets_ready_chk constraint)
  * provider keys, prompts, graph JSON and signed source URLs are never
    returned in any response body
"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import assets  # sibling module: REST helpers, validation, error mapping

# --------------------------------------------------------------------------- #
# Flags (server-side, default false, read inside the handler)
# --------------------------------------------------------------------------- #


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def advanced_enabled() -> bool:
    return _flag("ADVANCED_WORKFLOWS_ENABLED")


def module_flag(module: str) -> bool:
    if module == "outpaint":
        return _flag("OUTPAINT_EVAL_ENABLED")
    if module == "product_scene":
        return _flag("PRODUCT_SCENE_EVAL_ENABLED")
    return False


def provider_flag(provider: str) -> bool:
    # Flags are defined in WP0; no adapter exists behind them yet.
    if provider == "bfl":
        return _flag("PROVIDER_BFL_ENABLED")
    if provider == "replicate":
        return _flag("PROVIDER_REPLICATE_ENABLED")
    return False


# --------------------------------------------------------------------------- #
# Errors (extend the assets.py mapping without modifying it)
# --------------------------------------------------------------------------- #

_ADVANCED_ERROR_STATUS = {
    "invalid_request": 400,
    "asset_not_found": 404,
    "asset_not_owned": 404,
    "asset_not_ready": 409,
    "asset_expired": 409,
    "workflow_not_available": 403,
    "rate_limited": 429,
    "storage_unavailable": 503,
    "source_integrity_failed": 422,
}


def advanced_error(code: str, message: str) -> Exception:
    from fastapi import HTTPException

    return HTTPException(
        status_code=_ADVANCED_ERROR_STATUS.get(code, 400),
        detail={"error_code": code, "error_message": message},
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Supabase REST (service-role, server-side only)
# --------------------------------------------------------------------------- #


def _rest_table(table: str, method: str, query: str = "", **kwargs: Any):
    """Thin wrapper over assets._rest that targets an arbitrary public table."""
    return assets._rest(method, f"/rest/v1/{table}{('?' + query) if query else ''}", **kwargs)


def registry_lookup(workflow_key: str, workflow_version: Optional[str]) -> Optional[dict]:
    q = f"key=eq.{workflow_key}&select=*"
    if workflow_version:
        q += f"&version=eq.{workflow_version}"
    resp = _rest_table("workflow_definitions", "GET", q)
    if resp.status_code >= 300:
        raise advanced_error("storage_unavailable", "The workflow registry is unavailable.")
    rows = resp.json()
    return rows[0] if rows else None


def get_asset_row(asset_id: str) -> Optional[dict]:
    rows = assets.table_select(f"id=eq.{asset_id}&select=*")
    return rows[0] if rows else None


def write_eval_run(row: dict[str, Any]) -> None:
    """Server-side only eval-run record. Never raises into the request path:
    an eval-record failure must not fail a user-visible operation."""
    try:
        _rest_table(
            "transformation_eval_runs",
            "POST",
            json=row,
            headers={"Content-Type": "application/json", "Prefer": "return=minimal"},
        )
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Strict parameter parsers (allow-list, never permissive)
# --------------------------------------------------------------------------- #

FORBIDDEN_KEYS = {
    "prompt", "negative_prompt", "workflow", "graph", "nodes", "image_url",
    "mask", "width", "height", "ratio", "offset", "seed_override", "url",
    "urls", "base64", "data", "loras", "controlnet",
}

_OUTPAINT_ALLOWED = {"expansion_mode", "direction", "anchor", "style_mode"}
_OUTPAINT_DIRECTION_ANCHOR = {
    "left": {"right", "center"},
    "right": {"left", "center"},
    "top": {"bottom", "center"},
    "bottom": {"top", "center"},
    "symmetric": {"center"},
}

_PRODUCT_SCENE_ALLOWED = {"scene_direction", "background_style", "preserve_subject"}
_PRODUCT_SCENE_SCENE_DIRECTIONS = {
    "clean_studio", "premium_neutral", "warm_lifestyle", "natural_surface",
}


def parse_outpaint_params(params: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(params, dict):
        raise advanced_error("invalid_request", "params must be an object.")
    for key in params:
        if key in FORBIDDEN_KEYS or key not in _OUTPAINT_ALLOWED:
            raise advanced_error("invalid_request", f"Unsupported parameter: {key!r}.")
    expansion_mode = params.get("expansion_mode", "anchor_directional")
    if expansion_mode != "anchor_directional":
        raise advanced_error("invalid_request", "expansion_mode must be 'anchor_directional'.")
    style_mode = params.get("style_mode", "preserve_source")
    if style_mode != "preserve_source":
        raise advanced_error("invalid_request", "style_mode must be 'preserve_source'.")
    direction = params.get("direction")
    anchor = params.get("anchor")
    if direction not in _OUTPAINT_DIRECTION_ANCHOR:
        raise advanced_error("invalid_request", "Invalid direction.")
    if anchor not in _OUTPAINT_DIRECTION_ANCHOR[direction]:
        raise advanced_error("invalid_request", "Invalid direction/anchor combination.")
    return {
        "expansion_mode": expansion_mode,
        "direction": direction,
        "anchor": anchor,
        "style_mode": style_mode,
    }


def parse_product_scene_params(params: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(params, dict):
        raise advanced_error("invalid_request", "params must be an object.")
    for key in params:
        if key in FORBIDDEN_KEYS or key not in _PRODUCT_SCENE_ALLOWED:
            raise advanced_error("invalid_request", f"Unsupported parameter: {key!r}.")
    scene_direction = params.get("scene_direction")
    if scene_direction not in _PRODUCT_SCENE_SCENE_DIRECTIONS:
        raise advanced_error("invalid_request", "Invalid scene_direction.")
    background_style = params.get("background_style")
    allowed_bg = ((row.get("input_schema") or {}).get("background_style_enum")) or []
    if allowed_bg and background_style not in allowed_bg:
        raise advanced_error("invalid_request", "Invalid background_style.")
    if params.get("preserve_subject", True) is not True:
        raise advanced_error("invalid_request", "preserve_subject must be true.")
    return {
        "scene_direction": scene_direction,
        "background_style": background_style,
        "preserve_subject": True,
    }


def parse_params(module: str, params: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    if module == "outpaint":
        return parse_outpaint_params(params)
    if module == "product_scene":
        return parse_product_scene_params(params, row)
    raise advanced_error("workflow_not_available", "This workflow is not available.")


# --------------------------------------------------------------------------- #
# Gate resolution (called from POST /v1/generations before any dispatch)
# --------------------------------------------------------------------------- #


def resolve_advanced_request(
    *,
    workflow_key: str,
    workflow_version: Optional[str],
    source_asset_id: str,
    output_preset: str,
    params: dict[str, Any],
    user_id: str,
    environment: str = "staging",
) -> dict[str, Any]:
    """Gate order (also re-run at dispatch time):
      2. master + module flags
      3. registry row: requires_source_asset, research_only, staging env, internal
      4. asset: exists, owned, kind=input, ready, not expired, right bucket
      5. input envelope + output preset
      6. strict params
    Auth (step 1) happens in the caller via the JWKS dependency.
    Raises an HTTPException with a safe error code on any failure.
    """
    # 2 — flags first: no registry or storage call when the framework is off.
    if not advanced_enabled():
        raise advanced_error("workflow_not_available", "This workflow is not available.")

    # 3 — registry
    row = registry_lookup(workflow_key, workflow_version)
    if row is None:
        raise advanced_error("workflow_not_available", "This workflow is not available.")
    module = "outpaint" if str(workflow_key).startswith("outpaint") else (
        "product_scene" if str(workflow_key).startswith("product_scene") else "other"
    )
    if not module_flag(module):
        raise advanced_error("workflow_not_available", "This workflow is not available.")
    if not row.get("requires_source_asset"):
        raise advanced_error("invalid_request", "This workflow does not accept a source asset.")
    if row.get("commercial_status") != "research_only":
        raise advanced_error("workflow_not_available", "This workflow is not available.")
    if environment != "staging" or "staging" not in (row.get("allowed_envs") or []):
        raise advanced_error("workflow_not_available", "This workflow is not available.")
    if row.get("registry_visibility") != "internal":
        raise advanced_error("workflow_not_available", "This workflow is not available.")
    if row.get("status") not in ("draft", "testing"):
        raise advanced_error("workflow_not_available", "This workflow is not available.")

    # 4 — source asset
    try:
        uuid.UUID(source_asset_id)
    except (ValueError, TypeError):
        raise advanced_error("asset_not_found", "This asset could not be found.")
    asset = get_asset_row(source_asset_id)
    if asset is None or asset.get("deleted_at"):
        raise advanced_error("asset_not_found", "This asset could not be found.")
    if asset.get("owner_id") != user_id:
        raise advanced_error("asset_not_owned", "This asset could not be found.")
    if asset.get("kind") != "input":
        raise advanced_error("invalid_request", "Only uploaded input assets can be used as a source.")
    if asset.get("status") != "ready":
        raise advanced_error("asset_not_ready", "This asset is not ready yet.")
    if asset.get("bucket") != assets.BUCKET:
        raise advanced_error("asset_not_found", "This asset could not be found.")
    expires_at = asset.get("expires_at")
    if expires_at and datetime.fromisoformat(expires_at) <= _now():
        raise advanced_error("asset_expired", "This asset has expired.")

    # 5 — envelope + preset
    envelope = row.get("input_envelope") or {}
    width = int(asset.get("width") or 0)
    height = int(asset.get("height") or 0)
    max_w = envelope.get("max_width")
    max_h = envelope.get("max_height")
    max_px = envelope.get("max_pixels")
    if max_w and width > int(max_w):
        raise advanced_error("invalid_request", "The source image exceeds the allowed width.")
    if max_h and height > int(max_h):
        raise advanced_error("invalid_request", "The source image exceeds the allowed height.")
    if max_px and width * height > int(max_px):
        raise advanced_error("invalid_request", "The source image exceeds the allowed pixel count.")
    presets = row.get("allowed_output_presets") or []
    if output_preset not in presets:
        raise advanced_error("invalid_request", "This output preset is not allowed for the workflow.")

    # 6 — strict params
    validated = parse_params(module, params, row)

    return {
        "registry_row": row,
        "asset": asset,
        "module": module,
        "output_preset": output_preset,
        "request_params": validated,
    }


# --------------------------------------------------------------------------- #
# Source acquisition + output lifecycle (used by WP1/WP2 dispatch paths;
# defined in WP0 so the order is fixed and testable)
# --------------------------------------------------------------------------- #


def acquire_source_bytes(asset: dict[str, Any]) -> bytes:
    """Download source bytes server-side and verify SHA256 against the asset
    row before use. Never returns or logs any URL or authorization."""
    data = assets.storage_download(asset["storage_path"])
    if data is None:
        raise advanced_error("source_integrity_failed", "The source image could not be read.")
    if hashlib.sha256(data).hexdigest() != (asset.get("sha256") or ""):
        raise advanced_error("source_integrity_failed", "The source image failed an integrity check.")
    return data


def validate_output_bytes(data: bytes, declared_mime: str) -> assets.ValidationResult:
    """Outputs go through the same authoritative validation as inputs."""
    return assets.validate_image(data, declared_mime)


def write_ready_output(
    *,
    data: bytes,
    content_type: str,
    owner_id: str,
    job_id: str,
    source_asset_id: str,
    workflow_key: str,
    workflow_version: str,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    """Validate → upload → hash → only then write the `ready` output row.
    Any failure marks nothing ready; callers must treat an exception as
    'job failed' and perform best-effort cleanup."""
    result = validate_output_bytes(data, content_type)
    output_asset_id = str(uuid.uuid4())
    ext = assets.CANONICAL_EXT[result.content_type]
    path = f"{owner_id}/{output_asset_id}/original.{ext}"
    resp = assets._rest(
        "POST",
        f"/storage/v1/object/{assets.BUCKET}/{path}",
        content=data,
        headers={"Content-Type": result.content_type, "x-upsert": "false"},
    )
    if resp.status_code >= 300:
        raise advanced_error("storage_unavailable", "Could not store the output image.")
    # created_at is written explicitly from the same instant as finalized_at.
    # Letting the DB default fill created_at made it a few ms LATER than the
    # app-computed finalized_at, and the validate_generation_asset_expiry
    # trigger rejects finalized_at < created_at — which is what failed the
    # first WP1 outpaint job after a successful generate + composite.
    stamped = assets._now()
    try:
        return assets.table_insert(
            {
                "id": output_asset_id,
                "created_at": assets._iso(stamped),
                "owner_id": owner_id,
                "bucket": assets.BUCKET,
                "storage_path": path,
                "content_type": result.content_type,
                "file_size": result.file_size,
                "width": result.width,
                "height": result.height,
                "sha256": result.sha256,
                "kind": "output",
                "status": "ready",
                "source_asset_id": source_asset_id,
                "job_id": job_id,
                "workflow_key": workflow_key,
                "workflow_version": workflow_version,
                "provenance": provenance,
                "finalized_at": assets._iso(stamped),
                "expires_at": assets._iso(stamped + assets.READY_TTL),
            }
        )
    except Exception:
        assets.storage_delete(path)  # never leave bytes without a row
        raise


# --------------------------------------------------------------------------- #
# Studio-safe registry filter (API layer, not the client)
# --------------------------------------------------------------------------- #


def studio_safe_row(row: dict[str, Any]) -> bool:
    return (
        row.get("registry_visibility") == "studio_safe"
        and row.get("commercial_status") != "research_only"
        and bool(row.get("production_enabled"))
        and bool(row.get("enabled_for_studio"))
    )
