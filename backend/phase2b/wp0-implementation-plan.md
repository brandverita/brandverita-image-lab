# Phase 2B — WP0 implementation plan (shared Image Transformation Framework v1)

Approved scope: **WP0 only**. Additive migration, source-asset gate, output/lineage
foundation, evaluation-run records, flags and feature gating, negative test suite.
**No active candidate dispatch.** No Modal research worker, no BFL adapter, no provider
secret, no Image Lab advanced panel, no candidate workflow row is created or deployed in
WP0. Staging only (`comfy-ui` / `thspgkedjkiltrcimond`, `brandverita-api-v6`). V5, the
V6 Flux worker, the Flux text-to-image path, Studio and production are untouched.

Decisions incorporated: BFL is the first (and only, first sprint) hosted Product Scene
candidate pending a written commercial/data review, Replicate is the documented fallback;
Module A uses a single `anchor_directional` abstraction with a strict enum; registry rows
use `status='testing'` with `commercial_status='research_only'`; hosted-provider input
mechanism is not assumed to be a Supabase signed URL; a `ready` output row is only
created after bytes are validated, uploaded and hashed.

---

## 1. Exact migration (additive, staging)

One migration file, additive only, no data migration, no change to Flux columns or the
Flux output path.

### 1.1 Registry columns

```sql
alter table public.workflow_definitions
  add column if not exists requires_source_asset boolean not null default false,
  add column if not exists allowed_output_presets jsonb not null default '[]'::jsonb,
  add column if not exists input_envelope jsonb not null default '{}'::jsonb,
  add column if not exists artifact_pins jsonb not null default '[]'::jsonb,
  add column if not exists candidate_id text,
  add column if not exists candidate_notes text;

create unique index if not exists workflow_definitions_candidate_id_key
  on public.workflow_definitions (candidate_id) where candidate_id is not null;
```

Immutability trigger `public.enforce_workflow_definitions_immutability()` is replaced
(same name, same trigger) so that once `status in ('active','deprecated','disabled')` the
existing immutable set **plus** `requires_source_asset`, `allowed_output_presets`,
`input_envelope`, `artifact_pins`, `candidate_id` cannot change. A config change means a
new version/candidate row.

`status` stays in the existing enum (`draft|testing|active|deprecated|disabled`);
`research_only` is only ever a `commercial_status` value.

### 1.2 Job link columns

```sql
alter table public.generation_jobs
  add column if not exists source_asset_id uuid references public.generation_assets(id),
  add column if not exists output_asset_id uuid references public.generation_assets(id),
  add column if not exists output_preset text,
  add column if not exists request_params jsonb not null default '{}'::jsonb;

create index if not exists generation_jobs_source_asset_idx
  on public.generation_jobs (source_asset_id);
create index if not exists generation_jobs_output_asset_idx
  on public.generation_jobs (output_asset_id);
```

`request_params` stores only the validated structured enums (preset, direction, anchor,
scene_direction, background_style, seed) — never a prompt, graph, URL or credential.

### 1.3 Evaluation runs (staging only)

