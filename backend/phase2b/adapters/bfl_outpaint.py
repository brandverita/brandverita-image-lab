"""
Phase 2B WP1b — Module A Smart Resize on the hosted provider (BFL expand).

Why this exists: the self-hosted SD-1.5 inpainting path (`modal_research_2b`)
can only invent 512-px-scale content, so wide extensions repeated subjects,
seamed, or produced flat grey. This adapter keeps every protection of the WP1
path and swaps only the generator for BFL's dedicated expand endpoint.

Unchanged from WP1 (deliberately, same helpers):
  * WP0 gate re-run at dispatch time (flags, ownership, readiness, params)
  * source downloaded and digest-verified server-side, never by the browser
  * geometry computed server-side from validated enums only
    (`outpaint_geometry.plan`) — the client cannot influence placement
  * the untouched source rectangle is pasted back over the provider result and
    verified byte-for-byte (`composite_and_verify` + `pixel_digest`); an
    unverified result fails the job and writes no asset and no storage object
  * every temp file deleted in `finally`

Different from WP1:
  * no ComfyUI worker, no mask; BFL is told how many pixels to add on each side
  * the provider credential lives only in the `bfl-research-2b` Modal secret and
    the image is inlined as base64 from this side — no signed URL is handed out
  * cost is recorded per run instead of GPU seconds

Provider key in the registry: `bfl_outpaint`.
"""

from __future__ import annotations

import base64
import hashlib
import io
import os
import shutil
import tempfile
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Optional

PROVIDER = "bfl_outpaint"
PROVIDER_FAMILY = "bfl"
PROVIDER_MODEL = "flux-pro-1.0-expand"
BFL_BASE_URL = os.environ.get("BFL_BASE_URL", "https://api.bfl.ai")
SECRET_NAME = "bfl-research-2b"

SUBMIT_TIMEOUT_S = 60
POLL_INTERVAL_S = 2.0
PROVIDER_TIMEOUT_S = 300
# Research-stage estimate per image (USD), metering only. Enforcement of any
# allowance lives in myaccount.brandverita.io, never here.
COST_PER_IMAGE = 0.05
# Provider limit per side.
MAX_EXPAND_PX = 2048

# Server-owned instruction for style_mode=preserve_source.
#
# WP1b failure mode, observed 2026-09-07: the first version ended with
# "Do not add new subjects, people, objects, text, logos, borders or frames."
# Flux-family models have no negation; every noun in that clause is read as
# something to include, so a square seascape came back with a woman's face in
# both side bands. The instruction is therefore purely positive — it describes
# continuation only and never names anything to avoid.
EXPAND_INSTRUCTION_GUIDED = (
    "Continue this same photograph outward to the edges. Carry on the existing "
    "background, sky, water, horizon line, perspective, lighting, colour grade "
    "and grain exactly as they already appear, so the wider picture reads as one "
    "continuous scene."
)

# The hosted expand model works from the picture alone; kept as a comparison
# mode so the guided text can be measured against no text at all.
EXPAND_INSTRUCTION_BARE = ""

PROMPT_MODES = {"guided": EXPAND_INSTRUCTION_GUIDED, "bare": EXPAND_INSTRUCTION_BARE}


def prompt_mode() -> str:
    mode = (os.environ.get("OUTPAINT_V2_PROMPT_MODE") or "guided").strip().lower()
    return mode if mode in PROMPT_MODES else "guided"


def expand_instruction() -> str:
    """Server-owned only: never read from a request body."""
    return PROMPT_MODES[prompt_mode()]


_dispatcher = None


def set_dispatcher(fn) -> None:
    """api.py injects the Modal-wrapped background function."""
    global _dispatcher
    _dispatcher = fn


def submit_generation(job: dict, _inputs: dict, _row: dict) -> Optional[str]:
    from fastapi import HTTPException

    if _dispatcher is None:
        raise HTTPException(
            status_code=503,
            detail="dispatch_failed: the hosted expand provider is not available.",
        )
    call = _dispatcher.spawn(job_id=job["job_id"], user_id=job["user_id"])
    return getattr(call, "object_id", None)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat()


