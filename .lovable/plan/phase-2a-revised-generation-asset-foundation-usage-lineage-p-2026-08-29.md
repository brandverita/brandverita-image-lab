# Phase 2A (revised) — Generation Asset Foundation + Usage/Lineage Prep

Staging only: `comfy-ui` Supabase, V6 API (`brandverita-api-v6`), Image Lab. No V5, Studio, worker, production, outpaint, provider dispatch, billing or credit changes. Nothing is applied until you approve this package.

All eight of your adjustments are folded in below.

## Confirmed current state

- Public tables: `allowed_emails`, `generation_jobs`, `generation_usage`, `workflow_definitions`. `generation_assets` and `usage_ledger` do not exist.
- `generation_jobs` already has `input_asset_ids uuid[]`, `output_asset_ids uuid[]`, `usage_ledger_id uuid` (Phase 1). No new job columns needed — only an FK for `usage_ledger_id`.
- Buckets: `generation-outputs` (private) only. `generation-assets` does not exist.
- Existing job/usage RLS is SELECT-only for `authenticated`, gated on `is_email_allowed(auth.uid())`; new tables follow the same shape.

## 1. Migration (additive; exact SQL to be applied)

```sql
-- generation_assets ---------------------------------------------------------
create table public.generation_assets (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null,
  workspace_id uuid,
  sha256 text,
  bucket text not null,
  storage_path text not null,
  content_type text,
  file_size bigint,
  width integer,
  height integer,
  kind text not null default 'input',
  status text not null default 'pending_upload',
  source_asset_id uuid references public.generation_assets(id) on delete set null,
  job_id uuid references public.generation_jobs(id) on delete set null,
  workflow_key text,
  workflow_version text,
  provenance jsonb not null default '{}'::jsonb,
  idempotency_key text,
  created_at timestamptz not null default now(),
  finalized_at timestamptz,
  deleted_at timestamptz,
  expires_at timestamptz,
  constraint generation_assets_bucket_path_key unique (bucket, storage_path),
  constraint generation_assets_kind_chk   check (kind in ('input','output')),
  constraint generation_assets_status_chk check (status in
    ('pending_upload','ready','rejected','deleted','expired')),
  constraint generation_assets_ready_chk check (
    status <> 'ready' or (sha256 is not null and content_type is not null
      and file_size is not null and width is not null and height is not null
      and finalized_at is not null)),
  constraint generation_assets_dims_chk check (
    (width  is null or (width  between 1 and 4096)) and
    (height is null or (height between 1 and 4096)) and
    (width is null or height is null or width::bigint * height::bigint <= 16777216)),
  constraint generation_assets_size_chk check (file_size is null or file_size <= 10485760)
);

create unique index generation_assets_idem_key
  on public.generation_assets (owner_id, idempotency_key)
  where idempotency_key is not null;
create index generation_assets_owner_recent
  on public.generation_assets (owner_id, status, created_at desc);
create index generation_assets_sha256_idx on public.generation_assets (sha256);
create index generation_assets_job_idx    on public.generation_assets (job_id);
```

Expiry consistency is enforced by a **trigger** (not a CHECK, because it compares against `now()`):

```sql
create or replace function public.validate_generation_asset_expiry()
returns trigger language plpgsql set search_path = public as $$
begin
  if new.expires_at is not null and new.expires_at <= new.created_at then
    raise exception 'generation_assets: expires_at must be after created_at';
  end if;
  if new.finalized_at is not null and new.finalized_at < new.created_at then
    raise exception 'generation_assets: finalized_at cannot precede created_at';
  end if;
  if new.status = 'ready' and new.expires_at is null then
    raise exception 'generation_assets: ready assets require expires_at';
  end if;
  return new;
end $$;
create trigger generation_assets_expiry_validate
  before insert or update on public.generation_assets
  for each row execute function public.validate_generation_asset_expiry();
```

