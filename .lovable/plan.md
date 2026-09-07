# Register the hosted Smart Resize row (outpaint:v2)

Two steps: you run the SQL insert, I run the config-hash tool from this
workspace (same as for `product_scene:v1`).

## Step 1 — you: run the insert

`backend/phase2b/wp1b-registry-migration.sql` is a plain data insert into the
existing `workflow_definitions` table, so no schema migration tool is involved.

1. Open the Supabase `comfy-ui` SQL editor.
2. Paste the full current contents of `backend/phase2b/wp1b-registry-migration.sql`
   into a fresh query tab (don't re-run an older saved tab).
3. Run it. The statement ends with `on conflict (key, version) do nothing`, so
   re-running is harmless.
4. The verify query at the bottom should return two rows:

```text
outpaint v1  testing research_only internal f f {staging} t modal_research_2b
outpaint v2  testing research_only internal f f {staging} t bfl_outpaint  flux-pro-1.0-expand
```

## Step 2 — me: set the config hash

Once you confirm the row exists, I run in this workspace:

```bash
pip install httpx
python backend/phase2b/tools/set_config_hash.py outpaint v2
```

It reads `SUPABASE_URL` and the service-role key from the workspace
environment, recomputes the SHA-256 over the immutable config fields with the
same canonicalisation the API uses, and writes `config_hash`. Expected output:

```text
outpaint:v2 config_hash=<64 hex chars>
```

Do not compute this hash in SQL — a differently-encoded hash trips the API's
`config_hash_mismatch` tripwire.

## Step 3 — verify end to end

- `GET /v1/workflows` (Lab origin) lists `outpaint:v2` with a
  `config_hash_prefix` matching the first 12 characters printed above.
- Run a Smart Resize at 1200x627 from the Lab and confirm the result appears
  and the source-region check passes.

## Notes

- `outpaint:v1` is untouched and remains available for comparison.
- The row is staging-only, research-only, internal: Studio visibility and any
  production dispatch stay refused server-side.
