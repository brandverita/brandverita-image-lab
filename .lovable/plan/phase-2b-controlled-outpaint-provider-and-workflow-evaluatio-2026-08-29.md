# Phase 2B — Controlled Outpaint Provider and Workflow Evaluation (v2, decisions incorporated)

Scope: staging-only research. No Studio surface, no billing, no production deployment,
no customer-facing outpainting. This document is the plan only — no provider adapter,
worker, registry migration, frontend UI, or secret is implemented or deployed until a
separate implementation approval.

## 0. Confirmed decisions (locked)

**Latency** — measured end-to-end, API request accepted → job completed with output
stored; cold and warm runs recorded separately:

| Tier | p50 | p95 |
| --- | --- | --- |
| Excellent | ≤ 30 s | ≤ 60 s |
| Acceptable (first async customer-facing workflow) | ≤ 45 s | ≤ 90 s |
| Conditional | — | 90–120 s, only if quality is materially superior |
| Fail | — | > 120 s, or completion rate < 95% |

**Cost** — target ≤ $0.10 per successful output; hard evaluation cap ≤ $0.20 per
output; up to $0.30 only for a candidate explicitly labelled premium that clears the
quality gate materially better than alternatives. Actual costs recorded for the exact
provider/model/resolution used.

**Review** — Reviewer 1: BrandVerita founder/product owner. Reviewer 2: an independent
reviewer who did not configure or run the candidate. Commercial/data-review owner:
BrandVerita founder/legal entity; technical evidence owner: BrandVerita engineering.
Legal statuses: `pending | cleared_staging | blocked | needs_counsel`.
`cleared_staging` applies only to authorized internal test assets and confers no
customer-data or production approval. No formal legal review has been obtained.

**Corpus** — BrandVerita-owned/authorized internal assets first; licensed stock only to
fill gaps (portraits, architecture, difficult lighting, texture/perspective). No
customer uploads, scraped content, review profile photos, or third-party web/social
images. Provenance note + SHA256 per corpus asset.

**Provider spend (staged funnel)** — Stage A: 6 assets × 2 presets = 12 runs per
candidate. Caps: $10 per external provider (Replicate, BFL), $10 soft cap for Modal
research in Stage A. Full corpus only after Stage A review. Stage B: separate approval,
$25 cap per shortlisted provider/candidate. Total Phase 2B budget ceiling: $75–$100
including retries.

**Workflow shape** — fixed absolute output presets (not user-facing ratios):
`1080x1080`, `1200x627`, `1600x900`, `1080x1350`, `1080x1920`. Expansion direction and
anchor are structured parameters. Evaluate a one-pass workflow first; a two-pass
refinement variant is only considered if the Stage A leader narrowly misses seam or
subject-integrity thresholds.

## 1. Executive recommendation

Treat outpainting as a provider selection experiment, not a feature build. Phase 2B
produces one artifact: a signed evaluation report naming one recommended `outpaint:v1`
provider path with measured quality, latency, cost, and legal status — plus the losing
candidates and why. Every candidate stays `research_only`, `production_enabled=false`,
`enabled_for_studio=false` for the entire phase; the API rejects research-workflow
dispatch from anything other than an allow-listed internal account in staging.

## 2. Asset-to-job contract (staging only)

Add `source_asset_id` as an accepted request field on `POST /v1/generations` **only for
workflows whose registry entry declares `requires_source_asset = true`**.

Server-side gate, in order, before any provider dispatch:

1. Caller is JWKS-verified and on the internal allow-list.
2. Workflow key/version resolves in the registry and is `research_only` + staging.
3. Asset row exists, `owner_id = auth user`, `status = 'ready'`, `deleted_at is null`,
   `expires_at > now()`, `kind = 'input'`.
4. Asset dimensions/pixels fit the workflow's declared input envelope, and the requested
   output preset is one of the five absolute presets and compatible with the asset's
   orientation/dimensions.
5. Expansion direction + anchor are valid structured parameters for the preset.

Failure codes: `asset_not_found`/`asset_not_owned` 404, `asset_not_ready` 409,
`asset_expired` 409 (new), `invalid_request` 400, `workflow_not_available` 403.
The job row records `source_asset_id` (FK to `generation_assets`); no public URL is
ever accepted as input; no browser-supplied graph JSON is ever accepted. Ownership is
re-checked at dispatch time, not only at request time.

