# BrandVerita Generation Platform — Studio-Readiness & outpaint:v1 Plan

## 1. Executive recommendation

Convert the working Image Lab backend into a versioned **Generation Platform** in five phases: (0) validate current state, (1) modularize the API around a server-side workflow registry without touching the Flux path, (2) add asset/lineage tables and a structured job model, (3) build `outpaint:v1` as an experimental, Lab-only workflow behind a feature flag, (4) define and freeze the Studio integration contract, (5) staging/production environment split with observability and cost controls. Studio UI work is explicitly out of scope; only the contract is delivered.

Priority markers used below: **[pre-Studio]** required before Studio integration · **[pre-prod]** required before production customer access · **[later]** useful later.

---

## 2. Current-state assessment (verified this session)

Confirmed by direct inspection:

- **Supabase project `comfy-ui`** (ref `thspgkedjkiltrcimond`) holds: `allowed_emails`, `generation_jobs` (id, user_id, workflow_id, status, prompt, negative_prompt, prompt_hash, idempotency_key, modal_call_id, output_path, result_url, width, height, seed, progress, error_code, error_message, created/updated/completed_at), `generation_usage` (period text, jobs_count, gpu_seconds). RLS: SELECT-only policies for `authenticated` on both generation tables, gated by the `allowed_emails` allowlist via `current_user_allowed()`. No `generation_assets` or `workflow_definitions` tables exist yet.
- **Storage**: one private bucket `generation-outputs`. Outputs stored as PNG, signed fresh on every read.
- **Modal API (`api.py` v5)**: FastAPI app `brandverita-api`, endpoints `/health`, `/v1/auth/check`, `POST /v1/generations`, `GET /v1/generations/{job_id}`, `GET /v1/generations/{job_id}/result`. Single hardcoded workflow `flux-schnell-txt2img-v1`; workflow graph built server-side in `build_flux_workflow()`; `run_generation` Modal function orchestrates worker call → storage upload → job update. Auth = Supabase JWT verified via direct `httpx` REST calls; Supabase access also via `httpx` (no supabase-py). `modal_call_id` always written after spawn.
- **Worker**: Modal app `comfyui-generation-worker`, class `ComfyUIWorker.generate_image(workflow_json) -> PNG bytes` (Flux Schnell via ComfyUI).
- **Frontend (this repo)**: Netlify-hosted, magic-link auth + allowlist gate, typed client `src/lib/generationApi.ts`, polling hook `use-generation.ts`, dev panel with job/Modal-call/output-path observability, recent jobs from Supabase.

