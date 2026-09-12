"""Stale-job sweep tests — pure, offline, no API or provider calls.

Run:  python backend/phase2b/tests/test_stale_jobs.py
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import stale_jobs as sj  # noqa: E402

failures: list[str] = []


def check(name: str, condition: bool) -> None:
    if condition:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name}")
        failures.append(name)


NOW = datetime(2026, 9, 12, 16, 10, tzinfo=timezone.utc)
FRESH = (NOW - timedelta(minutes=2)).isoformat()
STALE = (NOW - timedelta(minutes=11)).isoformat()

# Terminal rows are never touched.
for status in ("completed", "failed", "canceled", "cancelled", "expired"):
    check(
        f"terminal {status} untouched",
        sj.stale_patch({"status": status, "updated_at": STALE}, NOW) is None,
    )

# Every live non-terminal state is swept once stale.
for status in ("queued", "dispatching", "processing", "uploading_output"):
    patch = sj.stale_patch({"status": status, "updated_at": STALE}, NOW)
    check(
        f"stale {status} expires",
        patch is not None
        and patch["status"] == "expired"
        and patch["error_code"] == "job_stale"
        and patch["completed_at"] == NOW.isoformat(),
    )

# Fresh non-terminal rows are left alone.
check(
    "fresh processing untouched",
    sj.stale_patch({"status": "processing", "updated_at": FRESH}, NOW) is None,
)

# Boundary: exactly STALE_AFTER old is still alive (strictly older expires).
edge = (NOW - sj.STALE_AFTER).isoformat()
check(
    "exactly at threshold untouched",
    sj.stale_patch({"status": "processing", "updated_at": edge}, NOW) is None,
)

# Missing or unreadable timestamps never crash and never expire the job.
check("missing updated_at untouched", sj.stale_patch({"status": "queued"}, NOW) is None)
check(
    "bad updated_at untouched",
    sj.stale_patch({"status": "queued", "updated_at": "not-a-date"}, NOW) is None,
)

# Supabase returns both offset and naive-ish ISO; Z suffix parses.
check(
    "Z suffix parses",
    sj.stale_patch({"status": "queued", "updated_at": STALE.replace("+00:00", "Z")}, NOW)
    is not None,
)

# Default now= works without an explicit clock.
old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
check(
    "defaults to real clock",
    sj.stale_patch({"status": "uploading_output", "updated_at": old}) is not None,
)

if failures:
    print(f"\n{len(failures)} FAILURES")
    sys.exit(1)
print("\nAll stale-job sweep checks passed.")