```sql
create table public.transformation_eval_runs (
  id uuid primary key default gen_random_uuid(),
  module text not null,                          -- 'outpaint' | 'product_scene'
  job_id uuid references public.generation_jobs(id) on delete set null,
  candidate_id text,
  workflow_key text not null,
  workflow_version text not null,
  config_hash text,
  provider text not null,
  provider_model text,
  provider_call_id text,
  worker_version text,
  operator_user_id uuid not null,
  source_asset_id uuid references public.generation_assets(id) on delete set null,
  output_asset_id uuid references public.generation_assets(id) on delete set null,
  output_preset text,
  request_params jsonb not null default '{}'::jsonb,
  queued_at timestamptz,
  dispatched_at timestamptz,
  first_byte_at timestamptz,
  completed_at timestamptz,
  provider_latency_ms integer,
  total_latency_ms integer,
  cold_start boolean,
  gpu_seconds numeric,
  estimated_cost numeric,
  actual_provider_cost numeric,
  cost_currency text default 'USD',
  status text not null default 'pending',
  error_code text,
  error_message text,                            -- safe, redacted message only
  output_width integer,
  output_height integer,
  output_bytes bigint,
  output_sha256 text,
  source_region_verified boolean,
  reviewer_scores jsonb not null default '[]'::jsonb,
  rubric_mean numeric,
  blinded boolean not null default true,
  license_ref text,
  commercial_status text,
  data_retention_finding text,
  training_on_input boolean,
  legal_status text not null default 'pending',
  legal_reviewed_by text,
  legal_reviewed_at timestamptz,
  notes text,
  created_at timestamptz not null default now(),
  constraint transformation_eval_runs_module_chk check (module in ('outpaint','product_scene')),
  constraint transformation_eval_runs_status_chk
    check (status in ('pending','dispatched','running','completed','failed','canceled')),
  constraint transformation_eval_runs_legal_chk
    check (legal_status in ('pending','cleared_staging','blocked','needs_counsel'))
);

create index on public.transformation_eval_runs (module, created_at desc);
create index on public.transformation_eval_runs (candidate_id, created_at desc);
create index on public.transformation_eval_runs (job_id);

grant select on public.transformation_eval_runs to authenticated;
grant all on public.transformation_eval_runs to service_role;

alter table public.transformation_eval_runs enable row level security;

create policy "internal allow-list reads own eval runs"
  on public.transformation_eval_runs for select to authenticated
  using (operator_user_id = auth.uid() and public.is_email_allowed());
```

No insert/update/delete policies — every write is server-side service-role, exactly as
`generation_assets`. No anon grant. Name note: the Phase 2B plan called this
`outpaint_eval_runs`; it is renamed `transformation_eval_runs` because it now records both
modules. No migration of any existing table is required (the old name was never created).

### 1.4 Output-asset support

No schema change: `generation_assets` already carries `kind='output'`,
`source_asset_id`, `job_id`, `workflow_key`, `workflow_version`, `provenance`, and the
`generation_assets_ready_chk` constraint already forbids a `ready` row without
`sha256`, `content_type`, `file_size`, `width`, `height`, `finalized_at` — which enforces
decision 5 at the database level.

---

## 2. API changes (V6 staging)

New module `advanced.py` in `modal-project/phase1-v6-staging/`, added to the API image
with `add_local_file` (same rule as `assets.py`/`usage.py`). No worker change in WP0.

### 2.1 `POST /v1/generations` extension

Applies **only** when the resolved registry row has `requires_source_asset = true`.
Accepted body additions:

```
source_asset_id : uuid (required)
output_preset   : string, must be in the row's allowed_output_presets
params          : object, validated against the row's input_schema, enums only
```

Module A (`outpaint:v1`) params, enforced server-side even though no candidate exists yet:

```
expansion_mode : "anchor_directional"        (only value in V1)
direction      : left | right | top | bottom | symmetric
anchor         : left | right | top | bottom | center
style_mode     : "preserve_source"           (only value in V1)
```

Valid direction/anchor pairs (everything else → `invalid_request` 400):
`left→right|center`, `right→left|center`, `top→bottom|center`, `bottom→top|center`,
`symmetric→center`. No pixel offsets, ratios, masks, free text, or arbitrary dimensions.

Module B (`product_scene:v1`) params:

```
scene_direction  : clean_studio | premium_neutral | warm_lifestyle | natural_surface
background_style : (curated enum, fixed in the candidate's input_schema)
preserve_subject : true (only value in V1)
```

Any unknown key, any string field not in an enum, and any prompt-shaped field
(`prompt`, `negative_prompt`, `workflow`, `graph`, `nodes`, `image_url`) is rejected with
`invalid_request` — a strict allow-list parser, not a permissive one.

### 2.2 Gate order (before any dispatch, and again at dispatch time)

1. Bearer token JWKS-verified; caller on the internal allow-list.
2. `ADVANCED_WORKFLOWS_ENABLED` true **and** the module flag true, else
   `workflow_not_available` 403.
3. Registry row resolves; `requires_source_asset=true`; `commercial_status='research_only'`;
   `'staging' = any(allowed_envs)`; environment is staging; `registry_visibility='internal'`.
   Production environment rejects `research_only` unconditionally.
4. Asset row: exists, `owner_id = auth uid`, `kind='input'`, `status='ready'`,
   `deleted_at is null`, `expires_at > now()`, bucket is `generation-assets`.
