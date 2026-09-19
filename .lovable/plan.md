# Module C — editorial deploy complete; remaining steps

**Status: the editorial module is deployed and healthy.** Your swap of
`advanced.py` fixed it — health now reads `modules: {outpaint: true,
product_scene: true, editorial_layout: true}` and
`editorial_layout_adapter: bfl_editorial_layout`. The deploy side of Module C is
done.

## Done

- `advanced.py` replaced with the current 780-line version (has the editorial
  branch in `module_flag`), cache cleared, redeployed.
- Health confirms all three modules on and the editorial adapter registered.

## Expected: `editorial_layout:v1` not yet in `workflows`

The health `workflows` array still lists only the flux/outpaint/product_scene
rows. That's correct — it's read from the `workflow_definitions` table, and the
editorial registry row hasn't been inserted yet. It appears after step 1 below.
This is not an error.

## Remaining steps

1. **Registry migration** — `backend/phase2b/editorial-registry-migration.sql`
   inserts `editorial_layout:v1` (`testing` / `research_only` / `internal`,
   staging-only, `production_enabled=false`, `enabled_for_studio=false`).
   Idempotent (`on conflict do nothing`), and a `testing` row isn't locked by the
   immutability trigger, so it's safe and reversible. **I can run this now via the
   connected `comfy-ui` project on your approval**, or you run it in the Supabase
   SQL editor. Verify it returns
   `testing / research_only / internal / f / f / {staging} / t`.

2. **Config hash** (you, on the Mac) —
   `python backend/phase2b/tools/set_config_hash.py editorial_layout v1`
   from the workspace that has `backend/phase2b/`, with the service-role secret.
   Must be the Python canonicalisation, not SQL — a SQL-computed hash trips the
   mismatch tripwire.

3. **Capped evaluation batch** (you) — run a few editorial jobs from the Lab
   "Editorial layout" tab, score them (subject changed / text unreadable), and
   confirm rows appear under `editorial_layout` in the comparison table. Respect
   the $10 research spend cap.

4. **Close-out** — BFL disclosures, then decide Studio exposure (separate
   approval).

## Note

The `roadmap.md` Track I deploy entry can't be updated right now (plan mode locks
all files except this plan). I'll mark the deploy step done once we're in build
mode.
