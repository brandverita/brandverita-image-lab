"""
Phase 2B — Module C editorial layout adapter (hosted provider: BFL).

Same shape and custody rules as `bfl_product_scene.py`: this side owns assets,
storage, the database and the provider credential; the browser only ever sends
enum keys plus the headline/standfirst/label copy, which is typeset LOCALLY and
never reaches the provider instruction.

Order (fixed, mirrors WP2):
  1. re-run the framework gate at dispatch time
  2. download the source server-side, verify SHA256 before use
  3. build the provider instruction from SERVER-OWNED preset text only
     (editorial_presets): look + people + copy-zone wording
  4. call BFL with the image inlined as base64 — never a signed Supabase URL
  5. fetch the provider result server-side, normalise to the exact preset size
     -> this is the CLEAN PICTURE (no text on it)
  6. measure copy-zone usability on the clean picture (calm vs busy) and record
     it so a too-busy run can be reordered rather than shipped
  7. typeset the copy locally (editorial_typography) into a second asset
  8. validate → upload → hash → two `ready` output rows (clean + typeset);
     the job points at the typeset layout
  9. delete every temp file in `finally`
  10. update the job and write the transformation_eval_run

Provider key in the registry: `bfl_editorial_layout`.

Honest limitation, same as Module B and recorded per run: the provider
re-renders the whole frame, so `source_region_verified = null` and
`subject_preserved = "unverified"`. Human review in the eval rubric is the
gate, which is why the workflow stays research_only.
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

PROVIDER = "bfl_editorial_layout"
PROVIDER_FAMILY = "bfl"
PROVIDER_MODEL = "flux-kontext-pro"
BFL_BASE_URL = os.environ.get("BFL_BASE_URL", "https://api.bfl.ai")
SECRET_NAME = "bfl-research-2b"

SUBMIT_TIMEOUT_S = 60
POLL_INTERVAL_S = 2.0
PROVIDER_TIMEOUT_S = 300
# Research-stage cost estimate per image (USD). Recorded for metering only;
# enforcement lives in myaccount.brandverita.io.
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
            detail="dispatch_failed: the editorial layout provider is not available.",
        )
    call = _dispatcher.spawn(job_id=job["job_id"], user_id=job["user_id"])
    # The worker IS started at this point; a missing platform reference must not
    # be read as a dispatch failure (2026-09-22 false positive).
    return getattr(call, "object_id", None) or "spawned"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat()


def _stage(job_id: str, name: str, **fields: Any) -> None:
    extra = " ".join(f"{k}={v}" for k, v in fields.items())
    print(f"mc_stage job={job_id} step={name} {extra}".rstrip())


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


def _call_bfl(*, job_id: str, image_bytes: bytes, instruction: str, preset: str) -> dict[str, Any]:
    """Submit + poll + fetch, entirely server-side. Returns provider bytes and meta."""
    import httpx

    import editorial_presets

    key = _api_key()
    headers = {"x-key": key, "Content-Type": "application/json"}
    payload = {
        "prompt": instruction,
        "input_image": base64.b64encode(image_bytes).decode(),
        "aspect_ratio": editorial_presets.aspect_ratio(preset),
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


def run_editorial_layout(job_id: str, user_id: str) -> None:
    import advanced
    import jobs
    import registry
    import supabase_rest

    queued_at = datetime.now(timezone.utc)
    job_dir = tempfile.mkdtemp(prefix=f"mc-{job_id[:8]}-", dir="/tmp")
    temp_files: list[str] = []
    eval_row: dict[str, Any] = {
        "module": "editorial_layout",
        "job_id": job_id,
        "workflow_key": "editorial_layout",
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

        # 2 — server-side download, digest verified before use.
        _stage(job_id, "gate_passed", asset=asset["id"], preset=preset)
        source_bytes = advanced.acquire_source_bytes(asset)
        source_path = os.path.join(job_dir, "source.bin")
        with open(source_path, "wb") as handle:
            handle.write(source_bytes)
        temp_files.append(source_path)
        _stage(job_id, "source_downloaded", bytes=len(source_bytes))

        # 3 — instruction from the server preset table only. Copy (headline
        # etc.) is deliberately NOT part of it: text is typeset locally.
        import editorial_presets

        instruction = editorial_presets.compose_instruction(
            validated["look"], validated["people"], validated["copy_zone"], preset
        )
        preset_fingerprint = editorial_presets.fingerprint(
            validated["look"], validated["people"], validated["copy_zone"], preset
        )
        _stage(job_id, "preset_resolved", look=validated["look"])
        width, height = editorial_presets.resolve_output_preset(preset)
        zone = editorial_presets.zone_rect(validated["copy_zone"], width, height)

        # 4 + 5 — hosted call, bounded, then normalised to the exact preset size.
        dispatched_at = datetime.now(timezone.utc)
        eval_row["dispatched_at"] = _iso(dispatched_at)
        started = time.time()
        provider_result = _call_bfl(
            job_id=job_id,
            image_bytes=source_bytes,
            instruction=instruction,
            preset=preset,
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

        raw_path = os.path.join(job_dir, "provider.png")
        with open(raw_path, "wb") as handle:
            handle.write(provider_result["image"])
        temp_files.append(raw_path)

        clean_png = _normalise_to_preset(provider_result["image"], width, height)
        clean_path = os.path.join(job_dir, "clean.png")
        with open(clean_path, "wb") as handle:
            handle.write(clean_png)
        temp_files.append(clean_path)

        # 6 — copy-zone usability on the CLEAN picture, before any type goes on.
        import editorial_typography
        from PIL import Image

        clean_image = Image.open(io.BytesIO(clean_png))
        clean_image.load()
        usability = editorial_typography.zone_usability(clean_image, zone)
        _stage(job_id, "zone_measured", busy=usability["busy"], usable=usability["usable"])

        base_provenance = {
            "workflow": f"{row['key']}:{row['version']}",
            "provider": PROVIDER,
            "provider_model": provider_result.get("provider_model"),
            "provider_request_id": provider_result.get("request_id"),
            "output_preset": preset,
            "params": validated,
            "editorial_preset": preset_fingerprint,
            "source_asset_sha256": asset.get("sha256"),
            "subject_preserved": "unverified",
            "zone_usability": usability,
            "artifact_pins": row.get("artifact_pins") or [],
            "classification": "research_only/staging",
        }

        # 7 — clean picture stored first (layer 1 of the layered output).
        clean_asset = advanced.write_ready_output(
            data=clean_png,
            content_type="image/png",
            owner_id=user_id,
            job_id=job_id,
            source_asset_id=asset["id"],
            workflow_key=row["key"],
            workflow_version=row["version"],
            provenance={**base_provenance, "layer": "clean_picture"},
        )
        clean_asset_id = (
            clean_asset[0]["id"] if isinstance(clean_asset, list) else clean_asset["id"]
        )

        # 8 — local typesetting into the second layer. The model never drew
        # this text; every glyph comes from the bundled open-licence fonts.
        typeset_image, type_meta = editorial_typography.typeset(
            clean_image,
            zone,
            headline=validated["headline"],
            standfirst=validated["standfirst"],
            label=validated["label"],
            type_preset=validated["type_preset"],
        )
        buffer = io.BytesIO()
        typeset_image.save(buffer, format="PNG", optimize=True)
        typeset_png = buffer.getvalue()
        typeset_path = os.path.join(job_dir, "typeset.png")
        with open(typeset_path, "wb") as handle:
            handle.write(typeset_png)
        temp_files.append(typeset_path)

        layout_asset = advanced.write_ready_output(
            data=typeset_png,
            content_type="image/png",
            owner_id=user_id,
            job_id=job_id,
            source_asset_id=asset["id"],
            workflow_key=row["key"],
            workflow_version=row["version"],
            provenance={
                **base_provenance,
                "layer": "typeset_layout",
                "clean_picture_asset_id": clean_asset_id,
                "typeset": type_meta,
            },
        )
        layout_asset_id = (
            layout_asset[0]["id"] if isinstance(layout_asset, list) else layout_asset["id"]
        )

        completed_at = datetime.now(timezone.utc)
        jobs.patch_job(
            job_id,
            {
                "status": "completed",
                "progress": 100,
                "output_asset_id": layout_asset_id,
                "width": width,
                "height": height,
                "completed_at": _iso(completed_at),
            },
        )

        eval_row.update(
            {
                "status": "completed",
                "output_asset_id": layout_asset_id,
                "completed_at": _iso(completed_at),
                "total_latency_ms": int((completed_at - queued_at).total_seconds() * 1000),
                "cold_start": False,
                "source_region_verified": None,  # not byte-verifiable for this module
                "output_width": width,
                "output_height": height,
                "output_bytes": len(typeset_png),
                "variant_id": validated["look"],
                "provider_params": {
                    "look": validated["look"],
                    "people": validated["people"],
                    "copy_zone": validated["copy_zone"],
                    "type_preset": validated["type_preset"],
                    "instruction_sha256": preset_fingerprint["instruction_sha256"],
                    "zone_busy": usability["busy"],
                    "zone_usable": usability["usable"],
                    "type_ink": type_meta["ink"],
                    "type_scrim": type_meta["scrim"],
                    "type_contrast_ratio": type_meta["contrast_ratio"],
                },
            }
        )
        advanced.write_eval_run(eval_row)
        print(
            f"mc_editorial_completed job={job_id} preset={preset} "
            f"zone_usable={usability['usable']}"
        )

    except Exception as exc:  # noqa: BLE001
        described = _describe(exc)
        print(f"mc_editorial_failed job={job_id} detail={described}")
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
            f"mc_temp_cleanup job={job_id} files_removed={removed} "
            f"dir_exists={os.path.exists(job_dir)}"
        )
