# Set the config hash for outpaint:v2

Step 1 is done: the insert ran and both rows read as expected —
`outpaint v1 / modal_research_2b` and `outpaint v2 / bfl_outpaint /
flux-pro-1.0-expand`, both `testing / research_only / internal / false / false /
{staging} / true`.

## Step 2 — I run the config-hash tool

In this workspace (the same way `product_scene:v1` was done):

```bash
pip install httpx
python backend/phase2b/tools/set_config_hash.py outpaint v2
```

It reads `SUPABASE_URL` and the service-role key from the workspace
environment, recomputes the SHA-256 over the immutable config fields using the
same canonicalisation the API uses, and writes it to `config_hash`. Expected
output:

```text
outpaint:v2 config_hash=<64 hex chars>
```

Do not compute this hash in SQL — a differently-encoded value trips the API's
`config_hash_mismatch` tripwire.

## Step 3 — verify

- `GET /v1/workflows` (Lab origin) lists `outpaint:v2` with a
  `config_hash_prefix` equal to the first 12 characters printed above.
- Run a Smart Resize at 1200x627 in the Lab: the result should appear, the
  source-region check should pass, and the run should be recorded against the
  hosted provider.

## Notes

- `outpaint:v1` stays available for side-by-side comparison.
- The row is staging-only, research-only, internal: Studio visibility and
  production dispatch remain refused server-side.
