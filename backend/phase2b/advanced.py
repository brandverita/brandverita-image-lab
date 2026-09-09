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
    an eval-record failure must not fail a user-visible operation. It must not
    fail silently either — log enough to spot a schema/key mismatch."""
    try:
        resp = _rest_table(
            "transformation_eval_runs",
            "POST",
            json=row,
            headers={"Content-Type": "application/json", "Prefer": "return=minimal"},
        )
        if resp.status_code >= 300:
            print(
                f"wp_eval_run_write_failed status={resp.status_code} "
                f"body={resp.text[:300]}"
            )
    except Exception as exc:  # noqa: BLE001
        print(f"wp_eval_run_write_failed exc={type(exc).__name__}: {str(exc)[:300]}")


# --------------------------------------------------------------------------- #
# Evaluation scores (staging, internal Lab only)
# --------------------------------------------------------------------------- #

SCORE_MODULES = ("outpaint", "product_scene")


def _eval_run_for_job(job_id: str) -> Optional[dict]:
    resp = _rest_table(
        "transformation_eval_runs",
        "GET",
        f"job_id=eq.{job_id}&select=id,module,variant_id,provider_params&limit=1",
    )
    if resp.status_code >= 300:
        return None
    rows = resp.json()
    return rows[0] if rows else None


def save_score(*, job_id: str, reviewer_user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """One score per reviewer per run; re-submitting replaces the previous one.
    The job is checked to belong to the reviewer before anything is written."""
    if not isinstance(payload, dict):
        raise advanced_error("invalid_request", "body must be an object.")
    resp = _rest_table(
        "generation_jobs",
        "GET",
        f"id=eq.{job_id}&user_id=eq.{reviewer_user_id}&select=id,workflow_id,status&limit=1",
    )
    if resp.status_code >= 300:
        raise advanced_error("storage_unavailable", "The evaluation store is unavailable.")
    job_rows = resp.json()
    if not job_rows:
        raise advanced_error("asset_not_found", "Run not found.")
    job = job_rows[0]

    try:
        overall = int(payload.get("overall"))
    except (TypeError, ValueError):
        raise advanced_error("invalid_request", "overall must be a whole number 1-5.")
    if overall < 1 or overall > 5:
        raise advanced_error("invalid_request", "overall must be a whole number 1-5.")

    brightness = payload.get("brightness")
    if brightness is not None:
        try:
            brightness = int(brightness)
        except (TypeError, ValueError):
            raise advanced_error("invalid_request", "brightness must be a whole number 1-5.")
        if brightness < 1 or brightness > 5:
            raise advanced_error("invalid_request", "brightness must be a whole number 1-5.")

    invented = payload.get("invented_content")
    if invented is not None and not isinstance(invented, bool):
        raise advanced_error("invalid_request", "invented_content must be true or false.")

    notes = payload.get("notes")
    if notes is not None:
        if not isinstance(notes, str):
            raise advanced_error("invalid_request", "notes must be text.")
        notes = notes.strip()[:500] or None

    eval_run = _eval_run_for_job(job_id) or {}
    module = eval_run.get("module") or str(job.get("workflow_id") or "")
    if module not in SCORE_MODULES:
        raise advanced_error("invalid_request", "This run cannot be scored.")

    row = {
        "job_id": job_id,
        "eval_run_id": eval_run.get("id"),
        "module": module,
        "reviewer_user_id": reviewer_user_id,
        "overall": overall,
        "invented_content": bool(invented) if invented is not None else False,
        "brightness": brightness,
        "notes": notes,
    }
    write = _rest_table(
        "transformation_eval_scores",
        "POST",
        json=row,
        headers={
            "Content-Type": "application/json",
            "Prefer": "return=representation,resolution=merge-duplicates",
        },
    )
    if write.status_code >= 300:
        print(f"wp_eval_score_write_failed status={write.status_code} body={write.text[:300]}")
        raise advanced_error("storage_unavailable", "The score could not be saved.")
    saved = write.json()
    return saved[0] if isinstance(saved, list) and saved else row


def list_scored_runs(*, reviewer_user_id: str, module: Optional[str] = None) -> list[dict]:
    """Flat list of this reviewer's scored runs with the settings that produced
    them, so variants can be compared without exposing another user's data."""
    q = (
        f"reviewer_user_id=eq.{reviewer_user_id}"
        "&select=job_id,module,overall,invented_content,brightness,notes,created_at,"
        "transformation_eval_runs(variant_id,provider_params,output_preset,"
        "provider_model,total_latency_ms,estimated_cost)"
        "&order=created_at.desc&limit=200"
    )
    if module in SCORE_MODULES:
        q = f"module=eq.{module}&" + q
    resp = _rest_table("transformation_eval_scores", "GET", q)
    if resp.status_code >= 300:
        raise advanced_error("storage_unavailable", "The evaluation store is unavailable.")
    rows = resp.json()
    flattened: list[dict] = []
    for r in rows if isinstance(rows, list) else []:
        run = r.pop("transformation_eval_runs", None) or {}
        if isinstance(run, list):
            run = run[0] if run else {}
        r["variant_id"] = run.get("variant_id")
        r["provider_params"] = run.get("provider_params") or {}
        r["output_preset"] = run.get("output_preset")
        r["provider_model"] = run.get("provider_model")
        r["total_latency_ms"] = run.get("total_latency_ms")
        r["estimated_cost"] = run.get("estimated_cost")
        flattened.append(r)
    return flattened


