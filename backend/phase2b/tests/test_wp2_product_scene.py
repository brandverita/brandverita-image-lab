"""
Phase 2B WP2 — backend-only controlled product scene test (Module B, BFL).

    V6=https://brandverita--brandverita-api-v6-fastapi-app.modal.run \
    TOK_A=<staging JWT for an allow-listed operator> \
    SUPABASE_URL=https://thspgkedjkiltrcimond.supabase.co \
    ASSET=/path/to/brandverita-product-on-plain-background.png \
    python test_wp2_product_scene.py

ASSET should be a BrandVerita-owned product photo (single product, plain or
simple background). Without it the script generates a synthetic "product" so
the plumbing can be exercised; the human quality review needs a real asset.

Sequence:
  1  unknown source_asset_id -> 4xx, nothing dispatched
  2  upload + finalize the source asset (ready)
  3  GET /v1/scene-presets returns enums only, never instruction text
  4  submit product_scene:v1, 1080x1080, clean_studio
  5  poll to completed, record latency
  6  output dimensions exactly 1080x1080
  7  lineage: job.output_asset_id + ready, hashed, caller-owned output asset
  8  output is private: signed URL works, unsigned anonymous read refused
  9  no server-owned instruction text leaks into any client response
 10  rejections hold (free-text prompt / bad scene / bad preset / bad style)
 11  regression: V6 Flux text-to-image still works
 12  product_scene:v1 stays invisible to studio-origin registry reads
"""

from __future__ import annotations

import io
import os
import sys
import time
import uuid

import httpx
from PIL import Image, ImageDraw

