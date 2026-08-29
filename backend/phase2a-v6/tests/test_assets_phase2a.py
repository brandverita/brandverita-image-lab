"""
Phase 2A acceptance checks against the V6 STAGING API.

Run from `modal-project/phase1-v6-staging` with two distinct staging user tokens:

    export V6=https://brandverita--brandverita-api-v6-fastapi-app.modal.run
    export TOK_A="<user A supabase access token>"
    export TOK_B="<user B supabase access token>"
    export SUPABASE_URL="https://thspgkedjkiltrcimond.supabase.co"
    python tests/test_assets_phase2a.py

Requires: httpx, pillow. Read-only with respect to generation: it never submits a
Flux job (step 18 is a manual check).
"""

from __future__ import annotations

import io
import os
import struct
import sys
import uuid
import zlib

import httpx
from PIL import Image

V6 = os.environ["V6"].rstrip("/")
TOK_A = os.environ["TOK_A"]
TOK_B = os.environ["TOK_B"]

results: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> None:
    results.append((ok, label))
    print(("PASS  " if ok else "FAIL  ") + label)


def auth(token: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"} if token else {}


def png_bytes(w: int, h: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (30, 64, 175)).save(buf, format="PNG")
    return buf.getvalue()


def jpeg_bytes(w: int = 64, h: int = 64) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 200, 200)).save(buf, format="JPEG")
    return buf.getvalue()


def webp_bytes(w: int = 64, h: int = 64, animated: bool = False) -> bytes:
    buf = io.BytesIO()
    base = Image.new("RGB", (w, h), (10, 120, 90))
    if animated:
        base.save(buf, format="WEBP", save_all=True, append_images=[base, base], duration=100)
    else:
        base.save(buf, format="WEBP")
    return buf.getvalue()


def apng_bytes() -> bytes:
    buf = io.BytesIO()
    base = Image.new("RGB", (32, 32), (255, 0, 0))
    base.save(buf, format="PNG", save_all=True, append_images=[base, base], duration=100)
    return buf.getvalue()