Expiry policy set by the API: `pending_upload` → `now() + 30 minutes`; on finalize to `ready` → `now() + 30 days`. No cleanup scheduler in this phase (documented as Phase 2B).

```sql
-- usage_ledger --------------------------------------------------------------
create table public.usage_ledger (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  workspace_id uuid,
  job_id uuid references public.generation_jobs(id) on delete set null,
  workflow_key text not null,
  workflow_version text not null,
  provider text not null,
  estimated_credits numeric,
  estimated_provider_cost numeric,
  actual_provider_cost numeric,
  gpu_seconds numeric,
  status text not null default 'reserved',
  created_at timestamptz not null default now(),
  settled_at timestamptz,
  constraint usage_ledger_status_chk check (status in ('reserved','settled','void'))
);
create index usage_ledger_user_recent on public.usage_ledger (user_id, created_at desc);
create index usage_ledger_job_idx     on public.usage_ledger (job_id);

alter table public.generation_jobs
  add constraint generation_jobs_usage_ledger_fk
  foreign key (usage_ledger_id) references public.usage_ledger(id) on delete set null;

-- grants + RLS --------------------------------------------------------------
grant select on public.generation_assets to authenticated;
grant all    on public.generation_assets to service_role;
grant select on public.usage_ledger      to authenticated;
grant all    on public.usage_ledger      to service_role;
-- deliberately NO grants to anon

alter table public.generation_assets enable row level security;
alter table public.usage_ledger      enable row level security;

create policy "Approved users read own assets" on public.generation_assets
  for select to authenticated
  using (owner_id = auth.uid() and is_email_allowed(auth.uid()) and deleted_at is null);

create policy "Approved users read own usage ledger" on public.usage_ledger
  for select to authenticated
  using (user_id = auth.uid() and is_email_allowed(auth.uid()));
```

No insert/update/delete policies on either table → every write is service-role, server-side.

### Storage

- Create bucket `generation-assets` via the bucket tool: **private**, file size limit `10MB`.
- **No `storage.objects` policies for `authenticated` or `anon`** — no client SELECT/INSERT/UPDATE/DELETE. Service role bypasses RLS server-side. The only browser write path is a short-lived signed upload authorization scoped to one exact object path; the only browser read path is a signed read URL issued after an API ownership check.

Reversibility: purely additive. Leaving the tables/bucket unused restores exact Phase 1 behaviour; no existing column, policy, or row is touched.

## 2. API contract (V6 staging)

All endpoints require a JWKS-verified staging JWT. Errors: `{"error_code": "...", "message": "..."}`.

### `POST /v1/assets/upload-authorizations`

Request: `{ "file_name": "photo.png", "content_type": "image/png", "file_size": 812345, "idempotency_key": "<uuid v4>" }`

- Allow-list `image/png | image/jpeg | image/webp`; extension must match the declared MIME (`png`, `jpg`/`jpeg`, `webp`) → mismatch = `invalid_file_type`.
- `file_size > 10485760` → `file_too_large`.
- **Idempotent**: if a row exists for `(owner_id, idempotency_key)` that is still `pending_upload` and not expired, re-issue a fresh signed authorization for the *same* asset id and path — no new row. If that row is `ready` → return it as already-finalized. If `rejected`/`expired` → `409 asset_validation_failed` / `410`-equivalent `asset_not_ready` with a new key required.
- Else insert `pending_upload` with `kind='input'`, `bucket='generation-assets'`, `storage_path='<user_id>/<asset_id>/original.<ext>'`, `expires_at = now()+30min`, `provenance = {"source":"image_lab_asset_test","declared_content_type":...,"declared_file_size":...}`.

Response (minimal credential — one value, nothing else):

```json
{ "asset_id":"...", "upload_url":"https://<ref>.supabase.co/storage/v1/object/upload/sign/generation-assets/<path>?token=...",
  "method":"PUT", "content_type":"image/png", "expires_in":1800, "max_file_size":10485760 }
```