def _stage(job_id: str, name: str, **fields: Any) -> None:
    extra = " ".join(f"{k}={v}" for k, v in fields.items())
    print(f"wp1b_stage job={job_id} step={name} {extra}".rstrip())


def _describe(exc: BaseException) -> str:
    detail = getattr(exc, "detail", None)
    status = getattr(exc, "status_code", None)
    if detail is not None:
        text = f"{type(exc).__name__}({status}): {detail}"
    else:
        text = f"{type(exc).__name__}: {exc}"
    return text[:900]


def hosted_dispatch_enabled() -> bool:
    import advanced

    return advanced._flag("HOSTED_PROVIDER_DISPATCH_ENABLED") and advanced.provider_flag(
        PROVIDER_FAMILY
    )


def _api_key() -> str:
    key = (os.environ.get("BFL_API_KEY") or "").strip()
    if not key:
        raise RuntimeError(
            f"provider_credential_missing: BFL_API_KEY absent (secret {SECRET_NAME})"
        )
    return key


def expansion_from_placement(placement) -> dict[str, int]:
    """Pixels to add on each side, derived from the server-side placement."""
    left = placement.region_left
    top = placement.region_top
    right = placement.canvas_width - (placement.region_left + placement.region_width)
    bottom = placement.canvas_height - (placement.region_top + placement.region_height)
    padding = {
        "left": max(0, left),
        "top": max(0, top),
        "right": max(0, right),
        "bottom": max(0, bottom),
    }
    for side, value in padding.items():
        if value > MAX_EXPAND_PX:
            raise RuntimeError(
                f"expansion_too_large: {side}={value}px exceeds provider limit "
                f"{MAX_EXPAND_PX}px"
            )
    return padding


