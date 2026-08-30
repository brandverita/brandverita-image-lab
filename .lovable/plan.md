# Phase 2B (revised) — Image Transformation Framework v1 + two parallel internal modules

Replaces the single sequential outpaint experiment. One shared framework built once
(2B-0), then Module A (Smart Resize / Outpaint, Modal research lane) and Module B
(Product Background / Scene, one hosted provider) evaluated in parallel (2B-1 / 2B-2),
then a single review-and-select gate (2C). Staging only, provider-neutral, both
candidates `research_only` / `production_enabled=false` / `enabled_for_studio=false`
for the whole phase. Nothing is deployed until implementation is separately approved.

## 1. Shared framework architecture and data-model delta

Flow: Image Lab → `POST /v1/generations` (JWKS-verified) → asset+registry gate →
provider adapter (Modal research worker *or* hosted provider) → output written to the
private `generation-assets` bucket → `generation_assets` output row + eval run row →
client polls `GET /v1/generations/{id}` and reads the output only via a short-lived
signed URL after an ownership check.

Data-model delta (all additive; no change to the Flux text-to-image path):

- `workflow_definitions`: add `requires_source_asset boolean not null default false`,
  `allowed_output_presets jsonb not null default '[]'`, `input_envelope jsonb not null default '{}'`,
  `artifact_pins jsonb`, `candidate_notes text`. Existing immutability trigger must be
  extended to cover the new immutable-once-active fields.
- `generation_jobs`: add `source_asset_id uuid references public.generation_assets(id)`,
  `output_asset_id uuid references public.generation_assets(id)`, `output_preset text`.
- `generation_assets`: already supports `kind='output'`, `source_asset_id`, `job_id`,
  `workflow_key`, `workflow_version`, `provenance` — reused as-is, no schema change.
- New staging table `public.outpaint_eval_runs` (name kept; covers both modules) —
  run/job/candidate identity, module, provider + provider_model + provider_call_id,
  worker version, request params (preset, anchor, expansion_mode / scene_direction,
  background_style, seed), timing (queued/dispatched/first_byte/completed,
  total_latency_ms, cold_warm), cost (gpu_seconds, estimated_cost, actual_provider_cost,
  currency), result (status, safe error_code/message, dimensions, bytes, sha256,
  source_region_match), quality (per-reviewer rubric scores, mean, blinded flag),
  legal (`license_ref`, `commercial_status`, retention finding, training-on-input flag,
  `legal_status in pending|cleared_staging|blocked|needs_counsel`).
  Grants: `select` to `authenticated` scoped to the internal allow-list; `all` to
  `service_role`; no anon; no client write policies.

## 2. Exact API contract changes

`POST /v1/generations` accepts, only when the resolved registry entry declares
`requires_source_asset=true`:

```
{ workflow_id, workflow_version?, idempotency_key,
  source_asset_id: uuid,
  output_preset: "1200x627"|"1600x900"|"1080x1080"|"1080x1350",
  params: { anchor, expansion_mode, style_mode:"preserve_source" }      // Module A
        | { scene_direction, background_style, preserve_subject:true }  // Module B
}
```

Server-side gate order, before any dispatch: (1) JWKS-verified caller on the internal
allow-list; (2) workflow resolves and is `research_only` + staging + flag on;
(3) asset row exists, `owner_id = auth uid`, `status='ready'`, `deleted_at is null`,
`expires_at > now()`, `kind='input'`; (4) asset fits `input_envelope` and the requested
preset is in `allowed_output_presets` and compatible with orientation; (5) module params
validated against a strict enum/`input_schema` — no free-text prompt field is accepted
for either module. Ownership is re-checked at dispatch time.

Errors: `asset_not_found`/`asset_not_owned` 404, `asset_not_ready` 409, `asset_expired`
409, `invalid_request` 400, `workflow_not_available` 403, `rate_limited` 429.
`GET /v1/generations/{id}` gains `source_asset_id`, `output_asset_id`, `output_preset`
and a signed output URL only after the ownership check. No signed URL, provider key,
graph JSON, prompt, or model path ever appears in a response, log, or the client bundle.

## 3. Registry candidate records and feature flags

Candidate ids: `outpaint-v1-modal-comfy-<model>-01`,
`productscene-v1-<provider>-<model>-01`. Both rows: `status='testing'`,
`commercial_status='research_only'`, `registry_visibility='internal'`,
`production_enabled=false`, `enabled_for_studio=false`, `requires_source_asset=true`,
`allowed_envs={staging}`, presets per module, `config_hash` immutable once active,
`artifact_pins` = repo URL + full SHA + filename + SHA256 + license per artifact.
Any config change means a new candidate id.

Flags (server, default false): `ADVANCED_WORKFLOWS_ENABLED` (master kill switch),
`OUTPAINT_EVAL_ENABLED`, `PRODUCT_SCENE_EVAL_ENABLED`, `PROVIDER_<X>_ENABLED`.
Client: `VITE_ADVANCED_LAB_ENABLED` default false, gating one internal Image Lab panel.
Studio-shaped registry reads filter research/internal rows at the API layer.

