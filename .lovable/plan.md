# Run the config-hash tool for product_scene:v1

I run this from the Lovable workspace, not from your local machine or a GitHub
codespace. The script `backend/phase2b/tools/set_config_hash.py`, the
service-role key, and `SUPABASE_URL` are all already present in this workspace,
and it can reach Supabase over HTTPS. No codespace, no Supabase re-linking, and
no service-role key handling on your side. The only missing piece is `httpx`,
which I install before running.

## Steps (executed by me in this workspace)

1. Install the one missing dependency:

```bash
pip install httpx
```

2. Run the config-hash tool for the `product_scene:v1` registry row:

```bash
python backend/phase2b/tools/set_config_hash.py product_scene v1
```

The script reads `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` from the
workspace environment (both already set), recomputes the SHA-256 over the
canonical JSON of the immutable config fields, and writes it to
`workflow_definitions.config_hash`.

3. Expected output — a single line:

```text
product_scene:v1 config_hash=<64 hex chars>
```

4. Verify in the Supabase SQL editor (you run this part):

```sql
select key, version, left(config_hash, 12) as config_hash_prefix
from public.workflow_definitions
where key = 'product_scene';
```

The 12-char prefix must match what the script printed, and it must agree with
the `config_hash_prefix` the API reports on `GET /v1/workflows` for Lab
origin. A mismatch trips the API's `config_hash_mismatch` log and means the
row's config was edited outside the immutability trigger's coverage.

## Why not a codespace

- `backend/phase2b/tools/set_config_hash.py` lives in this Lovable staging
  workspace, not in the deployed frontend repo `brandverita/generation-test-ui`,
  so a fresh codespace of that repo would not contain it.
- "Linking Supabase" to a codespace exposes the publishable/anon key, not the
  service-role key the script needs; you would have to add the service-role
  key as a codespace secret yourself.

## If the script fails

- `no registry row for product_scene:v1` — the WP2 insert did not land; re-run
  the verify query from the migration and confirm the row exists.
- `patch failed: 401/403` — service-role key is wrong or expired; rebind via
  Project Settings and rerun.
- `ModuleNotFoundError: httpx` — dependency install did not take; reinstall and
  rerun.

## After it succeeds

Continue with step 4 of `backend/phase2b/README-wp2-integration.md`: copy the
WP2 files (`scene_presets.py`, `adapters/bfl_product_scene.py`, `advanced.py`,
`api.py`) into your local `phase1-v6-staging/` folder, create the
`bfl-research-2b` Modal secret, `modal deploy api.py`, and confirm `/health`
reports `product_scene_adapter: bfl_product_scene` and
`hosted_dispatch_enabled: true`.
