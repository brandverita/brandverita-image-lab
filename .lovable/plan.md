# WP2 checks 8a/8b — test-side field name mismatch, not a service defect

## What the run actually shows

Module B works end-to-end: job accepted, completed in 26.1s, exact 1080x1080
output, hashed and caller-owned output asset, no instruction leakage, every
rejection held, Flux unchanged, invisible to Studio origin.

The two failures are in the test script, not the API. The asset endpoint returns
the short-lived signed link under the key `read_url` (`_safe_asset` in
`assets.py` sets `out["read_url"]`), and it deliberately does not expose
`storage_path`. The WP2 test looks for `download_url` or `url`, finds neither,
so 8a fails and 8b falls through to its "storage_path not exposed" branch.

## Change

Edit `backend/phase2b/tests/test_wp2_product_scene.py` only:

1. Read the signed link as `read_url` first, keeping `download_url`/`url` as
   fallbacks, then fetch it and assert 200 for 8a.
2. For 8b, derive the unsigned object URL from the signed link itself instead of
   requiring `storage_path`: take the signed URL, strip the query string, and
   replace `/object/sign/` with `/object/public/`. Fetch it with no auth and
   assert the response is >= 400. Keep the current "not exposed" fallback only if
   no signed link is present at all.

No change to `assets.py`, `api.py`, `advanced.py`, or the adapter — the privacy
behaviour under test is already correct (private bucket, signed reads only).

## After the edit

Re-run `python test_wp2_product_scene.py`; expect 18/18. Then paste the two SQL
result sets the script prints (`generation_assets` row and
`transformation_eval_runs` row) so the WP2 build manifest can be recorded, and I
will close out WP2 in `module-b.md`.