## 4. Modal research worker plan (cannot affect V6 Flux)

Separate Modal app `comfyui-research-worker-2b` in its own directory, its own image,
its own pinned ComfyUI SHA and its own SHA256-verified model artifacts. The V6 API
dispatches to it only through a new adapter selected by the registry row's `provider`;
the Flux adapter, graph, worker app and V5 rollback target are untouched. One controlled
outpaint graph, no browser-supplied nodes; the original source region is composited back
unchanged after generation and verified by comparing the source region hash — a mismatch
fails the run. Deleting the research app must not affect Flux.

## 5. Hosted-provider selection checklist and secret design

Pick exactly one provider before any spend, on written evidence: commercial use
permitted; no training on customer inputs; input/output retention window and deletion;
sub-processor list and region; image-editing/subject-preservation capability at the two
presets; per-call price; rate limits; SLA/status history; license reference recorded in
the candidate row. Recorded as `legal_status` + `provider_terms_reference`. No run before
the finding is written.

Secrets: one server-side secret per provider (`<PROVIDER>_API_KEY`) in the Modal app
secret store only, read inside the handler, never in Netlify env, never `VITE_*`, never
logged. Inputs reach the provider as a short-lived server-issued signed read URL, never
a public URL; the URL is not persisted on the job row.

## 6. Output asset and lineage design

Output written to `generation-assets` at `<user_id>/<output_asset_id>/original.<ext>` as
a new row: `kind='output'`, `source_asset_id`, `job_id`, `workflow_key`,
`workflow_version`, `provenance` (candidate id, config hash, provider, preset), sha256,
dimensions, staging TTL. Job row records `source_asset_id` + `output_asset_id`; lineage
is cross-checkable both ways. Inputs are downloaded to an ephemeral path keyed by
`job_id`, SHA256-verified against the asset row, and deleted in a `finally` block.
Bucket stays private; browser reads only via short-lived signed URLs.

## 7. Test plan, rollback, deployment isolation

Negative contract tests: not-owned, not-ready, expired, output-kind source,
over-envelope, non-preset, invalid anchor/expansion_mode/scene_direction, free-text
prompt rejected, cross-user, unauthenticated, flags off ⇒ not dispatchable, production
mode rejects `research_only`, research rows absent from Studio-shaped reads.
Integrity tests: temp files provably deleted, source region unchanged in Module A
output, lineage rows correct, no secret in client bundle, no signed URL or prompt in logs.
Regression: Flux V6 byte-identical behaviour, V5 healthy, `usage_ledger` stays unwired.

Evaluation: 8-asset fast corpus (2 clean-background product, 2 product-in-scene,
1 portrait, 1 text/logo-edge, 1 hard texture/perspective, 1 interior/exterior) frozen by
asset id + SHA256; 2 presets per module ⇒ 16 runs per candidate; two reviewers, blind,
existing 1–5 seven-axis rubric, >1 point disagreement ⇒ third review. Gates: p95 ≤ 90 s
(reject > 120 s), completion ≥ 95%, ≤ $0.10 per successful output (hard cap $0.20),
Stage A caps $10 Modal + $10 hosted provider. No 24-asset corpus until the
fast-validation report is reviewed (Phase 2C).

Rollback: master flag off ⇒ both candidates unreachable; registry rows deactivated, not
deleted; research worker app deleted independently; V5 remains the API rollback target;
frontend panel is flag-gated so a Netlify revert is not required.

## 8. Work packages

- **WP0 (shared, blocking)**: migration (registry columns, job link columns,
  `outpaint_eval_runs`), asset-resolution gate, adapter interface + dispatch-time
  ownership recheck, output-asset writer + lineage, temp-file/SHA256 discipline, flags,
  eval-run recording, negative-test suite. Ships behind flags with no candidate active.
- **WP1 (parallel)**: Modal research worker app + outpaint graph + composite-back
  verification + Module A candidate row.
- **WP2 (parallel)**: provider terms/data review → provider choice → secret →
  adapter + curated scene directions + Module B candidate row.
- **WP3**: internal Image Lab advanced panel (flag-gated, structured inputs only).
- **WP4**: 8-asset corpus freeze, 16 runs per candidate, blind scoring, cost
  reconciliation, fast-validation report.
- **WP5 (Phase 2C)**: review, select winner(s), then full 24-asset run for winners only.

WP1 and WP2 start only after WP0's negative tests pass; WP4 requires both modules or can
run per module as each lands.

## Open items for your confirmation

- Hosted provider for Module B: shortlist and choose after the terms review, or do you
  already have a preferred one?
- Module A `expansion_mode` values to support in v1 (e.g. `symmetric` vs
  `anchor_directional` only).
