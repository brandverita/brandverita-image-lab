# Phase 2A — Generation Asset Foundation + Usage/Lineage Prep (staging only)

Scope guard: staging Supabase (`comfy-ui`) + V6 API/worker + Image Lab only. No V5 change, no Studio, no outpaint, no Replicate/BFL, no billing, no production identity or deployment.

## Confirmed current state (checked before writing this plan)

- Public tables today: `allowed_emails`, `generation_jobs`, `generation_usage`, `workflow_definitions`. `generation_assets` and `usage_ledger` do **not** exist yet.
- `generation_jobs` **already has** `input_asset_ids`, `output_asset_ids`, `usage_ledger_id` (added in the Phase 1 migration). So requirement 2 needs only FK constraints, not new columns.
- Storage buckets today: `generation-outputs` only. `generation-assets` does not exist.
- Frontend: `src/lib/generationApi.ts` is the single API module; `src/routes/index.tsx` composes the panels; auth session via `useSupabaseSession`, allow-list via `useAccessCheck`.
- The V6 backend lives outside this repo (your local `modal-project/phase1-v6-staging`). I will produce the exact file contents here for you to paste and deploy; I cannot deploy it.

## 1. Migration (additive, reversible-by-disuse)

One migration, `phase_2a_generation_assets`:

1. `create table public.generation_assets (...)` exactly per your column list, with:
   - `check (kind in ('input','output'))`, `check (status in ('pending_upload','ready','rejected','deleted','expired'))`
   - `unique (bucket, storage_path)` plus the plain unique on `storage_path`
   - `source_asset_id references public.generation_assets(id)`, `job_id references public.generation_jobs(id) on delete set null`
   - indexes: `(owner_id, status, created_at desc)`, `(sha256)`, `(job_id)`
2. `create table public.usage_ledger (...)` per your column list, `check (status in ('reserved','settled','void'))`, index `(user_id, created_at desc)`, `(job_id)`.
3. FKs only (no new columns) on `generation_jobs.usage_ledger_id → usage_ledger(id)`; leave the two uuid[] columns unconstrained (Postgres has no array FK) and document that the API validates membership.
4. Grants + RLS, in this order per table:
   - `grant select on public.generation_assets to authenticated;` `grant all ... to service_role;` — **no anon grant**
   - `grant select on public.usage_ledger to authenticated;` `grant all ... to service_role;`
   - enable RLS; policies: `select` to `authenticated using (owner_id = auth.uid())` (assets, and `user_id = auth.uid()` for ledger). No insert/update/delete policies at all → all writes are service-role only.
5. Storage: create private bucket `generation-assets` (10 MB limit) via the bucket tool, then `storage.objects` policies: **no** client insert/select; service-role only. Client never touches the bucket without a signed URL, so owner-path policies are deliberately omitted.

Reversibility: nothing existing is altered, so leaving the new tables/bucket unused restores Phase 1 behaviour exactly.

## 2. V6 API files (staging only)

New/changed files in `phase1-v6-staging`:

- `assets.py` (new) — all asset logic: path builder `<user_id>/<asset_id>/original.<ext>`, MIME/extension allow-list (`image/png|jpeg|webp` → `png|jpg|webp`), 10 MB cap, magic-byte sniffing, safe decode for width/height, SHA256, signed-URL creation via storage REST.
- `supabase_rest.py` (extend) — service-role helpers: `storage_create_signed_upload_url`, `storage_create_signed_url`, `storage_head_object`, `storage_download_object`, `storage_delete_object`; table insert/patch for `generation_assets`.
- `usage.py` (new) — `reserve_usage(...)`/`settle_usage(...)`/`void_usage(...)` helper interface only. **Not wired into the generation path in 2A**; `api.py` gets a single commented integration point next to job creation. Flux behaviour unchanged.
- `api.py` — mount three endpoints, all behind the existing JWKS-verified dependency:
  - `POST /v1/assets/upload-authorizations` → validate declared filename/MIME/size, insert `pending_upload` row, return `{asset_id, bucket, storage_path, upload_url, token, expires_in}`.
  - `POST /v1/assets/{asset_id}/finalize` → ownership check, object must exist, download bytes, magic-byte + real MIME check, decode dims, sha256, size; on pass → `ready` + `finalized_at`; on fail → `rejected` and delete/quarantine the object.
  - `GET /v1/assets/{asset_id}` → ownership check; safe metadata + fresh short-lived signed read URL only when `ready`.
  - Also `GET /v1/assets?limit=n` for the owner's recent `ready` assets (needed by the panel; reads via service role scoped to `owner_id = caller`).
