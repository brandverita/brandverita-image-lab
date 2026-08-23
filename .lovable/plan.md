# BrandVerita Generation Platform — Revised Plan (Provider-Neutral, Studio-Readiness)

## 1. Updated executive recommendation

Build the Generation Platform as a **provider-neutral** service behind one stable API contract, with provider adapters (`modal_comfyui`, `replicate`, `bfl_api`) selected per workflow version by the server-side registry. Execute in strict phase order: **Phase 0** is validation and decisions only (no behavior change) — it resolves the identity/JWT model, records the worker environment, and classifies the current Flux deployment as `research_only`. **Phase 1** is Flux-preserving modularization only: registry + adapter interface + Modal adapter, byte-identical Flux behavior, additive schema. Replicate evaluation (Phase 2), outpaint research (Phase 3), and the Studio contract (Phase 4) follow only after the prior phase's acceptance criteria pass. The smallest safe work packages are: Phase 0 = a read-only decision record; Phase 1 = one additive DB migration + one Modal API restructure (v6) + regression proof. No Studio UI, no outpainting, no billing, no production deployment in this request.

---

## 2. Decision record (confirmed answers to prior open questions)

| # | Decision |
|---|---|
| Q1 Data home | `comfy-ui` Supabase project is the **permanent staging / Image Lab** project. A **dedicated production Supabase project** will be created before any customer-facing Studio release. No production jobs, assets, usage data, or service-role credentials in `comfy-ui`. Main account app owns identity/billing/entitlement; Studio owns designs/Content Hub/Tela state. |
| Q2 Outpaint | `outpaint:v1` stays **Lab-only, experimental, `research_only`**. No self-hosted FLUX.1-Fill-dev for customers without verified commercial self-hosted license. Lab may evaluate Modal (research), Replicate-hosted editing endpoints, and BFL editing — each subject to model/node/provider/hosting terms. Promotion requires a documented ≥20 authorized-asset test set + quality rubric. |
| Q3 Identity | One authoritative identity issuer for the Generation API, resolved in **Phase 0 before backend modularization**. Server-side JWT verification (signature, `iss`, `aud`, expiry/nbf, stable user ID, workspace ID, entitlement claim or server-side lookup), ideally asymmetric keys + JWKS. No shared Supabase JWT secrets between projects; no "browser has a Studio session" trust. If the existing handoff token can't support required audience/claims, use a short-lived server-to-server token exchange. Final model stated in the Phase 0 decision record after inspecting the existing handoff and signing-key config. |
| Q4 Credits | No charging/deduction/payments this phase. Reservation-ready informational `usage_ledger` only: user, workspace, workflow key/version, provider, estimated credits, estimated provider cost, actual provider cost, actual GPU seconds, status `reserved`/`settled`/`void`. Design must later support reserve-before-dispatch and void-on-failure. |
| Q5 Retention | Staging/Lab: 30-day default retention, earlier user deletion, scheduled cleanup of expired objects, duration configurable per environment. Production: configurable per asset type and product policy (no fixed 90-day rule), user/workspace deletion and legal retention supported, signed URLs short-lived, no customer assets for provider/model improvement absent explicit terms + disclosures. |
| Q6 Presets | Approved preset-only list for `outpaint:v1`: `1080x1080`, `1200x627`, `1600x900`, `1080x1920`, `1080x1350`. No arbitrary dimensions. API owns preset definitions per workflow version; frontend fetches safe preset metadata only. |

---

## 3. Updated architecture

```text
myaccount.brandverita.io
        │ existing authenticated user / JWT handoff
        ▼
Studio at app.brandverita.io                    (future phase — no UI built now)
        │ provider-neutral generation requests
        ▼
BrandVerita Generation API (Modal FastAPI)
        ├── Authentication and entitlement layer (Phase 0 decision)
        ├── Workflow registry and release flags (Phase 1)
        ├── Asset authorization and lineage (Phase 2+)
        ├── Job lifecycle, idempotency, usage ledger
        ├── Provider adapter: replicate       (Phase 2, staging eval)
        ├── Provider adapter: bfl_api         (interface only)
        └── Provider adapter: modal_comfyui   (research_only)
                    │
                    ▼
            Provider-specific execution
                    │
                    ▼
       Private Generation Platform storage and metadata

Image Lab at brandverita-image-lab.netlify.app
        └── Calls STAGING Generation API only — testing, provider
            comparison, workflow QA, regression, operational diagnosis.
            Never a relay; never proxies Studio traffic; never points at
            production API / Supabase / storage / customer data.
```