def summarize_scores(rows: list[dict]) -> list[dict]:
    """Mean overall / brightness and invention rate per module+variant."""
    buckets: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        key = (r.get("module") or "unknown", r.get("variant_id") or "default")
        b = buckets.setdefault(
            key,
            {
                "module": key[0],
                "variant_id": key[1],
                "runs": 0,
                "_overall": 0,
                "_brightness": 0,
                "_brightness_n": 0,
                "invented": 0,
            },
        )
        b["runs"] += 1
        b["_overall"] += int(r.get("overall") or 0)
        if r.get("brightness") is not None:
            b["_brightness"] += int(r["brightness"])
            b["_brightness_n"] += 1
        if r.get("invented_content"):
            b["invented"] += 1
    out = []
    for b in buckets.values():
        runs = max(b["runs"], 1)
        out.append(
            {
                "module": b["module"],
                "variant_id": b["variant_id"],
                "runs": b["runs"],
                "overall_mean": round(b["_overall"] / runs, 2),
                "brightness_mean": (
                    round(b["_brightness"] / b["_brightness_n"], 2)
                    if b["_brightness_n"]
                    else None
                ),
                "invented_rate": round(b["invented"] / runs, 2),
            }
        )
    out.sort(key=lambda x: (x["module"], x["variant_id"]))
    return out


# --------------------------------------------------------------------------- #
# Strict parameter parsers (allow-list, never permissive)
# --------------------------------------------------------------------------- #

FORBIDDEN_KEYS = {
    "prompt", "negative_prompt", "workflow", "graph", "nodes", "image_url",
    "mask", "width", "height", "ratio", "offset", "seed_override", "url",
    "urls", "base64", "data", "loras", "controlnet",
}

# Research knobs (staging, internal Lab only). They are enum-bounded: a value
# outside the allow-list is a 400, and free text can never reach the provider
# because these keys only ever select between server-owned constants.
#
# `prompt_mode` picks which server-owned continuation text is sent with a Smart
# Resize run; `guidance` / `steps` control how tightly the provider follows the
# supplied picture, which is the setting that stops it inventing content.
OUTPAINT_PROMPT_MODES = ("guided", "bare", "bright")
OUTPAINT_GUIDANCE_VALUES = (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0)
OUTPAINT_STEPS_VALUES = (20, 30, 40, 50)
PRODUCT_SCENE_PRESET_VARIANTS = ("v1", "v2")

_OUTPAINT_ALLOWED = {
    "expansion_mode",
    "direction",
    "anchor",
    "style_mode",
    "prompt_mode",
    "guidance",
    "steps",
}
_OUTPAINT_DIRECTION_ANCHOR = {
    "left": {"right", "center"},
    "right": {"left", "center"},
    "top": {"bottom", "center"},
    "bottom": {"top", "center"},
    "symmetric": {"center"},
}

