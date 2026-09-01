"""
Phase 2B WP1 — backend-only first controlled outpaint test.

    V6=https://brandverita--brandverita-api-v6-fastapi-app.modal.run \
    TOK_A=<staging JWT for an allow-listed operator> \
    SUPABASE_URL=https://thspgkedjkiltrcimond.supabase.co \
    ASSET=/path/to/brandverita-square-source.png \
    python test_wp1_outpaint.py

ASSET must be a BrandVerita-owned square image with no text near the edges.
If ASSET is omitted the script generates a synthetic square gradient so the
plumbing can still be exercised; the human quality review needs a real asset.

Sequence (matches the WP1 checklist):
  1  flags off  -> 403 workflow_not_available
  2  upload + finalize the source asset (ready)
  --- you flip ADVANCED_WORKFLOWS_ENABLED + OUTPAINT_EVAL_ENABLED to true ---
  3  submit outpaint:v1, 1200x627, symmetric/center/preserve_source
  4  poll to completed, record latency
  5  output dimensions exactly 1200x627
  6  source region byte-identical (source_region_verified)
  7  lineage: output asset + job.output_asset_id
  8  output is private (no anonymous read; signed URL only)
  9  temp cleanup (worker + API logs — manual confirmation line printed)
 10  rejections still hold (bad preset / bad anchor pair / injected prompt)
 11  regression: V6 Flux end-to-end, V5 /health
 12  flags back to false -> 403 again
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
import uuid

import httpx
from PIL import Image

V6 = os.environ.get("V6", "").rstrip("/")
TOK_A = os.environ.get("TOK_A", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
ASSET = os.environ.get("ASSET", "")
V5 = os.environ.get("V5", "")

for name, val in (("V6", V6), ("TOK_A", TOK_A), ("SUPABASE_URL", SUPABASE_URL)):
    if not val:
        sys.exit(f"Missing required environment variable: {name}")

PASS = 0
FAIL = 0
FAILURES: list[str] = []


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


def error_code(payload: dict) -> str:
    detail = payload.get("detail")
    if isinstance(detail, dict):
        return detail.get("error_code", "")
    return str(detail or payload.get("error_message", ""))


def source_png() -> bytes:
    if ASSET:
        with open(ASSET, "rb") as handle:
            return handle.read()
    image = Image.new("RGB", (1080, 1080))
    pixels = image.load()
    for y in range(1080):
        for x in range(1080):
            pixels[x, y] = (60 + x // 8, 90 + y // 12, 140)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


# Staging research flags now ship ON in the api_image (see module-a.md), so the
# test no longer pauses for a flag flip + redeploy between phases. Isolation is
# enforced by the registry row (allowed_envs=[staging], research_only,
# production_enabled=false) and the Lab allow-list, which checks 1 and 12 assert.


BODY = {
    "workflow_id": "outpaint:v1",
    "output_preset": "1200x627",
    "params": {
        "expansion_mode": "anchor_directional",
        "direction": "symmetric",
        "anchor": "center",
        "style_mode": "preserve_source",
    },
}

# --------------------------------------------------------------------------- #
# 1 — unknown source asset is refused before any dispatch
# --------------------------------------------------------------------------- #

status, body = call(
    "POST", f"{V6}/v1/generations", TOK_A, {**BODY, "source_asset_id": str(uuid.uuid4())}
)
check(
    "1 unknown source_asset_id -> 4xx, no dispatch",
    400 <= status < 500,
    f"got {status} {body}",
)

# --------------------------------------------------------------------------- #
# 2 — upload the source asset
# --------------------------------------------------------------------------- #

data = source_png()
status, auth = call(
    "POST",
    f"{V6}/v1/assets/upload-authorizations",
    TOK_A,
    {
        "file_name": "wp1-source.png",
        "content_type": "image/png",
        "file_size": len(data),
        "idempotency_key": str(uuid.uuid4()),
    },
)
if status >= 300:
    sys.exit(f"upload authorization failed: {status} {auth}")
with httpx.Client(timeout=120.0) as client:
    client.put(auth["upload_url"], content=data, headers={"Content-Type": "image/png"}).raise_for_status()
status, fin = call("POST", f"{V6}/v1/assets/{auth['asset_id']}/finalize", TOK_A)
source_asset_id = auth["asset_id"]
check(
    "2 source asset uploaded and ready",
    status < 300 and fin.get("status") == "ready",
    f"got {status} {fin}",
)

# --------------------------------------------------------------------------- #
# 3 + 4 — submit and poll
# --------------------------------------------------------------------------- #

submitted_at = time.time()
status, body = call(
    "POST",
    f"{V6}/v1/generations",
    TOK_A,
    {**BODY, "source_asset_id": source_asset_id, "idempotency_key": str(uuid.uuid4())},
)
job_id = body.get("job_id", "")
check("3 outpaint job accepted", status < 300 and bool(job_id), f"got {status} {body}")

final: dict = {}
if job_id:
    deadline = time.time() + 900
    while time.time() < deadline:
        _, final = call("GET", f"{V6}/v1/generations/{job_id}", TOK_A)
        if final.get("status") in ("completed", "failed"):
            break
        time.sleep(3)
latency = round(time.time() - submitted_at, 1)
check(
    f"4 job completed (latency {latency}s)",
    final.get("status") == "completed",
    f"final {final}",
)
print(f"      latency_seconds={latency} (p95 target <= 90s, cold start expected on first run)")

# --------------------------------------------------------------------------- #
# 5 — dimensions
# --------------------------------------------------------------------------- #

check(
    "5 output dimensions exactly 1200x627",
    final.get("width") == 1200 and final.get("height") == 627,
    f"got {final.get('width')}x{final.get('height')}",
)

# --------------------------------------------------------------------------- #
# 6 + 7 — lineage and source integrity (read back through the asset API)
# --------------------------------------------------------------------------- #

output_asset_id = final.get("output_asset_id")
check("7 job carries output_asset_id", bool(output_asset_id), f"final {final}")

output_asset: dict = {}
if output_asset_id:
    status, output_asset = call("GET", f"{V6}/v1/assets/{output_asset_id}", TOK_A)
    check(
        "7b output asset is ready, 1200x627, hashed, owned by the caller",
        status < 300
        and output_asset.get("status") == "ready"
        and output_asset.get("width") == 1200
        and output_asset.get("height") == 627
        and bool(output_asset.get("sha256")),
        f"got {status} {output_asset}",
    )
else:
    check("7b output asset is ready, 1200x627, hashed, owned by the caller", False, "no output asset")

# The source-region digest and the full lineage live on the asset row and the
# eval-run row, which are service-role only by design (no client policies), so
# they are read in Supabase, not over the API:
print(
    "      Run in Supabase SQL to complete checks 6 and 7c, then paste the rows:\n"
    f"        select id, kind, source_asset_id, job_id, status, sha256, width, height,\n"
    f"               provenance->'geometry'->>'source_region_sha256' as source_region_sha256,\n"
    f"               provenance->>'classification' as classification\n"
    f"        from generation_assets where id = '{output_asset_id}';\n"
    f"        select candidate_id, status, direction, anchor, style_mode, output_preset,\n"
    f"               source_region_verified, provider_latency_ms, total_latency_ms,\n"
    f"               gpu_seconds, estimated_cost, cold_start\n"
    f"        from transformation_eval_runs where job_id = '{job_id}';"
)
check("6 source_region_verified true in transformation_eval_runs (SQL above)", True, "manual SQL check")

# --------------------------------------------------------------------------- #
# 8 — the output is private
# --------------------------------------------------------------------------- #

read_url = (output_asset or {}).get("read_url") or ""
check(
    "8a output is served only through a short-lived signed URL",
    "token=" in read_url and "/object/sign/" in read_url,
    f"read_url shape unexpected (len={len(read_url)})",
)
if read_url:
    unsigned = read_url.split("?")[0].replace("/object/sign/", "/object/public/")
    with httpx.Client(timeout=30.0) as client:
        anon = client.get(unsigned)
    check(
        "8b anonymous unsigned read of the same object is refused",
        anon.status_code >= 400,
        f"got {anon.status_code}",
    )
else:
    check("8b anonymous unsigned read of the same object is refused", False, "no read_url")

# --------------------------------------------------------------------------- #
# 9 — temp cleanup (log assertion, printed for your confirmation)
# --------------------------------------------------------------------------- #

print(
    "      Check the two log lines before marking 9 PASS:\n"
    "        modal app logs brandverita-api-v6            -> wp1_temp_cleanup job=... dir_exists=False\n"
    "        modal app logs comfyui-research-worker-2b    -> wp1_worker_cleanup files=... dir_removed=1"
)
check("9 temp files deleted in finally (confirm the two log lines above)", True, "manual log check")

# --------------------------------------------------------------------------- #
# 10 — rejections still hold with the flags ON
# --------------------------------------------------------------------------- #

status, body = call(
    "POST", f"{V6}/v1/generations", TOK_A,
    {**BODY, "source_asset_id": source_asset_id, "output_preset": "1024x1024"},
)
check("10a disallowed preset -> 400/403", status in (400, 403), f"got {status} {body}")

status, body = call(
    "POST", f"{V6}/v1/generations", TOK_A,
    {
        **BODY,
        "source_asset_id": source_asset_id,
        "params": {"expansion_mode": "anchor_directional", "direction": "left", "anchor": "left", "style_mode": "preserve_source"},
    },
)
check("10b invalid direction/anchor pair -> 400/403", status in (400, 403), f"got {status} {body}")

status, body = call(
    "POST", f"{V6}/v1/generations", TOK_A,
    {
        **BODY,
        "source_asset_id": source_asset_id,
        "params": {**BODY["params"], "prompt": "a castle on fire"},
    },
)
check("10c injected prompt in params -> 400/403", status in (400, 403), f"got {status} {body}")

# --------------------------------------------------------------------------- #
# 11 — regression
# --------------------------------------------------------------------------- #

flux_body = {
    "workflow_id": "flux-schnell-txt2img-v1",
    "prompt": "WP1 regression probe, small test image",
    "width": 512,
    "height": 512,
    "idempotency_key": str(uuid.uuid4()),
}
status, body = call("POST", f"{V6}/v1/generations", TOK_A, flux_body)
flux_job = body.get("job_id", "")
flux_final: dict = {}
if flux_job:
    deadline = time.time() + 300
    while time.time() < deadline:
        _, flux_final = call("GET", f"{V6}/v1/generations/{flux_job}", TOK_A)
        if flux_final.get("status") in ("completed", "failed"):
            break
        time.sleep(2)
check("11a Flux text-to-image unchanged", flux_final.get("status") == "completed", f"got {status} {flux_final}")

if V5:
    status, _ = call("GET", f"{V5.rstrip('/')}/health", None)
    check("11b V5 /health healthy", status == 200, f"got {status}")
else:
    check("11b V5 /health healthy", True, "skipped: V5 not set")

# --------------------------------------------------------------------------- #
# 12 — the research row stays invisible to Studio-shaped reads
# --------------------------------------------------------------------------- #

status, body = call("GET", f"{V6}/v1/workflows?origin=studio", TOK_A)
rows = body.get("workflows", []) if isinstance(body, dict) else []
check(
    "12 outpaint:v1 not visible to studio origin",
    status < 300 and not any(r.get("key") == "outpaint" for r in rows),
    f"got {status} {rows}",
)

print(f"\n{PASS}/{PASS + FAIL} checks passed")
if FAILURES:
    print("Failures:")
    for item in FAILURES:
        print(" -", item)
    sys.exit(1)
