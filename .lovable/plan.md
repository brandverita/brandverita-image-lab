# WP2 close-out — record the Module B build manifest

Module B (product scene, BFL flux-kontext-pro) passed 18/18 in staging on
2026-09-05: job accepted, completed, exact 1080x1080 output, hashed
caller-owned output asset, signed-URL-only delivery, no instruction leakage,
all rejections held, Flux regression unchanged, Studio isolation confirmed.

## 1. Data you still need to paste

The WP2 test printed two SQL queries. Run them in the Supabase `comfy-ui` SQL
editor and paste the result sets here:

- `generation_assets` row for asset `6a51f33b-d172-4231-b59e-6ef31cf0d22e`
  (kind, lineage, sha256, dimensions, instruction_sha256, subject_preserved,
  classification).
- `transformation_eval_runs` row for job `0e0b14b6-7d0d-4d34-a084-3dcd1a81bbf3`
  (module, provider, latency, estimated_cost, provider_request_id,
  source_region_verified).

These close the lineage + metering evidence for the manifest.

## 2. Update `backend/phase2b/module-b.md`

Append a WP2 acceptance section recording:

- Acceptance date 2026-09-05, staging, 18/18 checks.
- Observed latency 162.7s vs p95 target ≤90s — flagged as an open finding:
  rerun the test 2–3 more times to see whether this was first-call provider
  warm-up before treating it as a breach. Estimated cost $0.04/image is
  within the ≤$0.10 target.
- Registry row: `product_scene:v1`, testing / research_only / internal,
  staging-only, production and Studio disabled, config_hash
  `4dfc6a2a605abc1fbd43e6a2dd2bad8e14430eb01760495dfd803712d1afea43`.
- Provider pin: BFL hosted endpoint, no file digest possible; traceability via
  provider_request_id recorded per run.
- The two pasted SQL result sets as lineage/metering evidence.

## 3. Restore the kill-switch posture

Confirm all five advanced flags return to the agreed staging state. Per the
current staging posture (flags ON in staging, isolation from the registry
row), only confirm `product_scene:v1` remains research_only + internal and
no Studio origin can see it — already proven by check 12. If you prefer the
conservative posture, set `PROVIDER_BFL_ENABLED=false` and redeploy
`api.py` to stop all hosted spend between test sessions.

## 4. Then

Both Phase 2B modules (A: outpaint, B: product scene) are accepted staging
research features. Next decision point: the Studio export package
(operative feature contract documentation) — separate plan when you want it.