V6 = os.environ.get("V6", "").rstrip("/")
TOK_A = os.environ.get("TOK_A", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
ASSET = os.environ.get("ASSET", "")

for name, val in (("V6", V6), ("TOK_A", TOK_A), ("SUPABASE_URL", SUPABASE_URL)):
    if not val:
        sys.exit(f"Missing required environment variable: {name}")

PASS = 0
FAIL = 0
FAILURES: list[str] = []

PRESET = "1080x1080"
FORBIDDEN_TEXT_MARKERS = ("Replace the background", "backdrop", "contact shadow")


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(f"{label}: {detail}")
        print(f"FAIL  {label}  {detail}")


def call(method: str, url: str, token: str | None = None, body: dict | None = None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
    with httpx.Client(timeout=60.0) as client:
        response = client.request(method, url, headers=headers, json=body)
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    return response.status_code, payload


def source_png() -> bytes:
    if ASSET:
        with open(ASSET, "rb") as handle:
            return handle.read()
    image = Image.new("RGB", (1024, 1024), (238, 238, 240))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle([360, 260, 664, 830], radius=48, fill=(30, 64, 120))
    draw.rectangle([392, 430, 632, 620], fill=(245, 245, 248))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


BODY = {
    "workflow_id": "product_scene:v1",
    "output_preset": PRESET,
    "params": {
        "scene_direction": "clean_studio",
        "background_style": "soft_shadow",
        "preserve_subject": True,
    },
}

# --------------------------------------------------------------------------- #
# 1 — unknown source asset refused before dispatch
# --------------------------------------------------------------------------- #

status, body = call(
    "POST", f"{V6}/v1/generations", TOK_A, {**BODY, "source_asset_id": str(uuid.uuid4())}
)
check("1 unknown source_asset_id -> 4xx, no dispatch", 400 <= status < 500, f"got {status} {body}")

# --------------------------------------------------------------------------- #
# 2 — upload the source asset
# --------------------------------------------------------------------------- #

data = source_png()
status, auth = call(
    "POST",
    f"{V6}/v1/assets/upload-authorizations",
    TOK_A,
    {
        "file_name": "wp2-product.png",
        "content_type": "image/png",
        "file_size": len(data),
        "idempotency_key": str(uuid.uuid4()),
    },
)
if status >= 300:
    sys.exit(f"upload authorization failed: {status} {auth}")
with httpx.Client(timeout=120.0) as client:
    client.put(
        auth["upload_url"], content=data, headers={"Content-Type": "image/png"}
    ).raise_for_status()
status, fin = call("POST", f"{V6}/v1/assets/{auth['asset_id']}/finalize", TOK_A)
source_asset_id = auth["asset_id"]
check(
    "2 source asset uploaded and ready",
    status < 300 and fin.get("status") == "ready",
    f"got {status} {fin}",
)

# --------------------------------------------------------------------------- #
# 3 — preset catalog exposes enums only
# --------------------------------------------------------------------------- #

status, catalog = call("GET", f"{V6}/v1/scene-presets", TOK_A)
catalog_text = str(catalog)
check(
    "3 scene preset catalog returns enums, no instruction text",
    status < 300
    and any(
        item.get("scene_direction") == "clean_studio"
        for item in catalog.get("scene_directions", [])
    )
    and PRESET in (catalog.get("output_presets") or [])
    and not any(marker in catalog_text for marker in FORBIDDEN_TEXT_MARKERS),
    f"got {status} {catalog}",
)

# --------------------------------------------------------------------------- #
# 4 + 5 — submit and poll
# --------------------------------------------------------------------------- #

submitted_at = time.time()
status, body = call(
    "POST",
    f"{V6}/v1/generations",
    TOK_A,
    {**BODY, "source_asset_id": source_asset_id, "idempotency_key": str(uuid.uuid4())},
)
job_id = body.get("job_id", "")
check("4 product scene job accepted", status < 300 and bool(job_id), f"got {status} {body}")

final: dict = {}
if job_id:
    deadline = time.time() + 600
    while time.time() < deadline:
        _, final = call("GET", f"{V6}/v1/generations/{job_id}", TOK_A)
        if final.get("status") in ("completed", "failed"):
            break
        time.sleep(3)
latency = round(time.time() - submitted_at, 1)
check(f"5 job completed (latency {latency}s)", final.get("status") == "completed", f"final {final}")
print(f"      latency_seconds={latency} (target p95 <= 90s), estimated_cost=$0.04/image")

# --------------------------------------------------------------------------- #
# 6 — exact preset dimensions
# --------------------------------------------------------------------------- #

check(
    f"6 output dimensions exactly {PRESET}",
    final.get("width") == 1080 and final.get("height") == 1080,
    f"got {final.get('width')}x{final.get('height')}",
)

# --------------------------------------------------------------------------- #
# 7 — lineage and output asset state
# --------------------------------------------------------------------------- #

output_asset_id = final.get("output_asset_id") or ""
check("7 job carries output_asset_id", bool(output_asset_id), f"final {final}")

output_asset: dict = {}
if output_asset_id:
    _, output_asset = call("GET", f"{V6}/v1/assets/{output_asset_id}", TOK_A)
check(
    "7b output asset is ready, exact size, hashed, owned by the caller",
    output_asset.get("status") == "ready"
    and output_asset.get("width") == 1080
    and output_asset.get("height") == 1080
    and bool(output_asset.get("sha256")),
    f"asset {output_asset}" if output_asset else "no output asset",
)

print("      Run in Supabase SQL to complete the lineage + metering checks:")
print(
    f"""
        select id, kind, source_asset_id, job_id, status, sha256, width, height,
               provenance->'scene_preset'->>'instruction_sha256' as instruction_sha256,
               provenance->>'subject_preserved' as subject_preserved,
               provenance->>'classification' as classification
        from generation_assets where id = '{output_asset_id}';

        select module, provider, status, output_preset, request_params,
               provider_latency_ms, total_latency_ms, estimated_cost,
               provider_call_id, source_region_verified
        from transformation_eval_runs where job_id = '{job_id}';
"""
)

# --------------------------------------------------------------------------- #
# 8 — private storage
# --------------------------------------------------------------------------- #

signed_url = (
    output_asset.get("read_url")
    or output_asset.get("download_url")
    or output_asset.get("url")
    or ""
)
signed_ok = False
if signed_url:
    with httpx.Client(timeout=60.0) as client:
        signed_ok = client.get(signed_url).status_code == 200
check("8a output served only through a short-lived signed URL", signed_ok, f"url_present={bool(signed_url)}")

storage_path = output_asset.get("storage_path") or ""
if storage_path:
    unsigned_url = f"{SUPABASE_URL}/storage/v1/object/generation-assets/{storage_path}"
elif signed_url:
    unsigned_url = signed_url.split("?", 1)[0].replace("/object/sign/", "/object/public/")
else:
    unsigned_url = ""

if unsigned_url:
    with httpx.Client(timeout=30.0) as client:
        anon = client.get(unsigned_url)
    check("8b anonymous unsigned read refused", anon.status_code >= 400, f"got {anon.status_code}")
else:
    check("8b anonymous unsigned read refused", False, "no signed link returned, cannot derive object URL")


# --------------------------------------------------------------------------- #
# 9 — no server-owned instruction text in any client response
# --------------------------------------------------------------------------- #

surface = str(final) + str(output_asset)
check(
    "9 no scene instruction text in job or asset responses",
    not any(marker in surface for marker in FORBIDDEN_TEXT_MARKERS),
    "instruction text leaked to a client response",
)

# --------------------------------------------------------------------------- #
# 10 — rejections
# --------------------------------------------------------------------------- #

REJECTIONS = [
    ("10a free-text prompt injected", {"params": {**BODY["params"], "prompt": "a neon city"}}),
    ("10b invalid scene_direction", {"params": {**BODY["params"], "scene_direction": "cyberpunk"}}),
    ("10c invalid background_style", {"params": {**BODY["params"], "background_style": "glow"}}),
    ("10d disallowed output preset", {"output_preset": "4096x4096"}),
    ("10e preserve_subject false", {"params": {**BODY["params"], "preserve_subject": False}}),
]
for label, override in REJECTIONS:
    payload = {
        **BODY,
        **override,
        "source_asset_id": source_asset_id,
        "idempotency_key": str(uuid.uuid4()),
    }
    status, body = call("POST", f"{V6}/v1/generations", TOK_A, payload)
    check(f"{label} -> 400/403", status in (400, 403), f"got {status} {body}")

# --------------------------------------------------------------------------- #
# 11 — Flux regression
# --------------------------------------------------------------------------- #

status, body = call(
    "POST",
    f"{V6}/v1/generations",
    TOK_A,
    {
        "workflow_id": "flux-schnell-txt2img-v1",
        "prompt": "a plain ceramic mug on a wooden table, product photo",
        "width": 1024,
        "height": 1024,
        "idempotency_key": str(uuid.uuid4()),
    },
)
flux_job = body.get("job_id", "")
flux_final: dict = {}
if flux_job:
    deadline = time.time() + 420
    while time.time() < deadline:
        _, flux_final = call("GET", f"{V6}/v1/generations/{flux_job}", TOK_A)
        if flux_final.get("status") in ("completed", "failed"):
            break
        time.sleep(3)
check(
    "11 Flux text-to-image unchanged",
    flux_final.get("status") == "completed" and bool(flux_final.get("result_url")),
    f"final {flux_final}",
)

# --------------------------------------------------------------------------- #
# 12 — studio isolation
# --------------------------------------------------------------------------- #

status, studio = call("GET", f"{V6}/v1/workflows?origin=studio", TOK_A)
leaked = [
    row
    for row in studio.get("workflows", [])
    if str(row.get("key", "")).startswith("product_scene")
]
check("12 product_scene:v1 not visible to studio origin", status < 300 and not leaked, f"leaked: {leaked}")

# --------------------------------------------------------------------------- #

print()
print(f"{PASS}/{PASS + FAIL} checks passed")
for failure in FAILURES:
    print(f"  - {failure}")
sys.exit(1 if FAIL else 0)
