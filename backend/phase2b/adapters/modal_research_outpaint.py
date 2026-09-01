"""
Phase 2B WP1 — outpaint adapter (API side).

Runs inside the brandverita-api-v6 app, in a background Modal function. It owns
everything that touches assets, storage and the database; the research worker
only ever sees bytes.

Order, per requirement 4:
  1. re-run the WP0 gate (flags, ownership, readiness, expiry, params)
  2. download the source into a job-specific temp directory
  3. verify SHA256 before use
  4. build padded canvas + mask server-side
  5. run the approved graph on comfyui-research-worker-2b
  6. composite the original source pixels back unchanged
  7. verify exact source-region integrity
  8. delete every temp file in `finally`
  9. write the output to the private bucket only after validation
 10. create the output asset row with full lineage, then update the job and
     write the transformation_eval_run

Provider key in the registry: `modal_research_2b`.
"""

from __future__ import annotations

import io
import os
import random
import shutil
import tempfile
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Optional

PROVIDER = "modal_research_2b"
WORKER_APP = "comfyui-research-worker-2b"
WORKER_CLASS = "ResearchOutpaintWorker"
# Cold start (A10G alloc + ComfyUI boot) plus one graph run. Anything past this
# is a stuck worker, not slow generation.
WORKER_CALL_TIMEOUT_S = 900

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
            detail="dispatch_failed: the research worker is not available.",
        )
    call = _dispatcher.spawn(job_id=job["job_id"], user_id=job["user_id"])
    return getattr(call, "object_id", None)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat()


def _describe(exc: BaseException) -> str:
    """Server-side only: the most specific text we can get out of an exception.

    HTTPException carries its useful information in `.detail` (often a dict with
    error_code), and `str(exc)` on it is just the status code — which is how the
    first WP1 failure recorded only 'HTTPException' and told us nothing.
    """
    detail = getattr(exc, "detail", None)
    status = getattr(exc, "status_code", None)
    if detail is not None:
        text = f"{type(exc).__name__}({status}): {detail}"
    else:
        text = f"{type(exc).__name__}: {exc}"
    return text[:900]


def _stage(job_id: str, name: str, **fields: Any) -> None:
    extra = " ".join(f"{k}={v}" for k, v in fields.items())
    print(f"wp1_stage job={job_id} step={name} {extra}".rstrip())



