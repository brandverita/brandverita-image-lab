# Phase 2B — Controlled Outpaint Provider and Workflow Evaluation (planning only)

Scope: staging-only research. No Studio surface, no billing, no production deployment,
no customer-facing outpainting. Nothing in this plan changes a deployed service until
approved; implementation is a later, separate approval.

Starting point (from your Phase 2A milestone): private `generation-assets` bucket,
28/28 asset API/security checks passing, PNG/JPEG/WebP upload+finalize working,
V6 Flux generation functional, V5 healthy as rollback, `usage_ledger` unwired at 0 rows.

## 1. Executive recommendation

Treat outpainting as a *provider selection experiment*, not a feature build. Phase 2B
produces one artifact: a signed evaluation report that names one recommended
`outpaint:v1` provider path, with measured quality, latency, cost, and legal status —
plus the losing candidates and why. Every candidate stays `research_only`,
`production_enabled = false`, `enabled_for_studio = false` for the entire phase, and the
API rejects dispatch of a research workflow from anything other than an allow-listed
internal account in staging.

## 2. Asset-to-job contract (staging only)

Add `source_asset_id` as an accepted request field on `POST /v1/generations` **only for
workflows whose registry entry declares `requires_source_asset = true`**.

Server-side gate, in order, before any provider dispatch:

1. Caller is JWKS-verified and on the internal allow-list.
2. Workflow key/version resolves in the registry and is `research_only` + staging.
3. Asset row exists, `owner_id = auth user`, `status = 'ready'`, `deleted_at is null`,
   `expires_at > now()`, `kind = 'input'`.
4. Asset dimensions/pixels are within the workflow's declared input envelope.
5. Requested output preset is in the workflow's `allowed_output_presets`.

Failures map to existing codes: `asset_not_found` 404, `asset_not_owned` 404,
`asset_not_ready` 409, `asset_expired` 409 (new), `invalid_request` 400,
`workflow_not_available` 403. Job row records `source_asset_id` (FK to
`generation_assets`) so lineage is queryable from either direction. No public URL is
ever accepted as input; no browser-supplied graph JSON is ever accepted.

Ownership is re-checked at dispatch time inside the worker path, not only at request
time, so a revoked/expired asset cannot be used by a queued job.

## 3. Candidate workflow registry scheme

Candidates are registry rows, not code branches. Key/version naming:

```text
outpaint:v1                     logical workflow key
  candidate id: outpaint-v1-<provider>-<model>-<nn>
  e.g. outpaint-v1-modal-comfy-sdxlinpaint-01
       outpaint-v1-replicate-<model>-01
       outpaint-v1-bfl-<model>-01
```

Every candidate row carries: `status='research_only'`, `visibility='internal'`,
`production_enabled=false`, `enabled_for_studio=false`, `requires_source_asset=true`,
`allowed_output_presets`, `input_envelope`, `provider`, `provider_model`,
`config_hash` (immutable once activated), `commercial_status`, `license_ref`,
`artifact_pins` (repo URL + full SHA + filename + SHA256 + license, per the Phase 1 rule),
`candidate_notes`. Activated versions remain immutable; a change means a new candidate id.

## 4. Provider evaluation framework

Three tracks, same request contract, same corpus, same rubric:

- **Track M — Modal + ComfyUI (self-hosted research).** Highest control and lowest
  marginal cost, most engineering. Runs on a dedicated research worker app, separate
  from the pinned Flux V6 worker, so Flux cannot regress.
- **Track R — Replicate-hosted candidates.** Fastest to measure, per-call cost, license
  and data-retention terms must be read per model.
- **Track B — BFL candidates.** Evaluate quality ceiling and commercial terms.

Adapters live behind the existing provider-adapter interface; each track is one adapter
plus registry rows. Secrets (Replicate/BFL keys) are server-side only, never in the
frontend, and are added as Supabase/Modal secrets at implementation time.

Comparability rules: identical corpus, identical output presets, identical seeds where
the provider exposes them, same reviewer set, blinded filenames during scoring.

## 5. Per-run record (what every test run must store)

One row per run in a new staging table `outpaint_eval_runs` (service-role writes only,
SELECT to the internal allow-list):

- Identity: `run_id`, `job_id`, `source_asset_id`, `output_asset_id`, `operator_user_id`
- Workflow: `workflow_key`, `workflow_version`, `candidate_id`, `config_hash`
- Provider: `provider`, `provider_model`, `provider_call_id`, `worker_version`/image id
- Request: `output_preset`, expansion direction/ratio, seed, steps/guidance if exposed
- Timing: `queued_at`, `dispatched_at`, `first_byte_at`, `completed_at`,
  `provider_latency_ms`, `total_latency_ms`, cold/warm flag
- Cost: `gpu_seconds`, `estimated_cost`, `actual_provider_cost`, currency
- Result: `status`, `error_code`, `error_message`, output dimensions, bytes, SHA256
- Quality: rubric scores per reviewer + mean, reviewer ids, blinded flag, notes
- Legal/data review: `license_ref`, `commercial_status`, provider data-retention finding,
  training-on-input flag, reviewer + date, `legal_status` in
  `pending | cleared_staging | blocked`

No prompts, tokens, or image bytes are logged to stdout or the browser console.

## 6. Evaluation corpus and human rubric

Fixed corpus of **24 authorized assets** (20 minimum + 4 spares), uploaded once through
the existing Phase 2A pipeline, frozen by `asset_id` list and each asset's SHA256 so
every candidate sees byte-identical inputs. Composition target:

- 6 product-on-plain-background, 4 product-in-scene, 4 people/portrait,
  4 interior/exterior scene, 3 text/logo-bearing, 3 hard cases
  (fine repeating texture, strong perspective, shallow depth of field)