## 3. Candidate workflow registry scheme

```text
outpaint:v1                     logical workflow key
  candidate id: outpaint-v1-<provider>-<model>-<nn>
  e.g. outpaint-v1-modal-comfy-<model>-01
       outpaint-v1-replicate-<model>-01
       outpaint-v1-bfl-<model>-01
```

Each candidate row carries: `status='research_only'`, `visibility='internal'`,
`production_enabled=false`, `enabled_for_studio=false`, `requires_source_asset=true`,
`allowed_output_presets` (the five absolute presets), `input_envelope`, `provider`,
`provider_model`, `config_hash` (immutable once activated), `commercial_status`,
`license_ref`, `artifact_pins` (repo URL + full SHA + filename + SHA256 + license, per
the Phase 1 rule), `candidate_notes`. A change means a new candidate id.

## 4. Provider evaluation framework

Three tracks, same request contract, same corpus, same presets, same rubric:

- **Track M — Modal + ComfyUI (self-hosted research).** Dedicated research worker app,
  separate from the pinned Flux V6 worker, so Flux cannot regress.
- **Track R — Replicate-hosted candidates.** Per-call cost; license and data-retention
  terms read per model.
- **Track B — BFL candidates.** Quality ceiling and commercial terms.

Adapters sit behind the existing provider-adapter interface. Provider secrets are
server-side only, never in the frontend. Comparability rules: identical corpus,
identical presets, identical seeds where exposed, same reviewer set, blinded filenames.

Staged funnel: **Stage A** = 6 assets × 2 presets = 12 runs per candidate, within the
per-provider $10 caps. Results reviewed before any Stage B; Stage B (separate approval)
runs the shortlisted candidate(s) against the full corpus.

## 5. Per-run record

One row per run in staging table `outpaint_eval_runs` (service-role writes only, SELECT
to the internal allow-list):

- Identity: `run_id`, `job_id`, `source_asset_id`, `output_asset_id`, `operator_user_id`
- Workflow: `workflow_key`, `workflow_version`, `candidate_id`, `config_hash`
- Provider: `provider`, `provider_model`, `provider_call_id`, `worker_version`/image id
- Request: `output_preset`, expansion direction, anchor, seed, steps/guidance if exposed
- Timing: `queued_at`, `dispatched_at`, `first_byte_at`, `completed_at`,
  `provider_latency_ms`, `total_latency_ms` (API accepted → output stored), cold/warm flag
- Cost: `gpu_seconds`, `estimated_cost`, `actual_provider_cost`, currency,
  exact provider/model/resolution recorded
- Result: `status`, `error_code`, `error_message`, output dimensions, bytes, SHA256,
  completion counted toward the ≥95% completion-rate gate
- Quality: rubric scores per reviewer + mean, reviewer ids, blinded flag, notes
- Legal/data: `license_ref`, `commercial_status`, provider data-retention finding,
  training-on-input flag, reviewer + date, `legal_status` in
  `pending | cleared_staging | blocked | needs_counsel`

No prompts, tokens, or image bytes in stdout or browser console.

## 6. Evaluation corpus and human rubric

Fixed corpus of **24 authorized assets** (20 + 4 spares), uploaded once through the
Phase 2A pipeline, frozen by `asset_id` list + SHA256 so every candidate sees
byte-identical inputs. Composition target: 6 product-on-plain-background,
4 product-in-scene, 4 people/portrait, 4 interior/exterior, 3 text/logo-bearing,
3 hard cases (fine repeating texture, strong perspective, shallow depth of field);
landscape and portrait; provenance note per asset. Gaps are filled with licensed stock
only, per the confirmed corpus rule.

Stage A runs use 2 of the 5 presets per asset (chosen per asset orientation); Stage B
runs the full preset set where applicable.

Rubric, 1–5 per axis; Reviewer 1 (founder/product) and Reviewer 2 (independent, did not
configure/run the candidate); blinded; disagreement >1 point triggers a third review:

1. Seam continuity 2. Structural plausibility 3. Texture/material fidelity
4. Colour/lighting match 5. Subject integrity 6. Text/logo behaviour 7. Artefact freedom

Aggregate: mean of axes; a candidate fails outright if any single axis scores ≤2 on
more than 20% of runs regardless of mean.

## 7. Asset flow, temp files, output storage, lineage

