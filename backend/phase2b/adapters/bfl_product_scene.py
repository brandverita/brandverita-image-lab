"""
Phase 2B WP2 — Module B product background / scene adapter (hosted provider: BFL).

Runs inside the brandverita-api-v6 app in a background Modal function, the same
shape as the WP1 outpaint adapter: this side owns assets, storage, the database
and the provider credential; the browser never sees any of them.

Order (fixed, mirrors WP1):
  1. re-run the framework gate at dispatch time (flags, ownership, readiness,
     expiry, strict enum params)
  2. download the source server-side into a job temp dir
  3. verify SHA256 against the asset row before use
  4. build the provider request from SERVER-OWNED preset text only (scene_presets)
  5. call BFL with the image inlined as base64 — never a signed Supabase URL
  6. fetch the provider result server-side, then normalise to the exact preset size
  7. validate → upload → hash → write the `ready` output asset row
  8. delete every temp file in `finally`
  9. update the job and write the transformation_eval_run

Provider key in the registry: `bfl_product_scene`.

Honest limitation, recorded per run: unlike WP1 outpaint there is no byte-exact
source region to verify — the provider re-renders the whole frame. We therefore
record `source_region_verified = null` and a `subject_preserved = "unverified"`
provenance marker. Human review in the eval rubric is the gate for Module B,
which is why the workflow stays research_only.
"""

from __future__ import annotations

import base64
import io
import os
import shutil
import tempfile
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Optional

PROVIDER = "bfl_product_scene"
PROVIDER_FAMILY = "bfl"
PROVIDER_MODEL = "flux-kontext-pro"
BFL_BASE_URL = os.environ.get("BFL_BASE_URL", "https://api.bfl.ai")
SECRET_NAME = "bfl-research-2b"

SUBMIT_TIMEOUT_S = 60
POLL_INTERVAL_S = 2.0
PROVIDER_TIMEOUT_S = 300  # hosted call is bounded: a stuck provider fails fast
# Research-stage cost estimate for flux-kontext-pro, per image (USD). Recorded
# for metering only; enforcement lives in myaccount.brandverita.io.
COST_PER_IMAGE = 0.04

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
            detail="dispatch_failed: the product scene provider is not available.",
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
    print(f"wp2_stage job={job_id} step={name} {extra}".rstrip())


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
        # Never echo any part of the credential, present or absent.
        raise RuntimeError(
            f"provider_credential_missing: BFL_API_KEY absent (secret {SECRET_NAME})"
        )
    return key


def _normalise_to_preset(data: bytes, width: int, height: int) -> bytes:
    """Cover-fit to the exact preset size. BFL returns an aspect ratio, not a
    pixel size, so the API contract is enforced here rather than trusted."""
    from PIL import Image, ImageOps

    image = Image.open(io.BytesIO(data))
    image.load()
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGB")
    if (image.width, image.height) != (width, height):
        image = ImageOps.fit(
            image, (width, height), method=Image.LANCZOS, centering=(0.5, 0.5)
        )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _call_bfl(
    *, job_id: str, image_bytes: bytes, content_type: str, instruction: str, preset: str
) -> dict[str, Any]:
    """Submit + poll + fetch, entirely server-side. Returns provider bytes and meta."""
    import httpx

    import scene_presets

    key = _api_key()
    headers = {"x-key": key, "Content-Type": "application/json"}
    payload = {
        "prompt": instruction,
        "input_image": base64.b64encode(image_bytes).decode(),
        "aspect_ratio": scene_presets.aspect_ratio(preset),
        "output_format": "png",
        "prompt_upsampling": False,
        "safety_tolerance": 2,
    }

    with httpx.Client(timeout=SUBMIT_TIMEOUT_S) as client:
        response = client.post(f"{BFL_BASE_URL}/v1/{PROVIDER_MODEL}", json=payload, headers=headers)
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
                # Moderation and provider errors are distinct research signals.
                code = (
                    "provider_moderated"
                    if "Moderated" in status
                    else "provider_failed"
                )
                raise RuntimeError(f"{code}: BFL returned status {status}")

        sample_url = result.get("sample")
        if not sample_url:
            raise RuntimeError("provider_failed: BFL result carried no image")
        # Server-side fetch of the provider's delivery URL; it never reaches a browser.
        fetched = client.get(sample_url, timeout=120.0)
        if fetched.status_code >= 300 or not fetched.content:
            raise RuntimeError(f"provider_fetch_failed: BFL asset {fetched.status_code}")

    return {
        "image": fetched.content,
        "request_id": request_id,
        "provider_model": PROVIDER_MODEL,
    }