- Aspect spread across the 5 permitted dimension presets; both landscape and portrait
- Provenance: BrandVerita-owned or explicitly licensed only. Each asset gets a
  provenance note before it enters the corpus. No customer data.

Expansion presets per asset: 1.25x width, 1.5x width, 1.5x height, and one
asymmetric single-side expansion — so 4 runs per asset per candidate.

Rubric, 1–5 per axis, two independent reviewers, blinded, disagreement >1 point
triggers a third review:

1. Seam continuity (no visible boundary at the original edge)
2. Structural plausibility (perspective, horizon, geometry continue correctly)
3. Texture/material fidelity
4. Colour and lighting match
5. Subject integrity (no clone/regrow of the main subject or limbs)
6. Text/logo behaviour (no invented lettering; blank when unknown)
7. Artefact freedom (no ghosting, halo, watermark, mush)

Aggregate: mean of axes; a candidate fails outright on any single axis scoring ≤2 on
more than 20% of runs regardless of mean.

## 7. Asset flow, temp files, output storage, lineage

1. API resolves the asset and issues a **short-lived server-side signed read URL**
   (single-use where supported); the URL is passed to the provider/worker, never to the
   browser and never persisted in the job row.
2. Worker downloads to an ephemeral path under its own temp dir, keyed by
   `job_id`, verifies SHA256 against the asset row, and deletes the file in a `finally`
   block. No writes outside temp; nothing survives the container.
3. Track R/B: input is delivered via the same short-lived signed URL; retention terms
   are recorded as part of the legal review before any run.
4. Output is written to the private `generation-assets` bucket at
   `<user_id>/<output_asset_id>/original.<ext>` as a **new row** with `kind='output'`,
   `source_asset_id` set to the input, plus `job_id`, `workflow_key`,
   `workflow_version`, `provenance`, and the phase's staging TTL. Browser reads only via
   short-lived signed read URLs after an ownership check — bucket stays private.
5. Lineage is therefore both `output_asset.source_asset_id` and
   `generation_jobs.source_asset_id` → identical, cross-checkable.
6. `usage_ledger` stays unwired in 2B; cost data lives in `outpaint_eval_runs`.

## 8. Feature flags and safety gates

- Registry gate: dispatch rejected unless `status != 'research_only'` **or** the caller
  is internal-allow-listed **and** environment is staging. Production environment
  rejects `research_only` unconditionally, server-side.
- Env gate: `OUTPAINT_EVAL_ENABLED` (server) defaults false; per-provider gates
  `PROVIDER_REPLICATE_ENABLED`, `PROVIDER_BFL_ENABLED` default false.
- Client gate: `VITE_OUTPAINT_EVAL_ENABLED` default false; UI lives in an
  internal-only panel in Image Lab, never in Studio. No Studio code is touched.
- `enabled_for_studio=false` and `production_enabled=false` on every candidate;
  a Studio-facing read of the registry filters them out at the API layer.
- Kill switch: flipping `OUTPAINT_EVAL_ENABLED` to false stops all candidate dispatch
  without touching Flux V6 or V5.

## 9. Test, promotion, rollback, exclusions

**Phase test criteria (all required):** contract negative tests pass (not-owned,
not-ready, expired, over-envelope, non-preset, cross-user, unauthenticated); no
candidate is dispatchable with flags off; no candidate appears in a Studio-shaped
registry read; production-mode dispatch of a `research_only` candidate is rejected;
input temp files provably deleted; output rows carry correct lineage; Flux V6 unchanged
and V5 healthy throughout; no secret reaches the client bundle.

**Promotion criteria to a Phase 2C decision (not to production):** ≥1 candidate with
rubric mean ≥4.0, no axis-fail condition, p95 latency within an agreed budget,
measured cost per image within budget, and `legal_status = cleared_staging` with written
commercial terms and a no-training-on-input finding. Below that, the recommendation is
"none — re-scope".

**Rollback:** flags off → candidates unreachable; registry rows can be deactivated
without deletion (immutability preserved); no schema change touches Flux paths; V5 stays
the API rollback target; the research worker app is deleted independently of the V6
worker.

**Explicitly excluded from Phase 2B:** Studio UI or any Studio change, billing,
credits, pricing exposure, production deployment or production identity work,
customer-facing outpainting, inpainting, ControlNet, LoRA training, video,
`usage_ledger` wiring, public asset URLs, browser-supplied workflow JSON, and any
change to the V5/V6 Flux generation path.

## 10. Decisions to validate (assumptions flagged, not settled)

Each is a hypothesis to be tested and recorded, not a chosen design:

- Whether a ComfyUI inpaint/outpaint graph (SDXL-inpaint-class model + pad/mask +
  differential-diffusion-style blending) beats hosted candidates on seam quality —
  exact model, node set, mask feather, and denoise range all TBD by experiment.
- Whether latency is dominated by cold start or by inference for Track M.
- Whether hosted providers permit commercial use *and* no training on inputs.
- Whether a two-pass approach (coarse expand, then edge-region refine) is worth its
  cost multiple.
- Whether the input envelope should cap at 4096px per side post-expansion or lower.
- Whether output presets should be expansion *ratios* or absolute target dimensions.

## 11. Open questions for you

1. Latency and cost budgets to score against (target p95 seconds, target cost/image)?
2. Who are the two rubric reviewers, and who signs the legal/data review?
3. Can the 24-asset corpus be sourced from BrandVerita-owned material, or should I
   specify licensed stock instead?
4. Are Replicate and BFL both in scope for paid test spend in this phase, and is there a
   spend ceiling per track?