All frontend clients (Lab and future Studio) call only the BrandVerita Generation API — never Replicate, BFL, Modal, or ComfyUI directly.

---

## 4. Revised data-model delta

All changes are **additive** migrations in `comfy-ui` (staging). No renames, no drops. Every new table gets GRANTs + RLS in the same migration (authenticated SELECT-own only; service_role ALL; no anon).

**`workflow_definitions`** (new; registry — full schema in §6). Service-role write. Clients read only through view `workflow_definitions_public` (key, version, display_name, status, allowed_dimensions, safe input-schema subset, presets, registry_visibility where `studio_safe`) — never provider internals, terms refs, or flags.

**`generation_assets`** (new; Phase 2 unless additive prep approved in Phase 1):
`id uuid pk`, `owner_id uuid`, `workspace_id uuid null`, `sha256 text`, `bucket text`, `storage_path text`, `content_type text`, `file_size bigint`, `width int`, `height int`, `kind text` (input|output), `source_asset_id uuid null fk`, `job_id uuid null fk`, `workflow_key text`, `workflow_version text`, `provenance jsonb`, `created_at`, `deleted_at`, `expires_at`. New private bucket `generation-assets` for inputs; `generation-outputs` retained for outputs.

**`usage_ledger`** (new; informational, non-charging):
`id uuid pk`, `user_id uuid`, `workspace_id uuid null`, `job_id uuid fk`, `workflow_key text`, `workflow_version text`, `provider text`, `estimated_credits numeric`, `estimated_provider_cost numeric`, `actual_provider_cost numeric null`, `gpu_seconds numeric null`, `status text` (reserved|settled|void), `created_at`, `settled_at`. Service-role only.

**`generation_jobs` extensions** (additive columns):
`workspace_id uuid null`, `workflow_version text`, `workflow_config_hash text`, `provider text`, `provider_model text`, `provider_job_reference text`, `input_asset_ids uuid[]`, `output_asset_ids uuid[]`, `inputs jsonb` (validated safe inputs only), `worker_version text`, `usage_ledger_id uuid null`, `error_category text`, `internal_error_ref text`, `queued_at timestamptz`, `started_at timestamptz`, `expires_at timestamptz`. (`error_code`, `completed_at`, `progress` already exist.)

**State machine** (application-owned, enforced in the API):
```text
queued → dispatching → running → uploading_output → completed
queued|dispatching|running|uploading_output → failed
queued → cancelled
queued|dispatching|running → expired
```
`progress_percent` is informational only; clients must not infer state from it. All provider errors normalize to safe user-facing codes + internal categories — no raw provider exceptions, URLs, tokens, model config, or stack traces to clients.

---

## 5. Provider adapter specification

Backend-only interface; the frontend contract never changes per provider:

```text
submit_generation(job, validated_inputs, workflow_definition) -> provider_job_reference
get_generation_status(provider_job_reference) -> normalized status + progress
cancel_generation(provider_job_reference) -> best-effort
normalize_provider_result(provider_response) -> { output bytes/refs, metadata }
estimate_cost(validated_inputs, workflow_definition) -> { credits, provider_cost }
```

- **`modal_comfyui`** (implemented, Phase 1): current working Flux path moved verbatim — server-built ComfyUI graph, `ComfyUIWorker.generate_image`, storage upload, job updates. All self-hosted FLUX dev workflows are `research_only` until commercial self-hosted rights are documented; never dispatchable from Studio production.
- **`replicate`** (Phase 2, staging only): first hosted commercial candidate. Async prediction + polling/webhook per current Replicate API; prediction ID stored in `provider_job_reference`; exact model/version identifier, terms reference, and cost metadata recorded on the registry row; tokens server-only; workflow stays `pending_review` until legal/data-handling review is recorded. Do not self-host weights from a Replicate listing assuming hosted rights transfer.
- **`bfl_api`** (Phase 2, interface + registry support only): no production dispatch unless later approved; no customer/private production assets sent until data-use/retention/privacy/commercial terms are reviewed and accepted.

