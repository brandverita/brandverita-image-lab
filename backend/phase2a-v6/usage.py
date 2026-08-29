"""
Phase 2A — usage ledger helper interface (STAGING ONLY, NOT WIRED).

This module exists so a future phase can create *informational* usage records
next to job submission. Phase 2A deliberately does NOT call any of it: no
credits are deducted, no pricing is exposed to users, and Flux generation
behaviour is unchanged.

Integration point (deferred): in `api.py`, immediately after the
`generation_jobs` row is inserted and before dispatch, a future phase may call
`reserve_usage(...)` and store the returned id on the job's `usage_ledger_id`.
That is only safe once it can be done atomically with job creation (single
insert path plus compensating `void_usage` on dispatch failure), so it stays
deferred here.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

TABLE = "usage_ledger"


def _headers() -> dict[str, str]:
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _url(path: str) -> str:
    return f"{os.environ['SUPABASE_URL'].rstrip('/')}/rest/v1/{path}"


def reserve_usage(
    *,
    user_id: str,
    workflow_key: str,
    workflow_version: str,
    provider: str,
    job_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    estimated_credits: Optional[float] = None,
    estimated_provider_cost: Optional[float] = None,
) -> dict[str, Any]:
    """Creates an informational `reserved` row. No balance is checked or debited."""
    row = {
        "user_id": user_id,
        "workflow_key": workflow_key,
        "workflow_version": workflow_version,
        "provider": provider,
        "job_id": job_id,
        "workspace_id": workspace_id,
        "estimated_credits": estimated_credits,
        "estimated_provider_cost": estimated_provider_cost,
        "status": "reserved",
    }
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(_url(TABLE), headers=_headers(), json=row)
    resp.raise_for_status()
    return resp.json()[0]


def settle_usage(
    ledger_id: str,
    *,
    actual_provider_cost: Optional[float] = None,
    gpu_seconds: Optional[float] = None,
) -> dict[str, Any]:
    patch = {
        "status": "settled",
        "settled_at": datetime.now(timezone.utc).isoformat(),
        "actual_provider_cost": actual_provider_cost,
        "gpu_seconds": gpu_seconds,
    }
    with httpx.Client(timeout=15.0) as client:
        resp = client.patch(_url(f"{TABLE}?id=eq.{ledger_id}"), headers=_headers(), json=patch)
    resp.raise_for_status()
    return resp.json()[0]


def void_usage(ledger_id: str) -> dict[str, Any]:
    with httpx.Client(timeout=15.0) as client:
        resp = client.patch(
            _url(f"{TABLE}?id=eq.{ledger_id}"),
            headers=_headers(),
            json={"status": "void", "settled_at": datetime.now(timezone.utc).isoformat()},
        )
    resp.raise_for_status()
    return resp.json()[0]