_PRODUCT_SCENE_ALLOWED = {
    "scene_direction",
    "background_style",
    "preserve_subject",
    "preset_variant",
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
    validated: dict[str, Any] = {
        "expansion_mode": expansion_mode,
        "direction": direction,
        "anchor": anchor,
        "style_mode": style_mode,
    }
    # Optional research knobs. Absent means "use the deployed server default",
    # so an ordinary (Studio-shaped) request is byte-identical to before.
    if params.get("prompt_mode") is not None:
        mode = params.get("prompt_mode")
        if mode not in OUTPAINT_PROMPT_MODES:
            raise advanced_error("invalid_request", "Invalid prompt_mode.")
        validated["prompt_mode"] = mode
    if params.get("guidance") is not None:
        try:
            guidance = float(params.get("guidance"))
        except (TypeError, ValueError):
            raise advanced_error("invalid_request", "Invalid guidance.")
        if guidance not in OUTPAINT_GUIDANCE_VALUES:
            raise advanced_error("invalid_request", "Invalid guidance.")
        validated["guidance"] = guidance
    if params.get("steps") is not None:
        try:
            steps = int(params.get("steps"))
        except (TypeError, ValueError):
            raise advanced_error("invalid_request", "Invalid steps.")
        if steps not in OUTPAINT_STEPS_VALUES:
            raise advanced_error("invalid_request", "Invalid steps.")
        validated["steps"] = steps
    return validated


def parse_product_scene_params(params: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    """Module B accepts enums only. The scene instruction text lives in the
    server-owned `scene_presets` table, so a valid request cannot influence a
    single word of what the hosted provider is asked to do."""
    import scene_presets

    if not isinstance(params, dict):
        raise advanced_error("invalid_request", "params must be an object.")
    for key in params:
        if key in FORBIDDEN_KEYS or key not in _PRODUCT_SCENE_ALLOWED:
            raise advanced_error("invalid_request", f"Unsupported parameter: {key!r}.")
    scene_direction = params.get("scene_direction")
    if scene_direction not in scene_presets.SCENE_PRESETS:
        raise advanced_error("invalid_request", "Invalid scene_direction.")
    # The registry row may narrow the code-level enum, never widen it.
    allowed_scenes = ((row.get("input_schema") or {}).get("scene_direction_enum")) or []
    if allowed_scenes and scene_direction not in allowed_scenes:
        raise advanced_error("invalid_request", "Invalid scene_direction.")
    background_style = params.get("background_style") or scene_presets.DEFAULT_BACKGROUND_STYLE
    if background_style not in scene_presets.BACKGROUND_STYLES:
        raise advanced_error("invalid_request", "Invalid background_style.")
    allowed_bg = ((row.get("input_schema") or {}).get("background_style_enum")) or []
    if allowed_bg and background_style not in allowed_bg:
        raise advanced_error("invalid_request", "Invalid background_style.")
    if params.get("preserve_subject", True) is not True:
        raise advanced_error("invalid_request", "preserve_subject must be true.")
    validated: dict[str, Any] = {
        "scene_direction": scene_direction,
        "background_style": background_style,
        "preserve_subject": True,
    }
    # Optional wording variant, evaluation only; absent means the shipped text.
    if params.get("preset_variant") is not None:
        variant = params.get("preset_variant")
        if variant not in PRODUCT_SCENE_PRESET_VARIANTS:
            raise advanced_error("invalid_request", "Invalid preset_variant.")
        validated["preset_variant"] = variant
    return validated



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
# Output asset -> short-lived signed result URL
# --------------------------------------------------------------------------- #


def output_result_url(output_asset_id: Optional[str], owner_id: str) -> Optional[str]:
    """Mint a short-lived signed read URL for a job's stored output asset.

    Advanced modules (outpaint, product_scene) persist their result as a
    `generation_assets` row instead of the legacy `output_path`, so the job
    response had no `result_url` and clients rendered an empty result box.

    Only the caller's own `ready`, non-deleted asset is ever signed. Any
    failure returns None (never raises, never logs a URL) so a job response
    stays valid and the client's refresh action remains available.
    """
    if not output_asset_id:
        return None
    try:
        rows = assets.table_select(
            "select=storage_path,status,deleted_at"
            f"&id=eq.{output_asset_id}&owner_id=eq.{owner_id}&limit=1"
        )
    except Exception:  # noqa: BLE001
        return None
    if not rows:
        return None
    row = rows[0]
    if row.get("status") != "ready" or row.get("deleted_at"):
        return None
    try:
        return assets.storage_signed_read_url(row["storage_path"])
    except Exception:  # noqa: BLE001
        return None


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
