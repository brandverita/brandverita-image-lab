# WP2 close-out — fix silent eval-run loss, then record the Module B manifest

Module B passed 18/18 in staging on 2026-09-05, and the `generation_assets`
lineage row is confirmed: 1080x1080, ready, hashed, `instruction_sha256`
present, classification `research_only/staging`. One framework defect found
while collecting manifest evidence.

## Root cause (confirmed by reading the deployed-shape code)

`transformation_eval_runs` has zero rows for Module B. The adapter
(`adapters/bfl_product_scene.py` line 313) writes the provider reference
under the key `provider_request_id`, but the table column is
`provider_call_id`. PostgREST rejects the insert with an unknown-column
error, and `advanced.write_eval_run` swallows every exception by design
("an eval-record failure must not fail a user-visible operation") — so the
eval row was silently discarded while the job completed successfully.

## Fixes (three small edits, then redeploy + rerun)

1. `backend/phase2b/adapters/bfl_product_scene.py`:
   - Rename the eval_row key `provider_request_id` -> `provider_call_id`
     (line 313). The `provenance` dict keeps `provider_request_id` — that is
     free-form JSONB and correct as-is.
2. `backend/phase2b/advanced.py` — `write_eval_run`: stop failing silently.
   Keep the no-raise contract, but on a non-2xx response or exception print
   `wp_eval_run_write_failed status=<code> body=<first 300 chars>` so a
   schema/key mismatch is visible in Modal logs instead of vanishing.
3. `backend/phase2b/tests/test_wp2_product_scene.py`: the printed follow-up
   SQL selects `provider_request_id`; change it to `provider_call_id` so the
   printed query runs without the 42703 error you hit.

Then: copy the two amended files over `phase1-v6-staging/`, clear
`__pycache__`, `modal deploy api.py`, and rerun `test_wp2_product_scene.py`
(expect 18/18 again, one more BFL image at $0.04). This also produces a
fresh eval row + asset row for the manifest.

## Latency finding to record

Observed 162.7s vs p95 target ≤90s. The adapter bounds the provider call at
300s, so this is within safety limits but above target. Recorded as an open
finding; judge after 2–3 more samples whether it was first-call warm-up.

## Manifest close-out (after the rerun)

Append the WP2 acceptance section to `backend/phase2b/module-b.md`:
acceptance date, 18/18, registry row (testing / research_only / internal,
staging-only, config_hash `4dfc6a2a...afea43`), provider pin note, latency
finding, and the two SQL result sets from the rerun.

No schema change is needed — the `provider_call_id` column already exists.
