"""Workflow registry: load/cache workflow_definitions, dispatch gates, safe views.

The registry is the ONLY place commercial classification is enforced — the
provider adapters themselves are neutral. Clients never read the
workflow_definitions table directly (deny-all RLS); they receive the safe,
server-filtered view from GET /v1/workflows.
"""

import hashlib
import json
import os
import threading
import time
from typing import Optional

from fastapi import HTTPException

import advanced
import supabase_rest

CACHE_TTL_SECONDS = 60
ENVIRONMENT = os.environ.get("API_ENVIRONMENT", "staging")

# Client-facing aliases -> (registry key, default version).
LEGACY_WORKFLOW_ALIASES = {
    "flux-schnell-txt2img-v1": ("flux_text_to_image", "v1"),
    "flux_text_to_image": ("flux_text_to_image", "v1"),
}

# commercial_status values allowed for Studio/production dispatch.
COMMERCIAL_APPROVED = {
    "commercial_hosted",
    "commercial_self_hosted_approved",
    "licensed_self_hosted",
}

_cache_lock = threading.Lock()
_cache_rows: list = []
_cache_loaded_at = 0.0


def load_registry(force: bool = False) -> list:
    """All registry rows, cached for 60s. Raises HTTPException(500) if the
    registry cannot be read — a missing registry must never silently allow."""
    global _cache_rows, _cache_loaded_at
    with _cache_lock:
        if not force and _cache_rows and (time.monotonic() - _cache_loaded_at) < CACHE_TTL_SECONDS:
            return _cache_rows
        rows = supabase_rest.rest_get(
            "workflow_definitions",
            {"select": "*"},
            error_detail="registry_unavailable: could not load workflow registry",
        )
        _cache_rows = rows
        _cache_loaded_at = time.monotonic()
        return rows


def get_workflow(key: str, version: str) -> Optional[dict]:
    for row in load_registry():
        if row.get("key") == key and row.get("version") == version:
            return row
    return None


def resolve_workflow(workflow_id: str, workflow_version: Optional[str]) -> dict:
    """Map a client workflow reference to a registry row or 400."""
    alias = LEGACY_WORKFLOW_ALIASES.get(workflow_id)
    if alias:
        key, default_version = alias
    elif ":" in workflow_id:
        key, default_version = workflow_id.split(":", 1)
    else:
        key, default_version = workflow_id, None

    version = workflow_version or default_version
    if not version:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported_workflow: workflow version required for '{key}'",
        )
    row = get_workflow(key, version)
    if row is None:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported_workflow: no registered workflow '{key}:{version}'",
        )
    return row


def compute_config_hash(row: dict) -> str:
    """sha256 over the canonical JSON of the immutable config fields. Must
    match the seeded config_hash; a mismatch means someone edited an active
    version's config outside the immutability trigger's coverage."""
    config = {
        "key": row.get("key"),
        "version": row.get("version"),
        "provider": row.get("provider"),
        "provider_model": row.get("provider_model"),
        "provider_workflow_reference": row.get("provider_workflow_reference"),
        "input_schema": row.get("input_schema"),
        "output_schema": row.get("output_schema"),
        "allowed_dimensions": row.get("allowed_dimensions"),
    }
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def assert_dispatch_allowed(row: dict, origin: str = "lab") -> None:
    """Registry-owned dispatch gate. Adapters stay neutral; this is where
    commercial approval is enforced."""
    if row.get("status") != "active":
        raise HTTPException(
            status_code=403,
            detail=f"workflow_unavailable: workflow '{row.get('key')}:{row.get('version')}' is not active",
        )
    if ENVIRONMENT not in (row.get("allowed_envs") or []):
        raise HTTPException(
            status_code=403,
            detail=f"workflow_unavailable: workflow '{row.get('key')}:{row.get('version')}' is not allowed in this environment",
        )
    if origin == "studio" or ENVIRONMENT == "production":
        if row.get("commercial_status") not in COMMERCIAL_APPROVED or not row.get("production_enabled"):
            raise HTTPException(
                status_code=403,
                detail="workflow_not_commercially_approved: this workflow is not approved for production use",
            )


def validate_inputs(row: dict, inputs) -> None:
    """Validate request inputs against the registry row's input_schema and
    allowed_dimensions. `inputs` is the parsed GenerationInputs model."""
    schema = row.get("input_schema") or {}

    prompt_rules = schema.get("prompt") or {}
    if prompt_rules.get("required", True) and not inputs.prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")
    prompt_max = prompt_rules.get("max_length", 2000)
    if len(inputs.prompt) > prompt_max:
        raise HTTPException(status_code=400, detail=f"Prompt exceeds {prompt_max} characters")

    negative_rules = schema.get("negative_prompt") or {}
    negative_max = negative_rules.get("max_length", 1000)
    if len(inputs.negative_prompt or "") > negative_max:
        raise HTTPException(status_code=400, detail=f"Negative prompt exceeds {negative_max} characters")

    dimensions = row.get("allowed_dimensions") or []
    allowed = {(d.get("width"), d.get("height")) for d in dimensions}
    if allowed and (inputs.width, inputs.height) not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported dimensions")

    seed_rules = schema.get("seed") or {}
    if inputs.seed is not None:
        seed_min = seed_rules.get("minimum", 0)
        seed_max = seed_rules.get("maximum", 4294967295)
        if not (seed_min <= inputs.seed <= seed_max):
            raise HTTPException(status_code=400, detail="Seed out of range")


# Fields a client may ever see. Raw graphs, provider references, model file
# paths, deployment references, and infrastructure internals never leave.
SAFE_FIELDS = (
    "key",
    "version",
    "display_name",
    "description",
    "status",
    "provider",
    "provider_model",
    "commercial_status",
    "allowed_dimensions",
    "estimated_credits",
    "enabled_for_studio",
    "production_enabled",
)


def safe_workflow_view(row: dict, include_config_hash: bool = False) -> dict:
    view = {field: row.get(field) for field in SAFE_FIELDS}
    if include_config_hash and row.get("config_hash"):
        view["config_hash_prefix"] = row["config_hash"][:12]
    return view


def list_visible_workflows(origin: str = "lab") -> list:
    """Correction-1 server filtering. Phase 1 has no Studio origin: every
    authenticated Lab caller is an allowlisted internal user and sees the
    internal view for this environment. Studio filtering is delegated to the
    shared `advanced.studio_safe_row` predicate (registry_visibility ==
    'studio_safe', non-research_only, production_enabled, enabled_for_studio)
    plus an active-status check, applied once a Studio origin exists."""
    visible = []
    for row in load_registry():
        visibility = row.get("registry_visibility")
        if visibility not in ("internal", "studio_safe"):
            continue
        if ENVIRONMENT not in (row.get("allowed_envs") or []):
            continue
        if origin == "studio":
            if row.get("status") != "active" or not advanced.studio_safe_row(row):
                continue
        visible.append(safe_workflow_view(row, include_config_hash=(origin == "lab")))
    return visible