5. Asset dimensions/pixels within `input_envelope`; `output_preset` in
   `allowed_output_presets` and orientation-compatible.
6. Params validated per 2.1.

Failure codes: `asset_not_found` / `asset_not_owned` 404, `asset_not_ready` 409,
`asset_expired` 409, `invalid_request` 400, `workflow_not_available` 403,
`rate_limited` 429, `storage_unavailable` 503.

Because no candidate row exists in WP0, step 3 always fails in production-shaped ways —
the negative test suite asserts exactly that.

### 2.3 `GET /v1/generations/{job_id}` extension

Adds `source_asset_id`, `output_asset_id`, `output_preset`, and the validated
`request_params` echo. A signed output read URL is issued only for the owner, only when
the output asset is `ready`, 5-minute TTL, via the existing `assets.py` helper. Never
returned: provider keys, provider input authorization, graph JSON, model paths, internal
prompts, source signed URLs, raw provider errors.

### 2.4 Registry read filtering

Studio-shaped registry reads filter `registry_visibility <> 'studio_safe'`,
`commercial_status='research_only'`, `production_enabled=false` and
`enabled_for_studio=false` rows out at the API layer, not in the client.

---

## 3. Flag semantics (server-side, default false)

| Flag | Effect when false |
| --- | --- |
| `ADVANCED_WORKFLOWS_ENABLED` | master kill switch: every `requires_source_asset` request → 403; no adapter is even constructed |
| `OUTPAINT_EVAL_ENABLED` | Module A workflow keys rejected |
| `PRODUCT_SCENE_EVAL_ENABLED` | Module B workflow keys rejected |
| `PROVIDER_BFL_ENABLED` | BFL adapter unreachable (WP2; flag defined in WP0, no adapter behind it) |
| `PROVIDER_REPLICATE_ENABLED` | fallback provider unreachable |

Flags are read inside the request handler (never at module scope). Flag state is never
echoed to the browser except as an opaque boolean capability. Client flag
`VITE_ADVANCED_LAB_ENABLED` is defined but unused in WP0 — no UI ships.

## 4. Output asset and lineage lifecycle

Order is mandatory and enforced:

1. Job created `queued` with `source_asset_id`, `output_preset`, `request_params`.
2. Input acquired through a short-lived server-side authorization; bytes are downloaded
   server-side, SHA256 verified against the asset row before use; a mismatch fails the job
   with `source_integrity_failed`. The browser never receives the provider/worker input
   authorization, and the authorization is never persisted on the job row or logged.
   Hosted-provider input mechanism is not assumed: the adapter interface accepts
   *bytes* and each provider adapter (WP2) documents whether it uses a provider temporary
   upload or inline bytes/base64. Defaults to server-downloaded bytes.
3. Output bytes validated (declared type vs magic bytes vs decoded format, single frame,
   dimensions equal the requested preset, size/pixel limits) → uploaded to
   `generation-assets` at `<owner_id>/<output_asset_id>/original.<ext>` → SHA256,
   dimensions, bytes recorded.
4. **Only then** the output row is written/updated to `kind='output'`, `status='ready'`,
   `finalized_at=now()`, `source_asset_id`, `job_id`, `workflow_key`, `workflow_version`,
   `provenance` (candidate_id, config_hash, provider, provider_model, preset, params),
   staging TTL. Job set `completed` with `output_asset_id`.
5. Any failure in 2–4 → job `failed` with a safe error code; best-effort cleanup: delete
   the uploaded object if present, mark any placeholder output row `rejected`, never leave
   a `ready` row without verified bytes. All temp paths keyed by `job_id` and removed in a
   `finally` block.
6. Lineage is cross-checkable both ways: `job.source_asset_id ≡ output_asset.source_asset_id`
   and `job.output_asset_id → output_asset.id`, `output_asset.job_id → job.id`.
7. `usage_ledger` stays unwired; cost data lives in `transformation_eval_runs`.

Eval run rows are written by the framework at dispatch and completion for any advanced
job (server-side only), so timing/cost/error data exists from the first WP1/WP2 run.

## 5. Negative and regression test suite (WP0 acceptance)

Backend `backend/phase2b/tests/test_wp0_framework.py`, run against V6 staging with two
allow-listed users (A, B):

