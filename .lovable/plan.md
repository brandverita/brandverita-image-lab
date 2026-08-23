# BrandVerita Generation Platform — Revised Plan (Provider-Neutral, Studio-Readiness)

Approved 2026-08-23 with two corrections and one addition (incorporated below). Phase 0 executed as a read-only audit — see the Phase 0 decision record artifact. Phase 1 awaits explicit approval.

## 1. Executive recommendation

Build the Generation Platform as a **provider-neutral** service behind one stable API contract, with provider adapters (`modal_comfyui`, `replicate`, `bfl_api`) selected per workflow version by the server-side registry. Strict phase order: **Phase 0** validation/decisions only (done — decision record delivered); **Phase 1** Flux-preserving modularization (registry + adapter interface + Modal adapter, byte-identical Flux behavior, additive schema); Phase 2 Replicate staging evaluation + asset/ledger foundations; Phase 3 outpaint research (Lab-only); Phase 4 Studio integration contract. No Studio UI, outpainting, billing, or production deployment until the relevant phase is approved.

## 2. Decision record (confirmed answers)

| # | Decision |
|---|---|
| Q1 Data home | `comfy-ui` is the **permanent staging / Image Lab** project. A **dedicated production Supabase project** is created before any customer-facing Studio release. No production jobs/assets/usage/service-role credentials in `comfy-ui`. Main account app owns identity/billing/entitlement; Studio owns designs/Content Hub/Tela state. |
| Q2 Outpaint | `outpaint:v1` Lab-only, experimental, `research_only`. No self-hosted FLUX.1-Fill-dev for customers without verified commercial self-hosted license. Lab may evaluate Modal (research), Replicate-hosted editing, BFL editing — each subject to model/node/provider/hosting terms. Promotion requires a documented ≥20 authorized-asset test set + quality rubric. |
| Q3 Identity | One authoritative identity issuer, resolved in Phase 0 (see decision record: JWKS-based verification recommended; Studio token-claims inspection still required). Server-side verification of signature, `iss`, `aud`, expiry/nbf, stable user ID, workspace ID, entitlement claim or server-side lookup. No shared Supabase JWT secrets; no browser-session trust. |
| Q4 Credits | No charging this phase. Reservation-ready informational `usage_ledger` only (user, workspace, workflow key/version, provider, estimated credits, estimated/actual provider cost, actual GPU seconds, status reserved/settled/void). Must later support reserve-before-dispatch and void-on-failure. |
| Q5 Retention | Staging/Lab: 30-day default, earlier user deletion, scheduled cleanup, configurable per environment. Production: configurable per asset type and product policy; user/workspace deletion and legal retention supported; signed URLs short-lived; no customer assets for provider/model improvement absent explicit terms + disclosures. |
| Q6 Presets | `outpaint:v1` preset-only: `1080x1080`, `1200x627`, `1600x900`, `1080x1920`, `1080x1350`. No arbitrary dimensions. API owns presets per workflow version; frontend fetches safe preset metadata only. |

## 3. Architecture

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
                    ▼
            Provider-specific execution
                    ▼
       Private Generation Platform storage and metadata

Image Lab (brandverita-image-lab.netlify.app)
        └── Staging Generation API only. Never a relay; never proxies Studio
            traffic; never points at production API / Supabase / storage / data.
