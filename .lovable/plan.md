# Plan: Fix `ModuleNotFoundError: No module named 'supabase'` during `modal deploy api.py`

## Root cause (confirmed by reading the deployed api.py)

`modal deploy` imports the module **locally** (on your Mac) to introspect the app graph.
All module-level statements run in that local Python — including line 22:

```python
from supabase import Client, create_client
```

`supabase` is not installed in your local environment, so the import fails and aborts the
deploy before any container ever starts. The image's `pip_install("supabase")` only takes
effect at runtime inside the container; it cannot rescue the local import.

## Fix (recommended): make the supabase import lazy

Move the supabase import out of module scope and into the functions that actually use it.
Module-level code then only needs packages already present locally (`modal`, `fastapi`,
`pydantic` — all already imported fine). The container, which has `supabase` installed via
the image, resolves the import when the functions run.

Specific changes to `api.py`:

1. Delete the module-level line:
   ```python
   from supabase import Client, create_client
   ```
2. Replace the `Client` type hints (`def get_supabase_client() -> Client`,
   `def sign_output_path(supabase: Client, ...)`) with plain hints that don't require the
   import at module scope — either remove the return-type annotation on
   `get_supabase_client` and use `Any` (already importable from `typing`), or use string
   annotations. Simplest: drop the `Client` annotation and type the param as `Any`.
3. Inside `get_supabase_client()`, add:
   ```python
   from supabase import create_client
   return create_client(supabase_url, service_role_key)
   ```
4. `sign_output_path(supabase, output_path)` keeps working unchanged (it receives the
   client returned by `get_supabase_client`, and only calls methods on it — no import
   needed at module scope).

No other logic changes. The image, secrets, routes, and DB columns stay as-is.

## Alternative (not recommended): install supabase locally

`pip install supabase` on the Mac would let the local import succeed. This is fragile —
any future module-level import of a container-only package will break the deploy again.
The lazy-import fix is the durable Modal pattern.

## Deliverable

I'll write the corrected `api.py` to `/mnt/documents/api.py` (overwriting the current
copy) for you to download and `modal deploy` again. No Lovable project / frontend changes
are needed.
