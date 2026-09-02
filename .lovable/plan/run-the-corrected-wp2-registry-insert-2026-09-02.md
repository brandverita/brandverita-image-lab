# Run the corrected WP2 registry insert

The current project migration has already been verified: line 12 uses
`display_name`, not `title`. PostgreSQL reporting the exact text
`key, version, title, description` means the SQL Editor is still executing an
older copied version of the statement.

## Action

1. In the Supabase SQL Editor, discard the existing query tab contents rather
   than editing or rerunning its saved statement.
2. Re-copy the latest complete contents of
   `backend/phase2b/wp2-registry-migration.sql`.
3. Before running it, confirm its insert begins exactly as follows:

```sql
insert into public.workflow_definitions (
  key, version, display_name, description,
```

4. Search the SQL Editor text for `title`; there must be no matches.
5. Run the corrected statement. The earlier failed insert was atomic, so it did
   not leave a partial `product_scene:v1` row.
6. Run the config-hash command from the WP2 integration guide, then verify the
   registry row reports `testing / research_only / internal / false / false /
   {staging} / true`.

## If the same error appears again

Capture the first 15 lines shown in the SQL Editor immediately before execution.
The database cannot produce this specific error from the verified project file,
because that file no longer references a `title` column.