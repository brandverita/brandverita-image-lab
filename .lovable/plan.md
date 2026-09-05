# WP2 close-out — eval-run fix verified, record the Module B manifest

Module B passed 18/18 again on 2026-09-05 after the `provider_call_id` fix, and
the eval row now lands correctly (verified via SQL: job
`ff911678-bc2b-4cd1-8b36-9fc3bafcfc26`).

## Fresh evidence from the rerun

Asset row `d54e0700-63a8-42e5-88cf-ff0cca8e745d`:
- kind=output, status=ready, source_asset_id `a1db7262-...`, sha256
  `281c2a13...dfeb9`, 1080x1080, instruction_sha256 `a1eb5a26...5fe64`,
  subject_preserved=unverified, classification=research_only/staging.

Eval row for job `ff911678-...`:
- module=product_scene, provider=bfl_product_scene, status=completed,
  output_preset=1080x1080, provider_call_id `f9826009-bf7f-46c6-819e-af4209ba26a5`,
  estimated_cost=$0.04, source_region_verified=null,
  **provider_latency_ms=9 251, total_latency_ms=16 729**.

## Latency finding — resolved as warm-up

Second sample: 16.7s total / 9.3s provider, versus the first call's 162.7s.
The first-call figure was provider/adapter warm-up. Both samples are within the
p95 ≤90s target. Record both in the manifest and note that p95 confidence still
needs more samples over time.

## Remaining step: manifest close-out

Append the WP2 acceptance section to `backend/phase2b/module-b.md`:
- Acceptance date 2026-09-05, 18/18 (twice), eval-row recording defect found
  and fixed (`provider_request_id` → `provider_call_id`, plus write-failure
  logging in `advanced.write_eval_run`).
- Registry row: product_scene:v1, testing / research_only / internal,
  staging-only, config_hash `4dfc6a2a...afea43`.
- Provider pin: BFL flux-kontext-pro, $0.04/image, secret `bfl-research-2b`.
- Latency: two samples (162.7s warm-up, then 16.7s); within target.
- The two SQL result sets above.

No code or schema changes remain.