**Validation checklist before Phase 1** (owner: ops, read-only):
- [ ] Confirm exact ComfyUI version/commit and custom-node list installed in the worker image (needed for the registry's manifest fields; do not assume any outpainting node exists).
- [ ] Confirm whether the worker image already contains an inpainting-capable checkpoint or only the Schnell txt2img weights.
- [ ] Confirm current Modal cold-start and per-image GPU seconds from recent `generation_jobs` timings (baseline for cost metrics).
- [ ] Confirm the `generation_usage.period` format currently written by the API (e.g. `2026-08`) so the ledger extension matches.

---

## 3. Target architecture

```text
myaccount.brandverita.io ──(existing JWT handoff, unchanged)──► Studio (app.brandverita.io)
                                                                      │  (future phase)
Image Lab (Netlify, internal) ───────────┐                            │
                                         ▼                            ▼
                              BrandVerita Generation API (Modal FastAPI)
                              ├─ auth: Supabase JWT verify (httpx)
                              ├─ workflow registry (server-side, DB-backed)
                              ├─ job lifecycle + idempotency + usage ledger
                              ├─ asset service (private storage, signed URLs)
                              └─ dispatch ──► Modal workers ──► ComfyUI
                                                              │ approved,
                                                              │ server-built graphs
                                                              ▼
                                              private storage (generation-assets)
```

Rules that do not change: Studio calls the Generation API directly (never the Lab); the Lab never proxies for Studio; browsers never hold Modal/service-role secrets; workflow graphs are built server-side only.

---

## 4. Proposed data model (Phase 2) [pre-Studio]

New migration in the existing `comfy-ui` project (staging home; see §9 for the production-location decision):

**`workflow_definitions`** (registry, service-role write, authenticated read of safe columns only via a view `workflow_definitions_public` exposing: key, version, display_name, status, allowed_dimensions, input schema (safe subset), enabled_for_studio — never worker/model/manifest internals):
`id uuid pk`, `key text`, `version text`, `status text` (draft|testing|active|deprecated|disabled), `display_name text`, `description text`, `allowed_envs text[]`, `enabled_for_studio bool default false`, `input_schema jsonb`, `output_schema jsonb`, `allowed_dimensions jsonb`, `supported_file_types text[]`, `estimated_credits numeric`, `config_hash text`, `worker_version text`, `comfyui_ref text`, `model_manifest_ref text`, `feature_flag text`, `created_at`, `retired_at`, unique(key, version).

**`generation_assets`**: `id uuid pk`, `owner_id uuid`, `bucket text`, `storage_path text`, `content_type text`, `file_size bigint`, `source_asset_id uuid null fk`, `job_id uuid null fk`, `workflow_key text`, `workflow_version text`, `width int`, `height int`, `kind text` (input|output), `provenance jsonb`, `created_at`, `deleted_at`. RLS: owner SELECT only; writes service-role only. New private bucket `generation-assets` for customer-supplied inputs; keep `generation-outputs` for outputs (or migrate — decision in §16).

**`generation_jobs` extensions** (additive columns, no renames — preserves the Flux path): `workflow_version text`, `workflow_config_hash text`, `input_asset_ids uuid[]`, `output_asset_ids uuid[]`, `inputs jsonb` (validated request inputs minus secrets), `worker_version text`, `usage_ledger_id uuid null`, `error_category text`, `expires_at timestamptz`, `started_at timestamptz` (currently missing).

**`usage_ledger`** (reservation-ready, no charging): `id uuid pk`, `user_id`, `job_id fk`, `workflow_key/version`, `estimated_credits`, `actual_gpu_seconds`, `status` (reserved|settled|void), `created_at`, `settled_at`. Service-role only.

RLS pattern unchanged: users SELECT own rows; all mutations service-role via the API.

---

## 5. Proposed API contract (Phase 1 + Phase 4) [pre-Studio]

Backwards-compatible evolution of v5:

- `GET /v1/workflows` — safe registry metadata for the caller's environment (Lab gets testing+active; Studio gets `enabled_for_studio=true` and active only). No secrets, no node/model internals.
- `POST /v1/generations` — accepts both the legacy flat shape (prompt/width/height/seed → routed to `flux_text_to_image:v1`) **and** the structured shape:
  ```json
  { "workflow_id": "outpaint", "workflow_version": "v1",
    "inputs": { "source_asset_id": "uuid", "target_width": 1200, "target_height": 627,
                "anchor": "center", "expansion_mode": "horizontal", "style_mode": "preserve_source" },
    "idempotency_key": "uuid" }
  ```
  Server validates: JWT → workflow exists, status allows caller env, feature flag → input schema (pydantic per workflow) → asset ownership → dimension allowlist → idempotency replay (existing) → job insert + usage reservation → dispatch.
- `GET /v1/generations/{job_id}` and `GET /v1/generations/{job_id}/result` — unchanged, plus `workflow_version`, `worker_version` in the response.
- `POST /v1/assets` (Phase 3) — direct multipart upload of a source image to private storage; returns `{ asset_id }`. Size cap 10 MB, types png/jpeg/webp, magic-byte validated, re-encoded server-side.
- `GET /v1/assets/{id}` — metadata + fresh signed URL, ownership-checked.
- `POST /v1/generations/{job_id}/cancel` — best-effort cancel of a queued/running job **[later]**.
- Future Studio contract (Phase 4, documented, not built): `GET /v1/workflows?audience=studio`, structured `POST /v1/generations`, poll `GET /v1/generations/{id}`, `GET .../result`, then Studio saves the resulting `asset_id` into Content Hub via its own backend. Feature-flag check is server-side on every request, never trusted from the client.

---

## 6. Backend modularization plan (Phase 1) [pre-Studio]

Owner: Generation API (Modal). Single deploy, reversible.

- Split `api.py` into modules inside the same Modal app: `registry.py` (loads `workflow_definitions`, caches 60s, evaluates env + flag + status), `workflows/flux_txt2img.py` (today's `build_flux_workflow` moved verbatim — byte-identical graph output is the regression test), `workflows/outpaint.py` (Phase 3 stub returning 501), `jobs.py` (insert/update/respond), `assets.py` (upload/sign), `usage.py` (ledger reserve/settle), `supabase_rest.py` (existing httpx helpers).
- `GenerationRequest` becomes a discriminated union: flat legacy shape OR `{workflow_id, workflow_version, inputs}`; unknown workflow → 400 `unsupported_workflow`; disabled/flagged-off → 403 `workflow_unavailable`.
- `run_generation` dispatches to a per-workflow builder registered in a dict; the Flux branch is the existing code path unchanged.
- **Acceptance**: `/health` reports `version: "v6"` + loaded registry keys; an end-to-end Flux job from the Lab UI completes; `config_hash` recorded on the job.
- **Risk**: import/dispatch regression → **Rollback**: redeploy previous `api.py` (v5); DB columns are additive so no migration rollback needed.
- Seed registry rows via migration: `flux_text_to_image:v1` (active, envs = all, enabled_for_studio=false for now) and `outpaint:v1` (draft, envs = lab only, flag `outpaint_v1`).

---

## 7. outpaint:v1 technical & product specification (Phase 3) [pre-Studio, experimental]

**Product shape (Lab-only)**: source asset (uploaded in Lab or picked from prior job output), output preset, expansion direction (left|right|top|bottom|horizontal|vertical|all), anchor, preservation mode (preserve_image|preserve_product|preserve_background), optional style hint (neutral|clean_studio|natural|premium|minimal) mapped server-side to curated prompt fragments — no free-text customer prompt. Server-owned negative constraints appended always.

**Presets (validated list)**: Square 1080×1080 · LinkedIn 1200×627 · Hero 1600×900 · Story 1080×1920 · Portrait 1080×1350. Reject non-preset dimensions.

**Pipeline (server-built graph, decided in Lab)**:
1. Fetch source asset from private storage (ownership already checked at submit).
2. Place onto target canvas per anchor/expansion; build a mask covering only the expanded region (source pixels masked-in/protected).
3. Inpaint/outpaint the masked region with an outpainting-capable model — **node/model choice is an explicit Lab validation decision** (candidates: FLUX.1-Fill-dev, or SDXL-inpainting fallback; verify license for commercial marketing use before prod).
4. Upload output PNG, link `source_asset_id` → `output asset`, settle usage ledger.

**Failure handling**: malformed/oversized/unsupported file → 400 with safe code before dispatch; worker failure → `failed` + `error_category` (worker|storage|moderation|timeout); moderation → server-side check on inputs, refusal recorded without imagery retention.

**Quality gate before any Studio consideration**: a fixed test set of ≥20 representative marketing assets (product-on-white, lifestyle, text-adjacent) run through every preset; human review rubric (subject integrity, seam visibility, text-safe space usability); pass threshold agreed before status moves testing→active.

---

## 8. Generation Lab changes (Phase 3) [pre-Studio]

Owner: this repo (Image Lab frontend).

- Registry-driven UI: fetch `GET /v1/workflows`; Flux form unchanged; when `outpaint:v1` is visible, render an "Outpaint (experimental)" section: asset picker (upload or reuse recent output), preset dropdown, expansion/anchor/preservation controls. Feature-flagged by workflow visibility, not by frontend constants.
- `src/lib/generationApi.ts`: add `listWorkflows()`, `uploadAsset()`, structured `createGeneration` overload; keep legacy call intact.
- Recent jobs: show workflow key+version and thumbnails via fresh signed URLs.
- Acceptance: Lab user can upload a source image, run outpaint to LinkedIn preset, see result + lineage (source → output) in the dev panel; Flux regression passes in the same build.

---

## 9. Environment strategy [pre-prod]

| Concern | Local | Staging (current Lab) | Production |
|---|---|---|---|
| Modal app | `brandverita-api-dev` | `brandverita-api` (current) | `brandverita-api-prod` (new) |
| Supabase | local or comfy-ui | `comfy-ui` (current) | **decision**: dedicated Generation Platform project recommended before Studio prod — see §16 Q1 |
| Storage | generation-outputs | generation-outputs + generation-assets | separate buckets, prod project |
| Frontend | localhost:8080 | brandverita-image-lab.netlify.app | Studio deployment (not this repo) |
| Registry envs | draft+testing+active | draft+testing+active | active only |
| Secrets | Modal secrets per app | current set | separate Supabase service key + Modal tokens |
| Cost caps | none | soft alert | hard caps + alerts |

The existing Lab **remains staging permanently** and may call the staging API only. It must never point at the production API or production storage — enforced by `allowed_envs` in the registry and separate Supabase projects, not by convention. Cross-environment isolation test required.

---

## 10. Security plan [pre-Studio unless noted]

- Server-side Supabase JWT verification on every endpoint (existing pattern, keep).
- Ownership checks on jobs and assets before any read/sign; signed URLs short-lived, re-signed per request (existing).
- Private buckets only; no public assets by default.
- Origin allowlist per environment; CORS is browser hygiene, not authorization.
- Rate limits: per-user POST /v1/generations (e.g. 10/min) and asset upload (size + count) enforced in the API **[pre-prod]**.
- Hard limits: prompt 2000 chars, preset-only dimensions for outpaint, 10 MB uploads, png/jpeg/webp with magic-byte + re-encode validation.
- Idempotency: unique `(user_id, idempotency_key)`; replay returns the original job (existing behavior, formalized).
- Temporary worker files deleted in `finally` on every orchestrator path.
- Logging: no prompts, tokens, or image bytes in logs; audit metadata only (job id, workflow, timings, error category).
- Lab access: existing `allowed_emails` gate retained; Studio access: future per-workspace authorization **[pre-prod, decision Q3]**.
- Staging and production credentials fully separated.

---

## 11. Observability, reliability, cost [pre-Studio basics / pre-prod alerts]

- Job timing fields (`queued→started→completed`) enable queue/cold-start/execution/E2E metrics from `generation_jobs` alone; add a `/v1/stats/internal` endpoint for the Lab footer **[later]**.
- Stuck-job detection: pg_cron marks `queued > 15 min` or `running > 30 min` as `failed` with `error_category=stuck` **[pre-Studio]**; job `expires_at` for signed-result retention.
- Correlate via `modal_call_id` (already surfaced in the dev panel); confirm storage upload before `completed`.
- Error taxonomy: retryable (worker_timeout, storage_transient) vs terminal (invalid_input, moderation, unsupported_workflow).
- Usage ledger gives cost-per-generation; alert on error-rate spike, volume spike, and daily GPU-second budget **[pre-prod]**.

---

## 12. Testing & release checklist

1. Flux baseline regression: byte-stable graph builder + one E2E job per deploy. **[pre-Studio]**
2. outpaint:v1: ≥20-asset test set × 5 presets, human rubric pass. **[before status=active]**
3. API contract tests: legacy + structured shapes, unknown workflow, bad version. **[pre-Studio]**
4. AuthZ tests: other user's job/asset → 404; disabled workflow → 403. **[pre-Studio]**
5. Storage/signed-URL: expiry, refresh, cross-user denial. **[pre-Studio]**
6. Idempotency/double-click replay. **[pre-Studio]**
7. Worker failure + timeout → clean failed state, ledger voided. **[pre-Studio]**
8. Browser refresh mid-poll resumes (job id recoverable from recent jobs). **[later]**
9. Malformed/oversize/wrong-type uploads rejected pre-dispatch. **[pre-Studio]**
10. Cross-environment isolation: Lab cannot reach prod API/data. **[pre-prod]**
11. Rate-limit load test at expected internal volume. **[pre-prod]**
12. Secret scan: no tokens, raw graphs, or model internals in any client bundle or `/v1/workflows` payload. **[pre-Studio]**

---

## 13. Migration & rollback

Every phase is one Modal deploy + one additive DB migration. No column renames or drops; the legacy flat request shape keeps working until Studio ships, so rollback = redeploy previous API image. Registry rows are data, not code — disabling `outpaint:v1` is an `UPDATE status='disabled'`. Asset-table rollout is additive; if `generation_assets` misbehaves, outputs continue via `output_path` fallback until fixed.

---

## 14. Phased backlog (dependencies in order)

| # | Phase | Scope | Owner | Gate |
|---|---|---|---|---|
| 0 | Validation checklist (§2) | read-only inspection | ops | — |
| 1 | Registry + API modularization (v6) | Generation API + migration | API | Flux regression green |
| 2 | Assets + ledger + job extensions | Supabase migration + API | API/DB | 1 |
| 3 | outpaint:v1 builder + Lab UI + upload endpoint | API + worker + this repo | all | 2, node/model decision |
| 4 | Studio integration contract doc (no Studio code) | docs | API | 3 stable |
| 5 | Env split, alerts, rate limits, stuck-job cron | ops | API/DB | pre-prod |

---

## 15. Open questions needing your confirmation

1. **Production data home**: keep generation jobs/assets in `comfy-ui` for Studio launch, or create a dedicated Generation Platform Supabase project before production? (Recommendation: dedicated project pre-prod; comfy-ui stays staging.)
2. **Outpaint model**: FLUX.1-Fill-dev vs SDXL-inpainting fallback — must be validated in the Lab for quality and commercial license before any customer exposure. OK to evaluate both?
3. **Studio identity**: Studio users authenticate via the existing myaccount JWT handoff — should the Generation API trust that handoff token, or should Studio exchange it for a Supabase session on the generation project? Affects the whole authZ layer.
4. **Credit model**: usage ledger is reservation-ready; confirm no charging logic this phase and that `estimated_credits` per workflow is sufficient.
5. **Asset retention**: default retention/deletion policy for uploaded source assets and outputs (e.g. 90 days) — confirm before adding `expires_at` enforcement.
6. **Preset list**: confirm the five output presets (esp. Hero 1600×900) are the right marketing formats.

---

## Technical details (summary for implementers)

- All new tables get GRANTs + RLS in the same migration; authenticated SELECT-only, service_role ALL; registry exposed to clients through a safe-column view only.
- The API stays a single Modal FastAPI app; modularization is file-level, not new apps. Worker app unchanged except adding the outpaint builder input path.
- Frontend changes are additive: new `listWorkflows`/`uploadAsset` client functions and a feature-flagged outpaint section; existing Flux flow untouched.
- No Lovable Cloud, no new Netlify sites, no changes to myaccount↔Studio handoff, no Studio UI code in this phase.