---

## 6. Registry schema and initial entries

**`workflow_definitions`** columns (mandatory):
`id uuid pk`, `key text`, `version text`, `status text` (draft|testing|active|deprecated|disabled), `display_name text`, `description text`, `provider text`, `provider_model text`, `provider_workflow_reference text`, `commercial_status text` (research_only|commercial_hosted|licensed_self_hosted|pending_review|blocked), `provider_terms_reference text`, `provider_terms_verified_at timestamptz`, `data_handling_profile text`, `allowed_envs text[]`, `production_enabled bool default false`, `enabled_for_studio bool default false`, `registry_visibility text` (internal|studio_safe|hidden), `rollout_percentage int` (0–100), `allowed_workspace_ids uuid[] null`, `feature_flag text`, `input_schema jsonb`, `output_schema jsonb`, `allowed_dimensions jsonb`, `estimated_credits numeric`, `config_hash text` (immutable), `worker_version text`, `comfyui_ref text`, `model_manifest_ref text`, `created_at`, `retired_at`, unique(`key`,`version`).

**Commercial-use gate (non-negotiable)**: Studio production dispatch requires `commercial_status ∈ {commercial_hosted, licensed_self_hosted}` AND documented provider/model reference AND stored terms reference AND recorded verification date AND approved data-handling profile AND `production_enabled = true`. `research_only` is rejected server-side for production/Studio-origin requests regardless of frontend state or hidden URLs.

**Config immutability**: `config_hash` is immutable; any material change to provider model, graph, prompt template, custom-node config, or inference settings creates a new workflow version, never an edit.

**Initial seed rows** (staging):
```text
flux_text_to_image:v1            provider=modal_comfyui  commercial_status=research_only
                                 status=active  allowed_envs=[staging]  production_enabled=false
                                 enabled_for_studio=false  registry_visibility=internal
flux_text_to_image:v1-commercial-candidate
                                 provider=replicate  commercial_status=pending_review
                                 status=draft  allowed_envs=[staging]  production_enabled=false
                                 enabled_for_studio=false  registry_visibility=internal
outpaint:v1                      provider=modal_comfyui  commercial_status=research_only
                                 status=draft  allowed_envs=[staging]  production_enabled=false
                                 enabled_for_studio=false  registry_visibility=internal
```

---

## 7. Phase 0 — validation checklist (no behavior change)

Owner: ops + API. Output: a concise decision record.

- [ ] Record exact worker image: ComfyUI commit/version, custom-node list, model manifest, Python/CUDA/PyTorch versions, build reference → stored as `comfyui_ref` / `model_manifest_ref` on the Flux registry row.
- [ ] Measure baseline from recent `generation_jobs`: queue time, cold-start, execution, E2E, approximate GPU cost per image.
- [ ] Inspect the existing Studio ↔ myaccount JWT handoff and Supabase signing-key configuration (algorithm, JWKS availability, `iss`/`aud` claims, workspace/entitlement claims).
- [ ] Decide and record: **direct JWT verification vs short-lived server-to-server token exchange** — the single identity model for the Generation API.
- [ ] Confirm the exact deployed FLUX model/source and classify it `research_only` pending verified commercial self-hosted rights.
- [ ] Create provider/legal review checklist for Replicate and BFL hosted options (commercial use, data-use/retention, privacy, pricing).
- [ ] Confirm isolation: Image Lab cannot reach future production API/data (registry `allowed_envs`, separate projects/secrets — by construction, not convention).
- [ ] Confirm `generation_usage.period` format for ledger compatibility.

## 8. Phase 1 — implementation checklist (smallest safe package)

**One additive Supabase migration** (in `comfy-ui`, staging):
- Create `workflow_definitions` + GRANTs + RLS + safe-column view `workflow_definitions_public`; seed the three initial rows from §6.
- Add the `generation_jobs` extension columns from §4 (nullable, no backfill required).
- Defer `generation_assets` and `usage_ledger` tables unless the additive prep is approved in the same migration (they are inert until Phase 2 code exists).

