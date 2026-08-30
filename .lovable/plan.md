# Check 3: the outpaint registry row was never flagged as an asset workflow

17/18 confirm the amended `api.py` is live. Check 3 is a **data** gap, not a code gap.

Queried the staging registry just now:

```text
key                version                    status  requires_source_asset  allowed_output_presets
flux_text_to_image v1                         active  false                  []
flux_text_to_image v1-commercial-candidate     draft   false                  []
outpaint           v1                          draft   false                  []
```

`outpaint:v1` has `requires_source_asset = false`, so `POST /v1/generations` takes the non-asset branch in `api.py` (line 410) and `registry.assert_dispatch_allowed` answers `workflow_unavailable: ... is not active` — never reaching `advanced.resolve_advanced_request`, which is what emits `workflow_not_available`. WP0's migration added the columns but did not populate this row.

`allowed_output_presets` is also empty, and `input_envelope` unset — both are needed by the framework gate (`advanced.py` lines 288–302), which expects preset strings like `"1080x1080"`.

## Fix — one small data migration (no code change)

Update only the `outpaint:v1` row. The immutability trigger freezes these fields once `status` is `active/deprecated/disabled`; this row is `draft`, so the update is permitted.

- `requires_source_asset = true`
- `allowed_output_presets = ["1080x1080","1200x627","1600x900","1080x1350","1080x1920"]` (matches the approved absolute presets and the existing `allowed_dimensions`)
- `input_envelope = {"max_width": 4096, "max_height": 4096, "max_pixels": 16777216, "allowed_content_types": ["image/png","image/jpeg","image/webp"]}`
- `status = 'testing'` — aligns the row with the approved decision set (`testing`, `research_only`, `internal`, `production_enabled=false`, `enabled_for_studio=false`, `allowed_envs=[staging]`); the advanced gate accepts both `draft` and `testing`, so this is cosmetic but matches the record.
- `candidate_id` / `candidate_notes`: leave null in WP0 (populated per candidate in WP1/WP2).

Everything else stays exactly as is. All five `*_ENABLED` flags remain `false`, so the request still ends at the master-flag gate — the only change is that it is now refused by the framework with the correct `workflow_not_available` code instead of the generic lifecycle check.

## Expected results after the migration

- Check 3 → `403 workflow_not_available`.
- Checks 5, 7–9, 12–16 keep passing, now via the framework gate rather than the lifecycle check (same statuses).
- Check 17/18 unchanged: the row stays `internal` + `research_only`, so a Studio-origin read still returns nothing new. `safe_workflow_view` does not expose `requires_source_asset`, and the Studio filter rejects the row on `registry_visibility` regardless.
- Check 6 (Flux + stray `source_asset_id` → 400) unchanged; Flux rows keep `requires_source_asset = false`.

No Modal redeploy is needed — the registry cache is 60s TTL, so wait a minute (or the container recycles) and re-run the suite. Expected 28/28.

## Rollback

Single-row update; reverting means setting `requires_source_asset` back to `false`, `allowed_output_presets` to `[]`, `input_envelope` to null, and `status` back to `draft`.

## Close-out

Once your run shows 28/28 I write `backend/phase2b/wp0-build-manifest.md` (deployed revision, flag values, migration ids, test result, rollback). WP1 and WP2 still need your separate approval.