1. API resolves the asset and issues a **short-lived server-side signed read URL**
   (single-use where supported); passed to the provider/worker, never to the browser,
   never persisted in the job row.
2. Worker downloads to an ephemeral temp path keyed by `job_id`, verifies SHA256 against
   the asset row, deletes in a `finally` block; nothing survives the container.
3. Track R/B receive the input via the same short-lived signed URL; retention terms are
   recorded in the legal review before any run.
4. Output goes to the private `generation-assets` bucket at
   `<user_id>/<output_asset_id>/original.<ext>` as a new row with `kind='output'`,
   `source_asset_id`, `job_id`, `workflow_key`, `workflow_version`, `provenance`, and
   the staging TTL. Browser reads only via short-lived signed URLs after ownership
   check; bucket stays private.
5. Lineage is cross-checkable: `output_asset.source_asset_id` ≡ `job.source_asset_id`.
6. `usage_ledger` stays unwired; cost data lives in `outpaint_eval_runs`.

## 8. Feature flags and safety gates

- Registry gate: research-workflow dispatch rejected unless the caller is
  internal-allow-listed **and** environment is staging; production rejects
  `research_only` unconditionally, server-side.
- Env gates (server, default false): `OUTPAINT_EVAL_ENABLED`,
  `PROVIDER_REPLICATE_ENABLED`, `PROVIDER_BFL_ENABLED`.
- Client gate: `VITE_OUTPAINT_EVAL_ENABLED` default false; any UI is an internal-only
  Image Lab panel — Studio is never touched.
- `enabled_for_studio=false`, `production_enabled=false` on every candidate;
  Studio-facing registry reads filter them out at the API layer.
- Kill switch: `OUTPAINT_EVAL_ENABLED=false` stops all candidate dispatch without
  touching Flux V6 or V5.

## 9. Test, promotion, rollback, exclusions

**Phase test criteria (all required):** contract negative tests pass (not-owned,
not-ready, expired, over-envelope, non-preset, invalid anchor/direction, cross-user,
unauthenticated); no candidate dispatchable with flags off; no candidate in a
Studio-shaped registry read; production-mode dispatch of `research_only` rejected;
temp files provably deleted; output rows carry correct lineage; Flux V6 unchanged, V5
healthy; no secret in the client bundle; Stage A spend reconciled against the $10
per-provider caps and reported.

**Promotion criteria to a Phase 2C decision (not to production):** ≥1 candidate with
rubric mean ≥4.0, no axis-fail condition, latency in the Excellent or Acceptable tier
(p95 ≤ 90 s; 90–120 s only with materially superior quality), completion rate ≥95%,
measured cost ≤ $0.10/output target (≤ $0.20 hard, ≤ $0.30 only for a labelled premium
candidate with materially better quality), and `legal_status = cleared_staging` with
written commercial terms and a no-training-on-input finding. Below that: recommend
"none — re-scope".

**Rollback:** flags off → candidates unreachable; registry rows deactivated without
deletion; no schema change touches Flux paths; V5 stays the API rollback target; the
research worker app is deleted independently of the V6 worker.

**Explicitly excluded:** Studio UI or any Studio change, billing, credits, pricing
exposure, production deployment or production identity work, customer-facing
outpainting, inpainting, ControlNet, LoRA training, video, `usage_ledger` wiring,
public asset URLs, browser-supplied workflow JSON, any change to the V5/V6 Flux path,
and any formal legal clearance (staging review only).

## 10. Decisions to validate (hypotheses, not settled design)

- Whether a ComfyUI outpaint graph (model, node set, mask feather, denoise range — all
  TBD) beats hosted candidates on seam quality at the absolute presets.
- Whether Track M latency is dominated by cold start or inference (cold/warm recorded
  separately).
- Whether hosted providers permit commercial use *and* no training on inputs.
- Whether a two-pass refine pass is warranted — only revisited if the Stage A leader
  narrowly misses seam/subject-integrity thresholds (per the confirmed workflow-shape rule).
- Whether the input envelope should cap at 4096px per side post-expansion or lower.

## 11. Status of the previous open questions

All four resolved by the confirmed decisions in section 0: latency/cost budgets and
tiers, reviewer and legal-review ownership with the four-status taxonomy, corpus
sourcing rules, and staged paid-track approval with per-stage caps and the $75–$100
ceiling.
