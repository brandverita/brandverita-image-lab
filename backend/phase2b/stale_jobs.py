"""Stale-job sweep — closes orphaned non-terminal jobs.

A `modal deploy` replaces the API app and kills the background orchestrator
(`run_generation`) mid-flight. The GPU worker may have finished, but nothing
survives to upload the result or mark the job terminal, so the row sits at
e.g. `uploading_output` forever and the client polls until its own timeout
(2026-09-12 incident: job 4394c3b7 orphaned by a redeploy).

Pure helpers only — no Modal, FastAPI, or network imports — so the sweep is
testable offline and safe to call from any route. The polling GET endpoint is
the natural enforcement point: the client is already asking for the truth.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

TERMINAL_STATUSES = frozenset(
    {"completed", "failed", "canceled", "cancelled", "expired"}
)

# A non-terminal job whose row has not moved for this long is orphaned, not
# slow: warm renders finish in ~60s and even a cold worker start is minutes.
# The frontend gives up at 12 minutes, so 10 is always inside one session.
STALE_AFTER = timedelta(minutes=10)

STALE_ERROR_CODE = "job_stale"

_STALE_MESSAGE = (
    "This generation stopped reporting progress and was closed. "
    "Running it again is safe."
)


def parse_timestamp(raw: object) -> Optional[datetime]:
    """Parse a Supabase timestamptz value; None when absent or unreadable."""
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def stale_patch(row: dict, now: Optional[datetime] = None) -> Optional[dict]:
    """Return the expiry patch for a stale non-terminal job row, else None.

    `updated_at` is the heartbeat: the orchestrator touches the row on every
    state transition, so a row older than STALE_AFTER has no live owner.
    """
    if row.get("status") in TERMINAL_STATUSES:
        return None
    updated = parse_timestamp(row.get("updated_at"))
    if updated is None:
        return None
    current = now or datetime.now(timezone.utc)
    if current - updated <= STALE_AFTER:
        return None
    return {
        "status": "expired",
        "error_code": STALE_ERROR_CODE,
        "error_category": "orchestration",
        "error_message": _STALE_MESSAGE,
        "completed_at": current.isoformat(),
    }