- Image decode: Pillow added to the API image (`pillow`), decode with a pixel-bomb guard (`Image.MAX_IMAGE_PIXELS`) and `verify()` then re-open for size.
- Error codes returned as `{"error_code": ..., "message": ...}` with HTTP mapping: `invalid_file_type`/`file_too_large` → 400, `asset_not_found`/`asset_not_owned` → 404 (ownership failures are indistinguishable from not-found), `asset_not_ready` → 409, `asset_validation_failed` → 422, `storage_unavailable` → 503, missing/invalid JWT → 401.
- `/health` gains `assets: true` and `bucket: "generation-assets"` so the frontend can feature-detect.

## 3. Image Lab frontend (this repo)

- `src/lib/assetsApi.ts` (new) — typed client for the four endpoints + the direct-to-storage `PUT` using the returned signed upload token. Client-side pre-checks mirror the server (type + 10 MB) but the server remains authoritative. No logging of tokens, paths, or bytes.
- `src/hooks/use-asset-upload.ts` (new) — authorize → upload → finalize state machine (`idle | authorizing | uploading | finalizing | ready | rejected | error`) with structured error mapping.
- `src/components/generation/AssetTestPanel.tsx` (new) — internal "Asset Test" panel: file input (PNG/JPEG/WebP, <10 MB), progress/disabled states, result card showing status, dimensions, content type, size, SHA256 first 12 chars, and the signed thumbnail (`alt` describing the uploaded asset); plus a "Your recent staging assets" list with signed thumbnails. Light/neutral + blue-600 design system, dashed empty state, red error banner with Retry.
- `src/routes/index.tsx` — render the panel below the existing generation area, gated on session + allow-list + `API_CONFIGURED`. No other page changes.
- Explicitly not built: public-URL import, provider selector, outpaint UI, Studio changes.

## 4. Tests + verification checklist

Vitest unit tests (frontend, no network):
- `src/lib/__tests__/assetsApi.test.ts` — MIME allow-list rejects `image/gif`/`application/pdf` (`invalid_file_type`); 10 MB+1 rejected (`file_too_large`); error-code → user-message mapping; no token/path in thrown messages.
- `src/hooks/__tests__/use-asset-upload.test.ts` — happy path reaches `ready`; finalize returning `rejected` surfaces the rejected state; 401 surfaces "session expired"; upload failure is retryable.

Backend test script `tests/test_assets_phase2a.py` (curl-equivalent, run against V6 staging with two distinct staging users' JWTs):
1. no Authorization → `POST /v1/assets/upload-authorizations` = 401
2. `image/gif` declared → 400 `invalid_file_type`
3. declared size 11 MB → 400 `file_too_large`
4. valid authorization → row exists, `status = pending_upload`, path matches `<user_id>/<asset_id>/original.png`
5. real PNG, JPEG, WebP each: upload + finalize → `ready` with correct dims, size, content type, 64-char sha256
6. corrupt bytes with `.png` name → finalize = 422 `asset_validation_failed`, row `rejected`, object gone
7. user B finalize / GET user A's asset → 404 `asset_not_owned`-equivalent
8. owner GET ready asset → signed URL fetches 200 image; unauthenticated fetch of the raw object path → 400/403 (bucket private)
9. `select public from storage.buckets where id='generation-assets'` → `false`
10. one Flux V6 generation still completes with unchanged metadata; V5 `/health` still `version: v5`
11. re-run 4–5 with a second asset to confirm no cross-row path collision

Manual checklist appended to the phase doc, plus a `phase-2a-build-manifest.md` recording migration id, endpoint list, bucket config, and the deferred ledger integration point.

## 5. Order of work once approved

1. Migration + bucket (staging).
2. Backend files delivered here for you to paste + `modal deploy` to `brandverita-api-v6` (worker untouched).
3. Frontend panel + tests in this repo.
4. Run the checklist; report results before any Netlify redeploy of Image Lab.