# --------------------------------------------------------------------------- #
# background execution
# --------------------------------------------------------------------------- #


def run_product_scene(job_id: str, user_id: str) -> None:
    import advanced
    import jobs
    import registry
    import scene_presets
    import supabase_rest

    queued_at = datetime.now(timezone.utc)
    job_dir = tempfile.mkdtemp(prefix=f"wp2-{job_id[:8]}-", dir="/tmp")
    temp_files: list[str] = []
    eval_row: dict[str, Any] = {
        "module": "product_scene",
        "job_id": job_id,
        "workflow_key": "product_scene",
        "workflow_version": "v1",
        "provider": PROVIDER,
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

        # 4 — instruction from the server preset table only.
        instruction = scene_presets.build_instruction(
            validated["scene_direction"], validated.get("background_style")
        )
        preset_fingerprint = scene_presets.fingerprint(
            validated["scene_direction"], validated.get("background_style")
        )
        width, height = scene_presets.resolve_output_preset(preset)

        # 5 + 6 — hosted call, bounded, then normalised to the exact preset size.
        dispatched_at = datetime.now(timezone.utc)
        eval_row["dispatched_at"] = _iso(dispatched_at)
        started = time.time()
        provider_result = _call_bfl(
            job_id=job_id,
            image_bytes=source_bytes,
            content_type=asset.get("content_type") or "image/png",
            instruction=instruction,
            preset=preset,
        )
        provider_latency_ms = int((time.time() - started) * 1000)
        eval_row["provider_latency_ms"] = provider_latency_ms
        eval_row["estimated_cost"] = COST_PER_IMAGE
        eval_row["provider_request_id"] = provider_result.get("request_id")
        _stage(
            job_id,
            "provider_returned",
            ms=provider_latency_ms,
            bytes=len(provider_result["image"]),
        )

        raw_path = os.path.join(job_dir, "provider.png")
        with open(raw_path, "wb") as handle:
            handle.write(provider_result["image"])
        temp_files.append(raw_path)

        output_png = _normalise_to_preset(provider_result["image"], width, height)
        output_path = os.path.join(job_dir, "output.png")
        with open(output_path, "wb") as handle:
            handle.write(output_png)
        temp_files.append(output_path)

        # 7 — validate → upload → hash → ready row.
        provenance = {
            "workflow": f"{row['key']}:{row['version']}",
            "provider": PROVIDER,
            "provider_model": provider_result.get("provider_model"),
            "provider_request_id": provider_result.get("request_id"),
            "output_preset": preset,
            "params": validated,
            "scene_preset": preset_fingerprint,
            "source_asset_sha256": asset.get("sha256"),
            "subject_preserved": "unverified",
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
                "width": width,
                "height": height,
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
                "source_region_verified": None,  # not byte-verifiable for this module
                "output_width": width,
                "output_height": height,
                "output_bytes": len(output_png),
            }
        )
        advanced.write_eval_run(eval_row)
        print(f"wp2_product_scene_completed job={job_id} preset={preset}")

    except Exception as exc:  # noqa: BLE001
        described = _describe(exc)
        print(f"wp2_product_scene_failed job={job_id} detail={described}")
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
            f"wp2_temp_cleanup job={job_id} files_removed={removed} "
            f"dir_exists={os.path.exists(job_dir)}"
        )