**Modal API restructure (v6)** — same app, file-level split, no new Modal apps:
- `supabase_rest.py` — existing httpx helpers (unchanged).
- `registry.py` — load/cache registry (60s), evaluate env + status + flag + commercial gate.
- `adapters/base.py` — the §5 interface; `adapters/modal_comfyui.py` — today's dispatch + `build_flux_workflow` moved **verbatim**; `adapters/replicate.py`, `adapters/bfl_api.py` — stubs raising `workflow_unavailable`.
- `jobs.py` — insert/update/respond + state machine enforcement; `api.py` — thin FastAPI wiring.
- `POST /v1/generations` accepts the legacy flat shape (routed to `flux_text_to_image:v1`) and the structured `{workflow_id, workflow_version, inputs}` shape; unknown → 400 `unsupported_workflow`; not-allowed → 403 `workflow_unavailable`.
- New `GET /v1/workflows` — safe internal metadata for the Lab (registry_visibility=internal rows, safe fields only).
- Job records now write `workflow_version`, `workflow_config_hash`, `provider`, `provider_model`, `worker_version`, `queued_at`, `started_at`.
- `/health` reports `version: "v6"` + loaded registry keys.

**Image Lab frontend (this repo)**:
- `src/lib/generationApi.ts`: add `listWorkflows()` + `WorkflowInfo` type; legacy `createGeneration` path untouched.
- Dev panel: display `provider`, `workflow_version`, `config_hash` (first 8 chars) from job responses.
- No upload UI, no outpaint UI, no workflow picker beyond read-only display.

**Explicitly not in Phase 1**: customer asset upload, asset/usage behavior, Studio anything, outpaint execution, Replicate/BFL dispatch.

## 9. Phase 1 acceptance criteria and regression plan

1. `GET /health` returns `version: "v6"` and lists `flux_text_to_image:v1`.
2. Byte-level regression: the ComfyUI graph built by the new Modal adapter for a fixed (prompt, negative, width, height, seed) input equals the v5 builder output.
3. E2E: one Flux job from the Lab UI completes; image renders; recent jobs list loads.
4. Contract tests: legacy flat shape accepted; structured shape with `flux_text_to_image:v1` accepted; unknown workflow → 400; `outpaint:v1` (draft) → 403; stub providers → 403.
5. New job rows carry `provider=modal_comfyui`, `workflow_version`, `config_hash`, `worker_version`, `queued_at`/`started_at`.
6. `GET /v1/workflows` returns safe fields only (verified: no terms refs, no model internals).
7. AuthZ unchanged: other user's job → 404; unauthenticated → 401.
8. Typecheck + build green; Netlify deploy of the Lab unchanged in behavior.
Rollback: redeploy v5 `api.py`; migration is additive so no DB rollback needed. Registry disable is an `UPDATE status='disabled'`.

## 10. Risks, assumptions, genuinely unresolved items

- **Identity model** (Q3) is decided in principle but the concrete mechanism depends on what Phase 0 finds in the existing handoff (algorithm, JWKS, claims). This is the one item that can change Phase 2+ design.
- Replicate/BFL commercial + data-handling terms are **unverified**; the `pending_review` registry rows exist precisely so nothing ships before review.
- FLUX self-hosted commercial rights are **not verified** — current deployment is research/staging only by policy.
- Phase 1 assumes the registry cache and state-machine enforcement don't perturb the working dispatch path; the byte-level graph regression is the guard.
- Assumption: `ComfyUIWorker` needs no changes in Phase 1 (adapter calls it exactly as v5 does).

## 11. Explicitly deferred (not in this request)

Studio UI and any Studio code; outpaint execution and its Lab UI; Replicate/BFL dispatch implementation; customer asset upload/finalization flow; `generation_assets`/`usage_ledger` runtime behavior; rate limiting; credit deduction/billing; production Supabase project, production Modal app, and prod secrets; scheduled retention cleanup job; stuck-job cron; Studio identity enforcement (beyond the Phase 0 decision record); Content Hub handoff.