def bomb_png() -> bytes:
    """Valid PNG header declaring 30000x30000 (>16.7M pixels) with tiny IDAT."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", 30000, 30000, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"\x00" * 16))
        + chunk(b"IEND", b"")
    )


def authorize(token: str, name: str, mime: str, size: int, key: str | None = None):
    return httpx.post(
        f"{V6}/v1/assets/upload-authorizations",
        headers=auth(token),
        json={
            "file_name": name,
            "content_type": mime,
            "file_size": size,
            "idempotency_key": key or str(uuid.uuid4()),
        },
        timeout=30,
    )


def put(url: str, data: bytes, mime: str) -> httpx.Response:
    return httpx.put(url, content=data, headers={"Content-Type": mime}, timeout=60)


def finalize(token: str, asset_id: str) -> httpx.Response:
    return httpx.post(f"{V6}/v1/assets/{asset_id}/finalize", headers=auth(token), timeout=120)


def error_code(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except Exception:
        return ""
    detail = body.get("detail", body)
    if isinstance(detail, dict):
        return detail.get("error_code", "")
    return ""


def upload_flow(token: str, data: bytes, name: str, mime: str):
    resp = authorize(token, name, mime, len(data))
    if resp.status_code != 200:
        return resp, None
    body = resp.json()
    put(body["upload_url"], data, mime)
    return finalize(token, body["asset_id"]), body["asset_id"]


# 1 — unauthenticated
check(authorize(None, "a.png", "image/png", 1000).status_code == 401, "1 no auth -> 401")

# 2 — disallowed mime
r = authorize(TOK_A, "a.gif", "image/gif", 1000)
check(r.status_code == 400 and error_code(r) == "invalid_file_type", "2 image/gif -> 400")

# 3 — extension / mime mismatch
r = authorize(TOK_A, "photo.png", "image/jpeg", 1000)
check(r.status_code == 400 and error_code(r) == "invalid_file_type", "3 ext/mime mismatch -> 400")

# 4 — declared oversize
r = authorize(TOK_A, "big.png", "image/png", 11 * 1024 * 1024)
check(r.status_code == 400 and error_code(r) == "file_too_large", "4 11 MB declared -> 400")

# 5 + 6 — authorization creates one pending row; repeat reuses it
key = str(uuid.uuid4())
first = authorize(TOK_A, "a.png", "image/png", 4096, key).json()
second = authorize(TOK_A, "a.png", "image/png", 4096, key).json()
check(
    first["asset_id"] == second["asset_id"] and second.get("reused") is True,
    "5/6 repeated authorization reuses the same pending asset",
)

# 7 — PNG / JPEG / WebP happy paths
for data, name, mime in (
    (png_bytes(320, 200), "ok.png", "image/png"),
    (jpeg_bytes(), "ok.jpg", "image/jpeg"),
    (webp_bytes(), "ok.webp", "image/webp"),
):
    resp, asset_id = upload_flow(TOK_A, data, name, mime)
    body = resp.json() if resp.status_code == 200 else {}
    ok = (
        resp.status_code == 200
        and body.get("status") == "ready"
        and len(body.get("sha256") or "") == 64
        and body.get("file_size") == len(data)
        and body.get("content_type") == mime
    )
    check(ok, f"7 {mime} upload + finalize -> ready")
    if mime == "image/png" and asset_id:
        ready_id = asset_id
        ready_meta = body

# 8 — repeated finalize on a ready asset
again = finalize(TOK_A, ready_id)
check(
    again.status_code == 200 and again.json().get("finalized_at") == ready_meta.get("finalized_at"),
    "8 repeated finalize is idempotent",
)

# 9 — corrupt bytes named .png
resp, corrupt_id = upload_flow(TOK_A, b"this is not an image" * 10, "bad.png", "image/png")
check(
    resp.status_code == 422 and error_code(resp) == "asset_validation_failed",
    "9 corrupt image -> 422 rejected",
)
check(error_code(finalize(TOK_A, corrupt_id)) == "asset_validation_failed", "9b re-finalize -> 409")

# 10 — dimension and pixel-count limits
for data, label in (
    (png_bytes(5000, 100), "width > 4096"),
    (png_bytes(100, 4097), "height > 4096"),
):
    resp, _ = upload_flow(TOK_A, data, "big.png", "image/png")
    check(resp.status_code == 422, f"10 {label} -> rejected")

# 11 — animated
for data, name, mime, label in (
    (webp_bytes(animated=True), "anim.webp", "image/webp", "animated WebP"),
    (apng_bytes(), "anim.png", "image/png", "APNG"),
):
    resp, _ = upload_flow(TOK_A, data, name, mime)
    check(resp.status_code == 422, f"11 {label} -> rejected")

# 12 — decompression bomb
resp, _ = upload_flow(TOK_A, bomb_png(), "bomb.png", "image/png")
check(resp.status_code == 422, "12 decompression bomb -> validation error")

# 13 — foreign payloads renamed .png
FOREIGN = {
    "svg": b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
    "gif": b"GIF89a" + b"\x00" * 32,
    "tiff": b"II*\x00" + b"\x00" * 32,
    "heic": b"\x00\x00\x00\x18ftypheic" + b"\x00" * 32,
    "pdf": b"%PDF-1.7\n" + b"\x00" * 32,
    "avif": b"\x00\x00\x00\x1cftypavif" + b"\x00" * 32,
}
for label, data in FOREIGN.items():
    resp, _ = upload_flow(TOK_A, data, "x.png", "image/png")
    check(resp.status_code == 422, f"13 {label} renamed .png -> rejected")

# 14 — reused signed upload authorization
body = authorize(TOK_A, "once.png", "image/png", 4096).json()
data = png_bytes(64, 64)
put(body["upload_url"], data, "image/png")
second_put = put(body["upload_url"], data, "image/png")
check(second_put.status_code >= 400, "14 reused signed upload URL is rejected by storage")

# 15 — cross-user isolation
check(finalize(TOK_B, ready_id).status_code == 404, "15 user B finalize A's asset -> 404")
check(
    httpx.get(f"{V6}/v1/assets/{ready_id}", headers=auth(TOK_B), timeout=30).status_code == 404,
    "15b user B GET A's asset -> 404",
)
b_list = httpx.get(f"{V6}/v1/assets?limit=24", headers=auth(TOK_B), timeout=30).json()
check(
    all(a["asset_id"] != ready_id for a in b_list.get("assets", [])),
    "15c A's asset absent from B's list",
)

# 16 — owner signed read works, raw path does not
owner_view = httpx.get(f"{V6}/v1/assets/{ready_id}", headers=auth(TOK_A), timeout=30).json()
signed = httpx.get(owner_view["read_url"], timeout=60)
check(signed.status_code == 200 and signed.content[:4] == b"\x89PNG", "16 signed thumbnail works")
raw = httpx.get(
    f"{os.environ.get('SUPABASE_URL', '').rstrip('/')}/storage/v1/object/public/generation-assets/x",
    timeout=30,
)
check(raw.status_code >= 400, "16b public bucket URL does not serve objects")

print("\n17 run in SQL: select public from storage.buckets where id='generation-assets'; -- expect false")
print("18 manual: one Flux V6 generation still completes; select count(*) from usage_ledger = 0;")
print("   and curl the V5 /health -> version v5")

failed = [label for ok, label in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} automated checks passed")
if failed:
    print("FAILED:", *failed, sep="\n  - ")
    sys.exit(1)
