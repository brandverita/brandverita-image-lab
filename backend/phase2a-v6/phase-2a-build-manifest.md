# Phase 2A build manifest — Generation Asset Foundation (staging)

Date: 2026-08-29. Environment: staging only (`comfy-ui` / `thspgkedjkiltrcimond`,
`brandverita-api-v6`, Image Lab). V5, the V6 worker, Studio and production are untouched.

## Database

Migration applied (additive):

- `public.generation_assets` — owner/workspace, bucket + `storage_path`, `sha256`,
  `content_type`, `file_size`, `width`, `height`, `kind`, `status`, `source_asset_id`,
  `job_id`, `workflow_key`, `workflow_version`, `provenance`, `idempotency_key`,
  `created_at`, `finalized_at`, `deleted_at`, `expires_at`.
  - `unique (bucket, storage_path)` (no global unique on `storage_path`)
  - partial unique `(owner_id, idempotency_key)` for retry-safe authorization
  - CHECKs: kind, status, ready-completeness, ≤4096 px per side, ≤16,777,216 px, ≤10 MB
  - trigger `generation_assets_expiry_validate` — expiry/finalize consistency, ready ⇒ expiry
- `public.usage_ledger` — user/workspace/job, workflow key + version, provider,
  estimated credits, estimated/actual provider cost, gpu seconds, status, `settled_at`.
- FK `generation_jobs.usage_ledger_id → usage_ledger(id)`. No new job columns (the
  three link columns already existed from Phase 1).

Grants/RLS: `select` to `authenticated` only, scoped to `auth.uid()` + `is_email_allowed`;
`all` to `service_role`; **no anon grants**; **no insert/update/delete policies** — every
write is server-side service-role.

Pre-existing linter findings unchanged by this migration: two deny-all tables with RLS and
no policies (`allowed_emails`, `workflow_definitions` — intentional), the security-definer
allow-list function (intentional), and leaked-password protection (N/A, magic-link only).

## Storage

- Bucket `generation-assets`: **private**, 10 MB file size limit.
- No `storage.objects` policies for `anon`/`authenticated`. Browser writes only via a
  30-minute signed upload URL bound to one exact object path; browser reads only via a
  5-minute signed read URL issued after an API ownership check.
- Object path: `<user_id>/<asset_id>/original.<validated ext>`.

## API (V6 staging) — files delivered in `backend/phase2a-v6/`

| File | Role |
| --- | --- |
| `assets.py` | asset endpoints, validation pipeline, storage/table access, idempotency |
| `usage.py` | ledger helper interface — **not called anywhere** |
| `README-integration.md` | exact `api.py` / image edits + deploy steps |
| `tests/test_assets_phase2a.py` | 16 automated acceptance checks + 2 manual |

Endpoints (all JWKS-verified, ownership re-checked):

- `POST /v1/assets/upload-authorizations` — idempotent; returns `asset_id` and one
  short-lived `upload_url`. No raw token field, no keys, no bucket policy. Credentials are
  never persisted or logged.
- `POST /v1/assets/{asset_id}/finalize` — idempotent by status: pending validates,
  ready returns existing metadata, rejected → 409, deleted/expired/not-owned → 404.
- `GET /v1/assets/{asset_id}` — safe metadata + fresh signed read URL when ready.
- `GET /v1/assets?limit=n` — the caller's recent ready input assets.

Error codes: `invalid_file_type` 400, `file_too_large` 400, `asset_not_found` /
`asset_not_owned` 404, `asset_not_ready` 409, `asset_validation_failed` 422,
`storage_unavailable` 503, missing/invalid JWT 401.

Server-authoritative limits: PNG/JPEG/WebP only; 10 MB; 4096×4096; 16,777,216 px;
single-frame only (animated WebP/APNG rejected); Pillow decompression-bomb warnings
escalated to validation errors; magic bytes + decoded format + declared MIME must agree;
SHA256 recorded. TTLs: pending 30 min, ready 30 days. No cleanup scheduler this phase.

## Frontend (Image Lab)

`src/lib/assetsApi.ts`, `src/hooks/use-asset-upload.ts`,
`src/components/generation/AssetTestPanel.tsx`, mounted at the bottom of `src/routes/index.tsx`.
No public-URL import, no provider selection, no outpaint UI, no Studio change, no output assets.

## Scope held

`generation_assets` is input-only. Flux V6 generation is byte-for-byte unchanged and writes
no ledger rows. Deferred integration point documented in `usage.py` and
`README-integration.md` (needs atomic job-insert + reservation, plus void on dispatch
failure, before it can be enabled).

## Verification status

- Frontend: 20 automated tests pass (`bun run test`).
- Backend: `tests/test_assets_phase2a.py` is ready to run against V6 once `assets.py` is
  deployed; steps 17 (bucket not public) and 18 (Flux unaffected + V5 healthy) are manual.
