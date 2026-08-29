"""
Phase 2A — Generation asset foundation (STAGING ONLY).

Drop this file next to `api.py` in `modal-project/phase1-v6-staging/` and mount
the router (see README-integration.md). It is deliberately self-contained: it
talks to Supabase over REST with the service-role key and does not depend on the
internal signatures of `supabase_rest.py`, so it can be added without touching
existing V6 modules.

Security invariants:
  * every endpoint requires a JWKS-verified staging JWT (injected dependency)
  * ownership is re-checked server-side on every read/finalize/sign
  * the browser never receives service keys, bucket policies, or raw tokens;
    the only browser write path is one short-lived signed upload URL scoped to
    one exact object path
  * browser-declared metadata is never trusted: magic bytes, real decoded
    format, dimensions, pixel count, animation and size are all re-validated
  * nothing here creates output assets, ledger rows, or touches generation.
"""

from __future__ import annotations

import hashlib
import io
import os
import uuid
import warnings
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from PIL import Image
from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Limits (server-authoritative)
# --------------------------------------------------------------------------- #

BUCKET = "generation-assets"
MAX_FILE_BYTES = 10 * 1024 * 1024          # 10 MB
MAX_WIDTH = 4096
MAX_HEIGHT = 4096
MAX_PIXELS = 16_777_216
PENDING_TTL = timedelta(minutes=30)
READY_TTL = timedelta(days=30)
UPLOAD_URL_TTL_SECONDS = int(PENDING_TTL.total_seconds())
READ_URL_TTL_SECONDS = 300

ALLOWED: dict[str, tuple[str, tuple[str, ...]]] = {
    # declared mime -> (Pillow format, allowed lowercase extensions)
    "image/png": ("PNG", ("png",)),
    "image/jpeg": ("JPEG", ("jpg", "jpeg")),
    "image/webp": ("WEBP", ("webp",)),
}
CANONICAL_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}

# Decompression bombs must raise, not warn.
warnings.simplefilter("error", Image.DecompressionBombWarning)
Image.MAX_IMAGE_PIXELS = MAX_PIXELS

# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #

ERROR_STATUS = {
    "invalid_file_type": 400,
    "file_too_large": 400,
    "asset_not_found": 404,
    "asset_not_owned": 404,   # deliberately indistinguishable from not-found
    "asset_not_ready": 409,
    "asset_validation_failed": 422,
    "storage_unavailable": 503,
}


