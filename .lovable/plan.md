# Run the config-hash tool for product_scene:v1

This is a local, one-off script run. It talks only to Supabase over HTTPS — it does
not touch Modal, so it does **not** run from `modal-project`. Run it from the folder
where you keep this repo's `backend/` files (the same place the SQL file came from).

## Steps

1. Open Terminal and change into the repo root (the directory that contains
   `backend/phase2b/tools/set_config_hash.py`):

```bash
cd /path/to/generation-test-ui
```

2. Activate the Python env you already use and make sure `httpx` is present:

```bash
source ~/Desktop/modal-project/venv310/bin/activate
python -c "import httpx; print(httpx.__version__)"
# if it errors: pip install httpx
```

3. Get the service-role key from the Supabase dashboard:
   Project `comfy-ui` -> Project Settings -> API -> `service_role` secret.
   Paste it inline for this single command only. Do not put it in `.env`, the
   frontend, or any committed file.

4. Run the command as one line (the backslashes are line continuations; if you
   paste it multi-line, keep the trailing `\` at the end of each line and no
   trailing spaces after them):

```bash
SUPABASE_URL=https://thspgkedjkiltrcimond.supabase.co SUPABASE_SERVICE_ROLE_KEY=sb_secret_xxx python backend/phase2b/tools/set_config_hash.py product_scene v1
```

The `VAR=value ... python` prefix form sets the variables for that one process only;
nothing persists in your shell.

5. Expected output — a single line:

```text
product_scene:v1 config_hash=<64 hex chars>
```

6. Verify in the Supabase SQL editor:

```sql
select key, version, left(config_hash, 12) as config_hash_prefix
from public.workflow_definitions
where key = 'product_scene';
```

## If it fails

- `no registry row for product_scene:v1` — the insert did not land in this project;
  re-check the verify query from the migration.
- `patch failed: 401/403` — wrong key: it must be the `service_role` key, not the
  anon/publishable key.
- `ModuleNotFoundError: httpx` — wrong interpreter; activate the venv from step 2.
- `python: can't open file ...set_config_hash.py` — you are in the wrong directory;
  step 1's path must contain `backend/phase2b/tools/`.

After this succeeds, continue with step 4 of `README-wp2-integration.md`
(copy the WP2 files into `phase1-v6-staging/` and `modal deploy api.py`).
