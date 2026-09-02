# Fix the WP2 registry migration — wrong column name

The insert in `backend/phase2b/wp2-registry-migration.sql` uses `title`, but the
`workflow_definitions` table has no such column. The human-readable label column
is `display_name` (confirmed in the live schema and used by `registry.py`'s
`SAFE_FIELDS`).

## Change

In `backend/phase2b/wp2-registry-migration.sql`, rename the column in the insert
column list:

```text
key, version, title, description,        ->   key, version, display_name, description,
```

Nothing else changes: the value `'Product background / scene (research)'` stays
in the same position, and all other columns in the statement (`provider`,
`provider_model`, `status`, `commercial_status`, `registry_visibility`,
`production_enabled`, `enabled_for_studio`, `allowed_envs`,
`requires_source_asset`, `allowed_output_presets`, `input_schema`,
`output_schema`, `allowed_dimensions`, `input_envelope`, `artifact_pins`,
`candidate_notes`) exist on the table.

## After the fix

The rest of `README-wp2-integration.md` step 3 is unchanged:

1. Re-run the corrected SQL in the Supabase `comfy-ui` SQL editor.
2. Run `python backend/phase2b/tools/set_config_hash.py product_scene v1` with
   `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` set.
3. Verify row reads: `testing / research_only / internal / f / f / {staging} / t`.

Note: the migration is an ordinary data insert into an existing table, so it is
run by you in the SQL editor as before — no schema migration tool call is needed.