Contract: 1 unauthenticated → 401. 2 non-allow-listed → 403. 3 advanced request with
master flag off → 403 `workflow_not_available`. 4 unknown workflow key → 403.
5 `requires_source_asset` request with no `source_asset_id` → 400. 6 flux workflow with a
`source_asset_id` → 400 (ignored/rejected, never dispatched with an asset).
7 non-existent asset → 404. 8 user B's asset from user A → 404 `asset_not_owned`.
9 pending asset → 409 `asset_not_ready`. 10 expired asset → 409 `asset_expired`.
11 output-kind asset as source → 400. 12 preset not in `allowed_output_presets` → 400.
13 each invalid direction/anchor pair (left+left, right+right, top+top, bottom+bottom,
symmetric+left…) → 400. 14 `prompt`/`workflow`/`nodes`/`image_url` present → 400.
15 unknown params key → 400. 16 non-enum `scene_direction` → 400.

Safety: 17 no candidate row is dispatchable with flags off (registry query proves zero
`research_only` rows are reachable). 18 Studio-shaped registry read returns no internal
rows. 19 production-mode dispatch of `research_only` rejected. 20 no signed URL, prompt,
token, or provider key in any response body or log line. 21 `generation-assets` bucket
still private. 22 client bundle contains no provider key (`bun run build` + grep).

Lineage/DB: 23 attempted `ready` output row without sha256/dimensions is rejected by the
constraint. 24 `transformation_eval_runs` insert from an authenticated client is denied;
select is scoped to the caller. 25 `usage_ledger` still empty.

Regression: 26 Flux text-to-image end-to-end unchanged (same fields, same output path).
27 V5 `/health` healthy. 28 Frontend `bun run test` (existing 20 tests) green.

## 6. Rollback and deployment isolation

- Migration is additive only: dropping the new columns/table restores the Phase 2A state;
  no existing column, constraint, policy or row is modified except the registry
  immutability function, which is `create or replace` and reversible to its Phase 1 body.
- `ADVANCED_WORKFLOWS_ENABLED=false` makes the entire framework inert without a redeploy.
- WP0 deploys the V6 API only (`brandverita-api-v6`). The V6 worker app
  `comfyui-generation-worker-v6` is not rebuilt or redeployed. V5 remains the API
  rollback target.
- No Netlify deploy in WP0 — the frontend is unchanged, so no user-visible surface moves.
- No secret is created in WP0. `PROVIDER_BFL_ENABLED` exists as a flag with nothing
  behind it; the BFL key is designed and stored only in WP2, server-side in the Modal
  secret store, read inside the handler, never `VITE_*`, never in Netlify env.

## 7. Touch points

| Path | Change |
| --- | --- |
| `supabase/migrations/<new>.sql` | registry columns + immutability replace, job link columns, `transformation_eval_runs`, grants/RLS |
| `modal-project/phase1-v6-staging/advanced.py` | **new**: strict param parser, asset+registry gate, adapter interface, output writer, eval-run writer |
| `modal-project/phase1-v6-staging/registry.py` | expose the new registry fields; Studio-safe filter |
| `modal-project/phase1-v6-staging/jobs.py` | persist `source_asset_id`, `output_asset_id`, `output_preset`, `request_params` |
| `modal-project/phase1-v6-staging/assets.py` | reuse: output upload + signed read; add output-validation helper |
| `modal-project/phase1-v6-staging/api.py` | include `advanced` router; add `advanced.py` to the image; `/health` marker `advanced_framework: true` |
| `src/integrations/supabase/types.ts` | regenerated types for the new columns/table (read-only use) |
| `backend/phase2b/tests/test_wp0_framework.py` | **new**: the 28 checks above |
| `backend/phase2b/wp0-build-manifest.md` | **new** on completion: applied migration id, deployed API build, test results |

Unchanged: Flux graph and adapter, V6 worker, V5, `usage_ledger` wiring, all frontend
components and routes, Studio, production.

## 8. Exit criteria for WP0 → WP1/WP2 approval

All 28 checks pass; migration applied to staging and recorded; V6 redeployed with
`advanced_framework: true` and Flux verified unchanged; zero candidate rows exist; no
secret added; manifest written. WP1 (Modal research worker + outpaint graph) and WP2
(BFL commercial/data review → adapter + secret) then start in parallel, each requiring
your separate approval.
