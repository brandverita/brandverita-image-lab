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

# Never-dispatched queued jobs close on the short clock (2026-09-21 incident):
# no modal_call_id means no worker was ever asked to run.
never = (NOW - timedelta(minutes=2)).isoformat()
patch = sj.stale_patch({"status": "queued", "queued_at": never, "updated_at": never}, NOW)
check(
    "never-dispatched queued fails fast",
    patch is not None
    and patch["status"] == "failed"
    and patch["error_code"] == "dispatch_never_started"
    and patch["error_category"] == "dispatch",
)

# created_at is the fallback heartbeat when queued_at is absent.
check(
    "never-dispatched falls back to created_at",
    (sj.stale_patch({"status": "queued", "created_at": never}, NOW) or {}).get("error_code")
    == "dispatch_never_started",
)

# A dispatched job is slow, not broken — it waits out the long clock instead.
check(
    "dispatched queued not fast-failed",
    sj.stale_patch(
        {"status": "queued", "modal_call_id": "fc-123", "queued_at": never, "updated_at": never},
        NOW,
    )
    is None,
)

# Inside the grace period nothing is closed.
check(
    "fresh queued untouched",
    sj.stale_patch(
        {"status": "queued", "queued_at": (NOW - timedelta(seconds=30)).isoformat()}, NOW
    )
    is None,
)

# Only queued rows take the fast path; a dispatching row is mid-flight.
check(
    "dispatching not fast-failed",
    sj.stale_patch({"status": "dispatching", "queued_at": never, "updated_at": never}, NOW)
    is None,
)

if failures:
    print(f"\n{len(failures)} FAILURES")
    sys.exit(1)
print("\nAll stale-job sweep checks passed.")