Supabase's signed-upload token is embedded in `upload_url`; we do **not** additionally return a raw `token` field, and we never persist or log the URL/token (only `asset_id` and path are stored). The browser does a single `PUT` with the file body.

### `POST /v1/assets/{asset_id}/finalize`

Ownership first (`owner_id = caller` else `404 asset_not_found`). Idempotent by status:

| current status | behaviour |
|---|---|
| `pending_upload` | run validation → `ready` or `rejected` |
| `ready` | 200, return existing metadata unchanged (no re-download) |
| `rejected` | `409 asset_validation_failed` with the recorded reason |
| `deleted` / `expired` | `404 asset_not_found` |
| not owned / missing | `404 asset_not_found` |

Validation pipeline (server-side, browser metadata never trusted):
1. Object must exist at the controlled path → else `422 asset_validation_failed`; storage error → `503 storage_unavailable`.
2. Download bytes; real size ≤ 10 MB.
3. Magic-byte sniff: PNG `89 50 4E 47`, JPEG `FF D8 FF`, WebP `RIFF....WEBP`. Anything else (SVG, GIF, TIFF, HEIC, PDF, AVIF, BMP, ICO, zip) → reject.
4. Pillow: `warnings.simplefilter("error", Image.DecompressionBombWarning)` and `Image.MAX_IMAGE_PIXELS = 16_777_216`, so bombs raise instead of warn; `verify()` then reopen.
5. Decoded `img.format` must be in `{PNG, JPEG, WEBP}` **and** match the declared MIME.
6. Reject animated/multi-frame: `getattr(img, "n_frames", 1) > 1` or `img.info.get("is_animated")` (covers animated WebP/APNG).
7. `1 ≤ width ≤ 4096`, `1 ≤ height ≤ 4096`, `width*height ≤ 16777216`.
8. SHA256 of the exact bytes.
9. Pass → patch `status='ready'`, dims, real `content_type`, `file_size`, `sha256`, `finalized_at=now()`, `expires_at=now()+30 days`.
10. Fail → patch `status='rejected'`, `provenance.rejection_reason=<code>`, then delete the object (quarantine = delete in staging).

Response on success: `{asset_id, status, width, height, content_type, file_size, sha256, finalized_at, expires_at}`.

### `GET /v1/assets/{asset_id}`

Ownership required. `ready` → safe metadata + fresh signed read URL (`expires_in: 300`). Non-`ready` → `409 asset_not_ready`; unknown/other-owner/deleted/expired → `404 asset_not_found`. Never returns bucket internals beyond the bucket name, credentials, or provider metadata.

### `GET /v1/assets?kind=input&status=ready&limit=12`

Caller's own recent ready assets with signed thumbnails (service-role read filtered to `owner_id = caller`).

Error-code → HTTP: `invalid_file_type` 400, `file_too_large` 400, `asset_not_found` 404, `asset_not_owned` 404 (indistinguishable from not-found on purpose), `asset_not_ready` 409, `asset_validation_failed` 422, `storage_unavailable` 503, missing/bad JWT 401.

## 3. API file changes (`modal-project/phase1-v6-staging`)

- `assets.py` **new** — path builder, MIME/extension allow-list, the full validation pipeline above, signed upload/read helpers, idempotency resolution, structured error type.
- `supabase_rest.py` **extend** — `storage_create_signed_upload_url`, `storage_create_signed_url`, `storage_object_exists`, `storage_download`, `storage_delete`, plus `table_insert`/`table_patch`/`table_select` for `generation_assets`.
- `usage.py` **new** — `reserve_usage()`, `settle_usage()`, `void_usage()` interface only. **Not called anywhere in the generation path.** A comment in `api.py` marks the future integration point next to job creation; Flux behaviour byte-for-byte unchanged.
- `api.py` — register the four asset routes behind the existing auth dependency; add `pillow` to `api_image`; `/health` gains `"assets": true`.
- No worker change. `modal deploy api.py` for `brandverita-api-v6` only.