def run_outpaint(job_id: str, user_id: str) -> None:
    """Background execution. Any failure marks the job failed and leaves no
    storage object and no asset row behind."""
    import modal
    from PIL import Image

    import advanced
    import jobs
    import outpaint_geometry
    import registry
    import supabase_rest

    queued_at = datetime.now(timezone.utc)
    job_dir = tempfile.mkdtemp(prefix=f"wp1-{job_id[:8]}-", dir="/tmp")
    temp_files: list[str] = []
    eval_row: dict[str, Any] = {
        "module": "outpaint",
        "job_id": job_id,
        "workflow_key": "outpaint",
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

        jobs.patch_job(job_id, {"status": "processing", "started_at": _iso(datetime.now(timezone.utc))})

        row = registry.resolve_workflow(job["workflow_id"], job.get("workflow_version"))
        params = job.get("request_params") or {}
        preset = job.get("output_preset") or ""

        # 1 — re-run the gate at dispatch time; a flag flipped off between
        # submit and dispatch must stop the job here.
        resolved = advanced.resolve_advanced_request(
            workflow_key=row["key"],
            workflow_version=row["version"],
            source_asset_id=job.get("source_asset_id"),
            output_preset=preset,
            params=params,
            user_id=user_id,
            environment=registry.ENVIRONMENT,
        )
        asset = resolved["asset"]
        eval_row.update(
            {
                "workflow_key": row["key"],
                "workflow_version": row["version"],
                "config_hash": row.get("config_hash"),
                "source_asset_id": asset["id"],
                "output_preset": preset,
                "request_params": resolved["request_params"],
                "license_ref": (row.get("artifact_pins") or [{}])[0].get("license")
                if row.get("artifact_pins")
                else None,
            }
        )

        # 2 + 3 — download into the job dir and verify the digest before use.
        source_bytes = advanced.acquire_source_bytes(asset)
        source_path = os.path.join(job_dir, "source.bin")
        with open(source_path, "wb") as handle:
            handle.write(source_bytes)
        temp_files.append(source_path)

        source_image = Image.open(io.BytesIO(source_bytes))
        source_image.load()

        # 4 — server-owned canvas + mask.
        validated = resolved["request_params"]
        scaled_source, placement = outpaint_geometry.plan(
            source=source_image,
            output_preset=preset,
            direction=validated["direction"],
            anchor=validated["anchor"],
        )
        canvas_png, mask_png = outpaint_geometry.build_canvas_and_mask(
            scaled_source, placement
        )
        for name, data in (("canvas.png", canvas_png), ("mask.png", mask_png)):
            path = os.path.join(job_dir, name)
            with open(path, "wb") as handle:
                handle.write(data)
            temp_files.append(path)

        # 5 — the approved graph on the isolated research worker.
        dispatched_at = datetime.now(timezone.utc)
        eval_row["dispatched_at"] = _iso(dispatched_at)
        seed = random.randint(0, 2**31 - 1)
        worker = modal.Cls.from_name(WORKER_APP, WORKER_CLASS)()
        started = time.time()
        # Bounded call. A blocking .remote() on a crash-looping worker hung one
        # job for the full 3600s function timeout with no diagnosable error;
        # spawn + get(timeout=...) fails the job fast with a real error code.
        call = worker.outpaint.spawn(canvas_png, mask_png, seed)
        try:
            result = call.get(timeout=WORKER_CALL_TIMEOUT_S)
        except TimeoutError as exc:  # modal raises builtin TimeoutError
            raise RuntimeError(
                f"worker_timeout: no result from {WORKER_APP} within "
                f"{WORKER_CALL_TIMEOUT_S}s"
            ) from exc
        provider_latency_ms = int((time.time() - started) * 1000)

        generated_png = result["image"]
        generated_path = os.path.join(job_dir, "generated.png")
        with open(generated_path, "wb") as handle:
            handle.write(generated_png)
        temp_files.append(generated_path)

        # 6 + 7 — composite the untouched source back, then prove it.
        output_png, verified = outpaint_geometry.composite_and_verify(
            generated_png=generated_png,
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

        # 9 + 10 — validate, upload, and only then create the ready row.
        provenance = {
            "workflow": f"{row['key']}:{row['version']}",
            "worker_app": WORKER_APP,
            "worker_version": result.get("worker_version"),
            "graph": result.get("graph"),
            "seed": seed,
            "output_preset": preset,
            "params": validated,
            "geometry": placement.as_provenance(),
            "source_asset_sha256": asset.get("sha256"),
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
                "worker_version": result.get("worker_version"),
                "completed_at": _iso(completed_at),
            },
        )

        eval_row.update(
            {
                "status": "completed",
                "output_asset_id": output_asset_id,
                "completed_at": _iso(completed_at),
                "provider_latency_ms": provider_latency_ms,
                "total_latency_ms": int((completed_at - queued_at).total_seconds() * 1000),
                "gpu_seconds": result.get("gpu_seconds"),
                "cold_start": provider_latency_ms > 120_000,
                "estimated_cost": round((result.get("gpu_seconds") or 0) * 0.000306, 6),
                "worker_version": result.get("worker_version"),
                "output_width": placement.canvas_width,
                "output_height": placement.canvas_height,
                "output_bytes": len(output_png),
            }
        )
        advanced.write_eval_run(eval_row)
        print(f"wp1_outpaint_completed job={job_id} verified={verified}")

    except Exception as exc:  # noqa: BLE001
        code = getattr(exc, "detail", None)
        print(f"wp1_outpaint_failed job={job_id} type={type(exc).__name__}")
        try:
            import jobs as _jobs

            _jobs.patch_job(
                job_id,
                {
                    "status": "failed",
                    "error_code": "transformation_failed",
                    "error_category": "worker",
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
                    "error_message": str(code) if isinstance(code, str) else type(exc).__name__,
                    "completed_at": _iso(datetime.now(timezone.utc)),
                }
            )
            _advanced.write_eval_run(eval_row)
        except Exception:  # noqa: BLE001
            pass

    finally:
        # 8 — nothing survives, success or failure.
        removed = 0
        for path in temp_files:
            try:
                os.unlink(path)
                removed += 1
            except OSError:
                pass
        shutil.rmtree(job_dir, ignore_errors=True)
        print(
            f"wp1_temp_cleanup job={job_id} files_removed={removed} "
            f"dir_exists={os.path.exists(job_dir)}"
        )