def _png_bytes(image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", compress_level=6)
    return buffer.getvalue()


def _call_bfl(*, job_id: str, image_bytes: bytes, padding: dict[str, int]) -> dict[str, Any]:
    """Submit + poll + fetch, entirely server-side."""
    import httpx

    key = _api_key()
    headers = {"x-key": key, "Content-Type": "application/json"}
    payload = {
        "image": base64.b64encode(image_bytes).decode(),
        "prompt": expand_instruction(),
        "top": padding["top"],
        "bottom": padding["bottom"],
        "left": padding["left"],
        "right": padding["right"],
        "output_format": "png",
        "prompt_upsampling": False,
        "safety_tolerance": 2,
    }

    with httpx.Client(timeout=SUBMIT_TIMEOUT_S) as client:
        response = client.post(
            f"{BFL_BASE_URL}/v1/{PROVIDER_MODEL}", json=payload, headers=headers
        )
        if response.status_code == 402:
            raise RuntimeError("provider_quota_exhausted: BFL reports no remaining credit")
        if response.status_code in (401, 403):
            raise RuntimeError("provider_auth_failed: BFL rejected the research credential")
        if response.status_code >= 300:
            raise RuntimeError(
                f"provider_rejected: BFL {response.status_code} {response.text[:300]}"
            )
        submitted = response.json()
        request_id = submitted.get("id")
        polling_url = submitted.get("polling_url") or f"{BFL_BASE_URL}/v1/get_result"
        _stage(job_id, "provider_submitted", request=request_id)

        deadline = time.time() + PROVIDER_TIMEOUT_S
        result: dict[str, Any] = {}
        while True:
            if time.time() > deadline:
                raise RuntimeError(
                    f"provider_timeout: no result from BFL within {PROVIDER_TIMEOUT_S}s"
                )
            time.sleep(POLL_INTERVAL_S)
            poll = client.get(polling_url, params={"id": request_id}, headers={"x-key": key})
            if poll.status_code >= 300:
                raise RuntimeError(f"provider_poll_failed: BFL {poll.status_code}")
            body = poll.json()
            status = str(body.get("status") or "")
            if status in ("Ready", "ready"):
                result = body.get("result") or {}
                break
            if status in ("Error", "Failed", "Request Moderated", "Content Moderated"):
                code = "provider_moderated" if "Moderated" in status else "provider_failed"
                raise RuntimeError(f"{code}: BFL returned status {status}")

        sample_url = result.get("sample")
        if not sample_url:
            raise RuntimeError("provider_failed: BFL result carried no image")
        fetched = client.get(sample_url, timeout=120.0)
        if fetched.status_code >= 300 or not fetched.content:
            raise RuntimeError(f"provider_fetch_failed: BFL asset {fetched.status_code}")

    return {"image": fetched.content, "request_id": request_id}


# --------------------------------------------------------------------------- #
# background execution
# --------------------------------------------------------------------------- #


def run_outpaint(job_id: str, user_id: str) -> None:
    from PIL import Image

    import advanced
    import jobs
    import outpaint_geometry
    import registry
    import supabase_rest

    queued_at = datetime.now(timezone.utc)
    job_dir = tempfile.mkdtemp(prefix=f"wp1b-{job_id[:8]}-", dir="/tmp")
    temp_files: list[str] = []
    eval_row: dict[str, Any] = {
        "module": "outpaint",
        "job_id": job_id,
        "workflow_key": "outpaint",
        "workflow_version": "v2",
        "provider": PROVIDER,
        "provider_model": PROVIDER_MODEL,
        "operator_user_id": user_id,
        "queued_at": _iso(queued_at),
        "status": "running",
        "blinded": False,
        "legal_status": "pending",
        "commercial_status": "research_only",
    }

    try:
        rows = supabase_rest.rest_get(
            "generation_jobs",
            {"select": "*", "id": f"eq.{job_id}", "user_id": f"eq.{user_id}", "limit": 1},
        )
        if not rows:
            return
        job = rows[0]

        jobs.patch_job(
            job_id, {"status": "processing", "started_at": _iso(datetime.now(timezone.utc))}
        )

        row = registry.resolve_workflow(job["workflow_id"], job.get("workflow_version"))
        params = job.get("request_params") or {}
        preset = job.get("output_preset") or ""

        # 1 — gate again at dispatch time.
        resolved = advanced.resolve_advanced_request(
            workflow_key=row["key"],
            workflow_version=row["version"],
            source_asset_id=job.get("source_asset_id"),
            output_preset=preset,
            params=params,
            user_id=user_id,
            environment=registry.ENVIRONMENT,
        )
        if not hosted_dispatch_enabled():
            raise RuntimeError("hosted_dispatch_disabled: BFL dispatch is switched off")

        asset = resolved["asset"]
        validated = resolved["request_params"]
        eval_row.update(
            {
                "workflow_key": row["key"],
                "workflow_version": row["version"],
                "config_hash": row.get("config_hash"),
                "source_asset_id": asset["id"],
                "output_preset": preset,
                "request_params": validated,
            }
        )

        # 2 + 3 — server-side download, digest verified before use.
        _stage(job_id, "gate_passed", asset=asset["id"], preset=preset)
        source_bytes = advanced.acquire_source_bytes(asset)
        source_path = os.path.join(job_dir, "source.bin")
        with open(source_path, "wb") as handle:
            handle.write(source_bytes)
        temp_files.append(source_path)
        _stage(job_id, "source_downloaded", bytes=len(source_bytes))

        source_image = Image.open(io.BytesIO(source_bytes))
        source_image.load()

        # 4 — server-owned geometry (identical to WP1), turned into per-side
        # pixel amounts for the provider.
        scaled_source, placement = outpaint_geometry.plan(
            source=source_image,
            output_preset=preset,
            direction=validated["direction"],
            anchor=validated["anchor"],
        )
        padding = expansion_from_placement(placement)
        placed_png = _png_bytes(scaled_source)
        placed_path = os.path.join(job_dir, "placed.png")
        with open(placed_path, "wb") as handle:
            handle.write(placed_png)
        temp_files.append(placed_path)
        _stage(job_id, "geometry_ready", **padding)

        # 5 — hosted call, bounded.
        dispatched_at = datetime.now(timezone.utc)
        eval_row["dispatched_at"] = _iso(dispatched_at)
        started = time.time()
        provider_result = _call_bfl(
            job_id=job_id, image_bytes=placed_png, padding=padding
        )
        provider_latency_ms = int((time.time() - started) * 1000)
        eval_row["provider_latency_ms"] = provider_latency_ms
        eval_row["estimated_cost"] = COST_PER_IMAGE
        eval_row["provider_call_id"] = provider_result.get("request_id")
        _stage(
            job_id,
            "provider_returned",
            ms=provider_latency_ms,
            bytes=len(provider_result["image"]),
        )

        generated_path = os.path.join(job_dir, "generated.png")
        with open(generated_path, "wb") as handle:
            handle.write(provider_result["image"])
        temp_files.append(generated_path)

        # 6 + 7 — paste the untouched source back, then prove it survived.
        output_png, verified = outpaint_geometry.composite_and_verify(
            generated_png=provider_result["image"],
            scaled_source=scaled_source,
            placement=placement,
        )
        eval_row["source_region_verified"] = verified
        if not verified:
            raise RuntimeError("source_region_integrity_failed")

        output_path = os.path.join(job_dir, "output.png")
        with open(output_path, "wb") as handle:
            handle.write(output_png)
        temp_files.append(output_path)

        # 8 — validate → upload → hash → ready row.
        instruction = expand_instruction()
        provenance = {
            "workflow": f"{row['key']}:{row['version']}",
            "provider": PROVIDER,
            "provider_model": PROVIDER_MODEL,
            "provider_request_id": provider_result.get("request_id"),
            "output_preset": preset,
            "params": validated,
            "geometry": placement.as_provenance(),
            "expansion_px": padding,
            "instruction": instruction,
            "prompt_mode": prompt_mode(),
            "instruction_sha256": hashlib.sha256(instruction.encode()).hexdigest(),
            "instruction_chars": len(instruction),
            "source_asset_sha256": asset.get("sha256"),
            "source_region_verified": verified,
            "artifact_pins": row.get("artifact_pins") or [],
            "classification": "research_only/staging",
        }
        output_asset = advanced.write_ready_output(
            data=output_png,
            content_type="image/png",
            owner_id=user_id,
            job_id=job_id,
            source_asset_id=asset["id"],
            workflow_key=row["key"],
            workflow_version=row["version"],
            provenance=provenance,
        )
        output_asset_id = (
            output_asset[0]["id"] if isinstance(output_asset, list) else output_asset["id"]
        )

        completed_at = datetime.now(timezone.utc)
        jobs.patch_job(
            job_id,
            {
                "status": "completed",
                "progress": 100,
                "output_asset_id": output_asset_id,
                "width": placement.canvas_width,
                "height": placement.canvas_height,
                "completed_at": _iso(completed_at),
            },
        )

        eval_row.update(
            {
                "status": "completed",
                "output_asset_id": output_asset_id,
                "completed_at": _iso(completed_at),
                "total_latency_ms": int((completed_at - queued_at).total_seconds() * 1000),
                "cold_start": False,
                "output_width": placement.canvas_width,
                "output_height": placement.canvas_height,
                "output_bytes": len(output_png),
            }
        )
        advanced.write_eval_run(eval_row)
        print(f"wp1b_outpaint_completed job={job_id} verified={verified} preset={preset}")

    except Exception as exc:  # noqa: BLE001
        described = _describe(exc)
        print(f"wp1b_outpaint_failed job={job_id} detail={described}")
        print(traceback.format_exc())
        try:
            import jobs as _jobs

            _jobs.patch_job(
                job_id,
                {
                    "status": "failed",
                    "error_code": "transformation_failed",
                    "error_category": "provider",
                    "error_message": "The transformation could not be completed.",
                    "completed_at": _iso(datetime.now(timezone.utc)),
                },
            )
        except Exception:  # noqa: BLE001
            pass
        try:
            import advanced as _advanced

            eval_row.update(
                {
                    "status": "failed",
                    "error_code": "transformation_failed",
                    "error_message": described,
                    "completed_at": _iso(datetime.now(timezone.utc)),
                }
            )
            _advanced.write_eval_run(eval_row)
        except Exception:  # noqa: BLE001
            pass

    finally:
        removed = 0
        for path in temp_files:
            try:
                os.unlink(path)
                removed += 1
            except OSError:
                pass
        shutil.rmtree(job_dir, ignore_errors=True)
        print(
            f"wp1b_temp_cleanup job={job_id} files_removed={removed} "
            f"dir_exists={os.path.exists(job_dir)}"
        )