## 4. Frontend file changes (this repo)

- `src/lib/assetsApi.ts` **new** — typed client: `createUploadAuthorization`, `uploadToAuthorization` (single `PUT`, credential held in a local variable only, never stored or logged), `finalizeAsset`, `getAsset`, `listAssets`; client pre-checks mirror server limits (type, 10 MB) with the server authoritative; error-code → human message map.
- `src/hooks/use-asset-upload.ts` **new** — `idle → authorizing → uploading → finalizing → ready | rejected | error`, one idempotency key per selected file (reused on retry), retry re-authorizes if the signed URL expired.
- `src/components/generation/AssetTestPanel.tsx` **new** — internal Asset Test panel: file picker (PNG/JPEG/WebP <10 MB), disabled-while-busy, status, dimensions, content type, size, SHA256 first 12 chars, private signed thumbnail with descriptive alt text, red error banner + Retry, dashed empty state, and a "Your recent staging assets" grid.
- `src/routes/index.tsx` — mount the panel below the generation area, gated on session + allow-list + `API_CONFIGURED`.
- Not built: public-URL import, provider selector, outpaint UI, output-asset rows, Studio changes.

## 5. Test plan

Frontend (vitest, no network): `assetsApi` rejects `image/gif`/`application/pdf`/`image/svg+xml`; extension/MIME mismatch rejected client-side; 10 MB+1 rejected; error-code mapping; no credential string appears in thrown errors or console. `use-asset-upload`: happy path → `ready`; `rejected` finalize surfaces rejected; 401 → session expired; expired-authorization retry re-authorizes with the same idempotency key.

Backend `tests/test_assets_phase2a.py`, two distinct staging users (A, B):

1. no Authorization → 401
2. `image/gif` → 400 `invalid_file_type`
3. `photo.png` declared `image/jpeg` → 400 `invalid_file_type` (extension/MIME mismatch)
4. declared 11 MB → 400 `file_too_large`
5. authorization creates one `pending_upload` row at `<user_id>/<asset_id>/original.png`, `expires_at ≈ +30min`
6. **repeated authorization** with same idempotency key → same `asset_id`, same path, still exactly one row, fresh URL
7. PNG, JPEG, WebP each: upload + finalize → `ready`, correct dims/size/content type, 64-char sha256, `expires_at ≈ +30d`
8. **repeated finalize** on `ready` → 200 identical metadata, no second download, `finalized_at` unchanged
9. corrupt bytes named `.png` → 422 `asset_validation_failed`, row `rejected`, object deleted; re-finalize → 409
10. 5000x1000 PNG → rejected (width limit); 4096x4097 → rejected (height limit); 8192x4096 → rejected (pixel count)
11. animated WebP → rejected; APNG → rejected
12. decompression-bomb PNG → rejected as validation error, not a warning
13. SVG/GIF/TIFF/HEIC/PDF/AVIF payloads renamed `.png` → all rejected at magic-byte stage
14. reused signed upload authorization (second `PUT` to same URL) → storage rejects; expired authorization → `PUT` fails and retry re-authorizes cleanly
15. cross-user isolation: B finalize / GET / list of A's asset → 404; B cannot see A's row via the client (RLS SELECT check)
16. owner signed thumbnail returns 200 image; unauthenticated fetch of the raw object path → 400/403
17. `select public from storage.buckets where id='generation-assets'` → `false`
18. one Flux V6 generation still completes with unchanged metadata and zero `usage_ledger` rows; V5 `/health` still `version: v5`

Deliverable doc: `phase-2a-build-manifest.md` — migration id, endpoint list, bucket config, limit table, deferred ledger integration point, checklist results.

## 6. Order once approved

1. Apply migration + create private bucket (staging).
2. Deliver backend files here → you paste and `modal deploy api.py` (worker untouched).
3. Frontend panel + tests in this repo.
4. Run the 18-item checklist and report before any Netlify redeploy.