def api_error(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=ERROR_STATUS.get(code, 400),
        detail={"error_code": code, "error_message": message},
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Supabase service-role REST (server-side only)
# --------------------------------------------------------------------------- #


def _supabase_base() -> str:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    if not url:
        raise api_error("storage_unavailable", "Storage backend is not configured.")
    return url


def _service_headers() -> dict[str, str]:
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not key:
        raise api_error("storage_unavailable", "Storage backend is not configured.")
    return {"apikey": key, "Authorization": f"Bearer {key}"}


def _client() -> httpx.Client:
    return httpx.Client(timeout=30.0)


def _rest(method: str, path: str, **kwargs: Any) -> httpx.Response:
    headers = {**_service_headers(), **kwargs.pop("headers", {})}
    with _client() as client:
        return client.request(method, f"{_supabase_base()}{path}", headers=headers, **kwargs)


def table_insert(row: dict[str, Any]) -> dict[str, Any]:
    resp = _rest(
        "POST",
        "/rest/v1/generation_assets",
        json=row,
        headers={"Content-Type": "application/json", "Prefer": "return=representation"},
    )
    if resp.status_code >= 300:
        raise api_error("storage_unavailable", "Could not record the asset. Please retry.")
    return resp.json()[0]


def table_patch(asset_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    resp = _rest(
        "PATCH",
        f"/rest/v1/generation_assets?id=eq.{asset_id}",
        json=patch,
        headers={"Content-Type": "application/json", "Prefer": "return=representation"},
    )
    if resp.status_code >= 300 or not resp.json():
        raise api_error("storage_unavailable", "Could not update the asset. Please retry.")
    return resp.json()[0]


def table_select(query: str) -> list[dict[str, Any]]:
    resp = _rest("GET", f"/rest/v1/generation_assets?{query}")
    if resp.status_code >= 300:
        raise api_error("storage_unavailable", "Could not read the asset. Please retry.")
    return resp.json()


def storage_signed_upload_url(path: str) -> str:
    resp = _rest(
        "POST",
        f"/storage/v1/object/upload/sign/{BUCKET}/{path}",
        json={"expiresIn": UPLOAD_URL_TTL_SECONDS},
        headers={"Content-Type": "application/json"},
    )
    if resp.status_code >= 300:
        raise api_error("storage_unavailable", "Could not authorize the upload. Please retry.")
    signed = resp.json().get("url") or ""
    if not signed:
        raise api_error("storage_unavailable", "Could not authorize the upload. Please retry.")
    return f"{_supabase_base()}/storage/v1{signed if signed.startswith('/') else '/' + signed}"


def storage_signed_read_url(path: str, expires_in: int = READ_URL_TTL_SECONDS) -> str:
    resp = _rest(
        "POST",
        f"/storage/v1/object/sign/{BUCKET}/{path}",
        json={"expiresIn": expires_in},
        headers={"Content-Type": "application/json"},
    )
    if resp.status_code >= 300:
        raise api_error("storage_unavailable", "Could not create a preview link. Please retry.")
    signed = resp.json().get("signedURL") or ""
    if not signed:
        raise api_error("storage_unavailable", "Could not create a preview link. Please retry.")
    return f"{_supabase_base()}/storage/v1{signed if signed.startswith('/') else '/' + signed}"


def storage_download(path: str) -> Optional[bytes]:
    resp = _rest("GET", f"/storage/v1/object/{BUCKET}/{path}")
    if resp.status_code == 404:
        return None
    if resp.status_code >= 300:
        raise api_error("storage_unavailable", "Storage is temporarily unavailable.")
    return resp.content


def storage_delete(path: str) -> None:
    try:
        _rest("DELETE", f"/storage/v1/object/{BUCKET}/{path}")
    except HTTPException:
        pass  # best effort: the row is already marked rejected


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def sniff_magic(data: bytes) -> Optional[str]:
    """Returns the real mime for the three allowed formats, else None."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None  # SVG, GIF, TIFF, HEIC, PDF, AVIF, BMP, ICO, zip, anything else


class ValidationResult(BaseModel):
    content_type: str
    width: int
    height: int
    file_size: int
    sha256: str


def validate_image(data: bytes, declared_mime: str) -> ValidationResult:
    size = len(data)
    if size == 0:
        raise api_error("asset_validation_failed", "The uploaded file is empty.")
    if size > MAX_FILE_BYTES:
        raise api_error("file_too_large", "The uploaded file exceeds the 10 MB limit.")

    real_mime = sniff_magic(data)
    if real_mime is None or real_mime != declared_mime:
        raise api_error(
            "asset_validation_failed",
            "The file contents are not a valid PNG, JPEG or WebP image matching the declared type.",
        )

    expected_format = ALLOWED[declared_mime][0]
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
        with Image.open(io.BytesIO(data)) as img:
            if img.format != expected_format:
                raise api_error("asset_validation_failed", "The image format could not be verified.")
            if getattr(img, "n_frames", 1) > 1 or bool(img.info.get("is_animated")):
                raise api_error("asset_validation_failed", "Animated images are not supported.")
            width, height = int(img.width), int(img.height)
            img.load()
    except HTTPException:
        raise
    except Image.DecompressionBombWarning:
        raise api_error("asset_validation_failed", "The image is too large to process safely.")
    except Exception:
        raise api_error("asset_validation_failed", "The image could not be decoded.")

    if not (1 <= width <= MAX_WIDTH) or not (1 <= height <= MAX_HEIGHT):
        raise api_error(
            "asset_validation_failed",
            f"Image dimensions must be between 1 and {MAX_WIDTH} px on each side.",
        )
    if width * height > MAX_PIXELS:
        raise api_error("asset_validation_failed", "The image exceeds the maximum pixel count.")

    return ValidationResult(
        content_type=real_mime,
        width=width,
        height=height,
        file_size=size,
        sha256=hashlib.sha256(data).hexdigest(),
    )


# --------------------------------------------------------------------------- #
# Request / response models
# --------------------------------------------------------------------------- #


class UploadAuthorizationRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    content_type: str
    file_size: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=64)


def _safe_asset(row: dict[str, Any], signed_url: Optional[str] = None) -> dict[str, Any]:
    """Only user-safe fields. No bucket internals beyond the bucket name."""
    out = {
        "asset_id": row["id"],
        "status": row["status"],
        "kind": row["kind"],
        "content_type": row.get("content_type"),
        "file_size": row.get("file_size"),
        "width": row.get("width"),
        "height": row.get("height"),
        "sha256": row.get("sha256"),
        "created_at": row.get("created_at"),
        "finalized_at": row.get("finalized_at"),
        "expires_at": row.get("expires_at"),
    }
    if signed_url:
        out["read_url"] = signed_url
        out["read_url_expires_in"] = READ_URL_TTL_SECONDS
    return out


def _owned_row(asset_id: str, user_id: str) -> dict[str, Any]:
    try:
        uuid.UUID(asset_id)
    except ValueError:
        raise api_error("asset_not_found", "This asset could not be found.")
    rows = table_select(f"id=eq.{asset_id}&select=*")
    if not rows:
        raise api_error("asset_not_found", "This asset could not be found.")
    row = rows[0]
    if row["owner_id"] != user_id or row.get("deleted_at"):
        raise api_error("asset_not_found", "This asset could not be found.")
    return row


# --------------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------------- #


def build_assets_router(current_user_id: Callable[..., str]) -> APIRouter:
    """`current_user_id` is the existing V6 JWKS auth dependency returning the
    verified `sub` claim. Passing it in keeps identity logic in one place."""

    router = APIRouter(prefix="/v1/assets", tags=["assets"])

    @router.post("/upload-authorizations")
    def create_upload_authorization(
        payload: UploadAuthorizationRequest,
        user_id: str = Depends(current_user_id),
    ) -> dict[str, Any]:
        declared = (payload.content_type or "").lower().strip()
        if declared not in ALLOWED:
            raise api_error("invalid_file_type", "Only PNG, JPEG and WebP images are allowed.")
        ext = payload.file_name.rsplit(".", 1)[-1].lower() if "." in payload.file_name else ""
        if ext not in ALLOWED[declared][1]:
            raise api_error(
                "invalid_file_type",
                "The file extension does not match the declared image type.",
            )
        if payload.file_size > MAX_FILE_BYTES:
            raise api_error("file_too_large", "Images must be 10 MB or smaller.")

        now = _now()

        # Idempotent retry: reuse an existing pending row instead of duplicating.
        existing = table_select(
            f"owner_id=eq.{user_id}&idempotency_key=eq.{payload.idempotency_key}&select=*"
        )
        if existing:
            row = existing[0]
            status = row["status"]
            if status == "ready":
                return {**_safe_asset(row), "already_finalized": True}
            expires_at = row.get("expires_at")
            expired = bool(expires_at and datetime.fromisoformat(expires_at) <= now)
            if status == "pending_upload" and not expired:
                return {
                    "asset_id": row["id"],
                    "upload_url": storage_signed_upload_url(row["storage_path"]),
                    "method": "PUT",
                    "content_type": declared,
                    "expires_in": UPLOAD_URL_TTL_SECONDS,
                    "max_file_size": MAX_FILE_BYTES,
                    "reused": True,
                }
            if status == "rejected":
                raise api_error(
                    "asset_validation_failed",
                    "This upload was already rejected. Start a new upload.",
                )
            raise api_error(
                "asset_not_ready",
                "This upload authorization is no longer valid. Start a new upload.",
            )

        asset_id = str(uuid.uuid4())
        path = f"{user_id}/{asset_id}/original.{CANONICAL_EXT[declared]}"
        row = table_insert(
            {
                "id": asset_id,
                "owner_id": user_id,
                "bucket": BUCKET,
                "storage_path": path,
                "kind": "input",
                "status": "pending_upload",
                "idempotency_key": payload.idempotency_key,
                "expires_at": _iso(now + PENDING_TTL),
                "provenance": {
                    "source": "image_lab_asset_test",
                    "declared_content_type": declared,
                    "declared_file_size": payload.file_size,
                    "declared_extension": ext,
                },
            }
        )
        return {
            "asset_id": row["id"],
            "upload_url": storage_signed_upload_url(path),
            "method": "PUT",
            "content_type": declared,
            "expires_in": UPLOAD_URL_TTL_SECONDS,
            "max_file_size": MAX_FILE_BYTES,
            "reused": False,
        }

    @router.post("/{asset_id}/finalize")
    def finalize_asset(asset_id: str, user_id: str = Depends(current_user_id)) -> dict[str, Any]:
        row = _owned_row(asset_id, user_id)
        status = row["status"]

        if status == "ready":
            return _safe_asset(row)  # idempotent: no re-download, no mutation
        if status == "rejected":
            reason = (row.get("provenance") or {}).get("rejection_reason", "validation failed")
            raise api_error("asset_validation_failed", f"This asset was rejected ({reason}).")
        if status in ("deleted", "expired"):
            raise api_error("asset_not_found", "This asset could not be found.")
        if status != "pending_upload":
            raise api_error("asset_not_ready", "This asset cannot be finalized.")

        data = storage_download(row["storage_path"])
        if data is None:
            raise api_error("asset_validation_failed", "No uploaded file was found for this asset.")

        declared = (row.get("provenance") or {}).get("declared_content_type", "")
        try:
            result = validate_image(data, declared)
        except HTTPException as exc:
            code = "asset_validation_failed"
            if isinstance(exc.detail, dict):
                code = exc.detail.get("error_code", code)
                message = exc.detail.get("error_message", "validation failed")
            else:
                message = "validation failed"
            table_patch(
                asset_id,
                {
                    "status": "rejected",
                    "provenance": {
                        **(row.get("provenance") or {}),
                        "rejection_reason": code,
                        "rejection_detail": message,
                    },
                },
            )
            storage_delete(row["storage_path"])
            raise

        now = _now()
        updated = table_patch(
            asset_id,
            {
                "status": "ready",
                "content_type": result.content_type,
                "file_size": result.file_size,
                "width": result.width,
                "height": result.height,
                "sha256": result.sha256,
                "finalized_at": _iso(now),
                "expires_at": _iso(now + READY_TTL),
            },
        )
        return _safe_asset(updated)

    @router.get("/{asset_id}")
    def get_asset(asset_id: str, user_id: str = Depends(current_user_id)) -> dict[str, Any]:
        row = _owned_row(asset_id, user_id)
        if row["status"] != "ready":
            raise api_error("asset_not_ready", "This asset is not ready yet.")
        return _safe_asset(row, storage_signed_read_url(row["storage_path"]))

    @router.get("")
    def list_assets(limit: int = 12, user_id: str = Depends(current_user_id)) -> dict[str, Any]:
        limit = max(1, min(int(limit), 24))
        rows = table_select(
            f"owner_id=eq.{user_id}&kind=eq.input&status=eq.ready&deleted_at=is.null"
            f"&order=created_at.desc&limit={limit}&select=*"
        )
        return {
            "assets": [
                _safe_asset(row, storage_signed_read_url(row["storage_path"])) for row in rows
            ]
        }

    return router