```

All frontend clients call only the BrandVerita Generation API — never Replicate, BFL, Modal, or ComfyUI directly.

## 4. Data-model delta (additive; comfy-ui staging)

Every new table: GRANTs + RLS in the same migration (authenticated SELECT-own; service_role ALL; no anon).

- **`workflow_definitions`** (new; §6 schema). Clients never read it directly — `GET /v1/workflows` is server-filtered (Correction 1).
- **`generation_assets`** (Phase 2): `id`, `owner_id`, `workspace_id`, `sha256`, `bucket`, `storage_path`, `content_type`, `file_size`, `width`, `height`, `kind` (input|output), `source_asset_id`, `job_id`, `workflow_key`, `workflow_version`, `provenance jsonb`, `created_at`, `deleted_at`, `expires_at`. New private bucket `generation-assets`; `generation-outputs` retained for outputs.
- **`usage_ledger`** (Phase 2; informational): `id`, `user_id`, `workspace_id`, `job_id`, `workflow_key`, `workflow_version`, `provider`, `estimated_credits`, `estimated_provider_cost`, `actual_provider_cost`, `gpu_seconds`, `status` (reserved|settled|void), `created_at`, `settled_at`. Service-role only.
- **`generation_jobs` extensions** (Phase 1, additive nullable columns): `workspace_id`, `workflow_version`, `workflow_config_hash`, `provider`, `provider_model`, `provider_job_reference`, `input_asset_ids uuid[]`, `output_asset_ids uuid[]`, `inputs jsonb` (validated safe inputs only), `worker_version`, `usage_ledger_id`, `error_category`, `internal_error_ref`, `queued_at`, `started_at`, `expires_at`.

**State machine** (application-owned, enforced in the API):
```text
queued → dispatching → running → uploading_output → completed
queued|dispatching|running|uploading_output → failed
queued → cancelled
queued|dispatching|running → expired
```
`progress_percent` is informational only; clients never infer state from it. Provider errors normalize to safe user-facing codes + internal categories — no raw provider exceptions, URLs, tokens, model config, or stack traces to clients.

## 5. Provider adapter specification

Backend-only interface; the frontend contract never changes per provider:

```text
submit_generation(job, validated_inputs, workflow_definition) -> provider_job_reference
get_generation_status(provider_job_reference) -> normalized status + progress
cancel_generation(provider_job_reference) -> best-effort
normalize_provider_result(provider_response) -> { output bytes/refs, metadata }
estimate_cost(validated_inputs, workflow_definition) -> { credits, provider_cost }
```

- **`modal_comfyui`** (Phase 1, implemented): current working Flux path moved verbatim. Self-hosted FLUX dev workflows are `research_only` until commercial rights documented; never dispatchable from Studio production.
- **`replicate`** (Phase 2, staging only): async prediction + polling/webhook; prediction ID in `provider_job_reference`; exact model/version + terms reference + cost metadata on the registry row; tokens server-only; stays `pending_review` until legal/data-handling review recorded. No self-hosting of Replicate-listed weights assuming hosted rights transfer.
- **`bfl_api`** (Phase 2, interface + registry support only): no production dispatch unless later approved; no customer/private production assets until data-use/retention/privacy/commercial terms accepted.

## 6. Registry schema, immutability, visibility

**`workflow_definitions`**: `id`, `key`, `version`, `status` (draft|testing|active|deprecated|disabled), `display_name`, `description`, `provider`, `provider_model`, `provider_workflow_reference`, `commercial_status` (research_only|commercial_hosted|licensed_self_hosted|pending_review|blocked), `provider_terms_reference`, `provider_terms_verified_at`, `data_handling_profile`, `allowed_envs text[]`, `production_enabled bool default false`, `enabled_for_studio bool default false`, `registry_visibility` (internal|studio_safe|hidden), `rollout_percentage int 0–100`, `allowed_workspace_ids uuid[] null`, `feature_flag`, `input_schema jsonb`, `output_schema jsonb`, `allowed_dimensions jsonb`, `estimated_credits`, `config_hash`, `worker_version`, `comfyui_ref`, `model_manifest_ref`, `created_at`, `retired_at`, unique(`key`,`version`).

**Correction 2 — immutability split**:
- *Immutable once the version is activated* (enforced by DB trigger rejecting UPDATE): `key`, `version`, `provider`, `provider_model`, `provider_workflow_reference`, `config_hash`, `input_schema`, `output_schema`, `model_manifest_ref`, `comfyui_ref`. A material change to any of these creates a new workflow version.
- *Controlled but mutable* (service-role only, audited): `status`, `production_enabled`, `enabled_for_studio`, `registry_visibility`, `rollout_percentage`, `allowed_workspace_ids`, `feature_flag`, `retired_at`, `provider_terms_verified_at`, `data_handling_profile`. Incident disable or rollout change never creates a new version.

**Correction 1 — visibility / authorization**: `GET /v1/workflows` is server-filtered by authenticated caller + environment; the safe view is a column allowlist, not an authorization layer:
- Lab allowlisted internal users → safe internal metadata for research workflows (`registry_visibility=internal`, caller's env).
- Studio users → only `studio_safe` workflows that are active, commercially approved, `enabled_for_studio`, and allowed in the current environment.
- Unauthenticated or any other caller → no workflows (empty/401).
- No client response may include raw graphs, provider secrets, model file paths, deployment references, API tokens, or infrastructure internals.

**Commercial-use gate**: Studio production dispatch requires `commercial_status ∈ {commercial_hosted, licensed_self_hosted}` + documented provider/model reference + stored terms reference + verification date + approved data-handling profile + `production_enabled=true`. `research_only` is rejected server-side for production/Studio-origin requests regardless of frontend state.

**Initial seed rows** (staging): `flux_text_to_image:v1` (modal_comfyui, research_only, active, staging, internal), `flux_text_to_image:v1-commercial-candidate` (replicate, pending_review, draft, staging, internal), `outpaint:v1` (modal_comfyui, research_only, draft, staging, internal).

## 7. Phase 0 — validation checklist (executed 2026-08-23)

Read-only audit complete; full evidence in the Phase 0 decision record artifact. Covered: deployment manifest (API v5 live, worker image, models, DB, storage), baseline performance/cost (E2E ~55–72s, ~$0.02/image on A10G), identity recommendation (JWKS), environment separation, provider/legal review records (Correction 3: structured per-candidate records with provider, exact model/endpoint/version, hosted vs self-hosted, intended use, commercial-use conclusion, input/output retention conclusion, training/improvement-use conclusion, customer-data permission, terms URL, retrieval date/version, review owner/date, restrictions, approval status), and the Phase 1 go/no-go recommendation.

Outstanding Phase 0 follow-ups (user-supplied): ComfyUI fork commit hash (to pin), Supabase signing-keys migration status for comfy-ui, a sample Studio↔myaccount handoff token for claims inspection.

## 8. Phase 1 — implementation checklist (smallest safe package; awaits approval)

**One additive Supabase migration** (comfy-ui, staging): `workflow_definitions` + GRANTs + RLS + immutability trigger + seed rows; `generation_jobs` extension columns (nullable, no backfill). Defer `generation_assets`/`usage_ledger` tables to Phase 2.

**Modal API restructure (v6)** — same app, file-level split: `supabase_rest.py` (existing httpx helpers), `registry.py` (load/cache 60s, env + status + flag + commercial gate), `adapters/base.py` + `adapters/modal_comfyui.py` (verbatim Flux move) + `replicate.py`/`bfl_api.py` stubs (403 `workflow_unavailable`), `jobs.py` (state machine), thin `api.py`. `POST /v1/generations` accepts legacy flat shape (routed to `flux_text_to_image:v1`) and structured `{workflow_id, workflow_version, inputs}`; unknown → 400 `unsupported_workflow`; disallowed → 403. New `GET /v1/workflows` with Correction-1 server filtering. Jobs write `workflow_version`, `workflow_config_hash`, `provider`, `provider_model`, `worker_version`, `queued_at`, `started_at`. `/health` reports `version: "v6"` + registry keys. Add JWKS-based JWT verification (ES256, iss/aud/exp/nbf) alongside the existing auth check. Mark the 2 stale 2026-08-19 `queued` rows `expired`.

**Image Lab frontend**: `src/lib/generationApi.ts` adds `listWorkflows()` + `WorkflowInfo`; dev panel shows `provider`, `workflow_version`, `config_hash` prefix. No upload UI, no outpaint UI, no picker.

**Not in Phase 1**: customer asset upload, asset/usage runtime behavior, Studio anything, outpaint execution, Replicate/BFL dispatch.

## 9. Phase 1 acceptance criteria and regression plan

1. `/health` returns `version: "v6"` and lists `flux_text_to_image:v1`.
2. Byte-level regression: adapter-built graph for fixed (prompt, negative, w, h, seed) equals v5 output.
3. E2E: one Flux job from the Lab completes; image renders; recent jobs load.
4. Contract tests: legacy + structured shapes accepted; unknown workflow → 400; `outpaint:v1` (draft) → 403; stub providers → 403; unauthenticated `GET /v1/workflows` → none.
5. New jobs carry `provider=modal_comfyui`, `workflow_version`, `config_hash`, `worker_version`, `queued_at`/`started_at`.
6. `GET /v1/workflows` returns safe fields only; immutability trigger rejects edits to immutable fields on an active version.
7. AuthZ unchanged: other user's job → 404; unauthenticated → 401.
8. Typecheck + build green; Netlify Lab deploy unchanged in behavior.
Rollback: redeploy v5; migration additive (no DB rollback); registry disable = `UPDATE status='disabled'` (mutable field).

## 10. Risks, assumptions, unresolved items

- Studio identity sub-decision (handoff-token claims vs token exchange) awaits a sample token — does not block Phase 1.
- Replicate/BFL commercial + data-handling terms unverified — `pending_review` rows exist so nothing ships before review.
- FLUX self-hosted commercial rights not yet recorded (schnell weights are Apache-2.0 per HF listing; fork + custom nodes + deployment terms still need the review record) — research_only stands until recorded.
- ComfyUI fork commit unpinned in the worker image — record and pin during Phase 1.
- Assumption: `ComfyUIWorker` needs no changes in Phase 1.

## 11. Explicitly deferred

Studio UI/code; outpaint execution and Lab UI; Replicate/BFL dispatch; customer asset upload/finalization; `generation_assets`/`usage_ledger` runtime behavior; rate limiting; credit deduction/billing; production Supabase project, production Modal app, prod secrets; scheduled retention cleanup; stuck-job cron (beyond marking the 2 stale rows); Content Hub handoff.
