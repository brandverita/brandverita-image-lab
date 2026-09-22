"""Dispatch hand-off tests — pure, offline, no API or provider calls.

Guards the 2026-09-21 fix (an `async def` hand-off silently dispatching nothing)
AND the 2026-09-22 regression it caused (hosted modules returning no platform
reference were wrongly failed with dispatch_failed).

Run:  python backend/phase2b/tests/test_dispatch_guard.py
"""

import inspect
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Offline stub: the adapters import fastapi only for HTTPException.
if "fastapi" not in sys.modules:
    stub = types.ModuleType("fastapi")

    class HTTPException(Exception):
        def __init__(self, status_code: int = 500, detail: str = ""):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    stub.HTTPException = HTTPException  # type: ignore[attr-defined]
    sys.modules["fastapi"] = stub

failures: list[str] = []


def check(name: str, condition: bool) -> None:
    if condition:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name}")
        failures.append(name)


class _CallNoId:
    """A platform call handle that exposes no object_id."""


class _CallWithId:
    object_id = "fc-01ABCDEF"


class _Dispatcher:
    def __init__(self, call):
        self._call = call

    def spawn(self, **_kwargs):
        return self._call


JOB = {"job_id": "job-1", "user_id": "user-1"}

MODULES = [
    ("bfl_outpaint", "adapters.bfl_outpaint"),
    ("bfl_product_scene", "adapters.bfl_product_scene"),
    ("bfl_editorial_layout", "adapters.bfl_editorial_layout"),
    ("modal_research_outpaint", "adapters.modal_research_outpaint"),
]

for label, module_path in MODULES:
    mod = __import__(module_path, fromlist=["submit_generation", "set_dispatcher"])

    check(f"{label}: hand-off is synchronous", not inspect.iscoroutinefunction(mod.submit_generation))

    mod.set_dispatcher(_Dispatcher(_CallWithId()))
    ref = mod.submit_generation(JOB, {}, {})
    check(f"{label}: returns the platform reference", ref == "fc-01ABCDEF")

    mod.set_dispatcher(_Dispatcher(_CallNoId()))
    ref = mod.submit_generation(JOB, {}, {})
    check(
        f"{label}: falls back to a usable reference when none is exposed",
        isinstance(ref, str) and ref.strip() != "",
    )

    mod.set_dispatcher(None)


# --- the api.py guard shape, replicated exactly ------------------------------ #
def guard(provider_ref):
    if inspect.isawaitable(provider_ref):
        if hasattr(provider_ref, "close"):
            provider_ref.close()
        raise RuntimeError("adapter_returned_awaitable")
    if isinstance(provider_ref, str) and not provider_ref.strip():
        raise RuntimeError("adapter_returned_empty_call_id")
    if provider_ref is None:
        return "spawned"
    if not isinstance(provider_ref, str):
        return str(provider_ref)
    return provider_ref


async def _coro():
    return "never-awaited"


check("guard: accepts a real reference", guard("fc-123") == "fc-123")
check("guard: accepts a missing reference", guard(None) == "spawned")

try:
    guard(_coro())
    check("guard: rejects an un-awaited coroutine", False)
except RuntimeError as exc:
    check("guard: rejects an un-awaited coroutine", "awaitable" in str(exc))

try:
    guard("   ")
    check("guard: rejects an empty reference", False)
except RuntimeError as exc:
    check("guard: rejects an empty reference", "empty_call_id" in str(exc))

print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("all dispatch guard checks passed")
