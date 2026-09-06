# CORS allow-list for Studio + preview (API + Supabase Storage)

Two CORS surfaces block the Studio upload. Both must be updated, because the
browser makes requests to **two different hosts**:

1. The **Modal FastAPI API** (`brandverita--brandverita-api-v6-fastapi-app.modal.run`)
   — JSON calls: `GET /v1/workflows`, `POST /v1/assets/upload-authorizations`,
   `POST /v1/assets/{id}/finalize`, `POST /v1/generations`, polling, result URL.
2. **Supabase Storage** (`thspgkedjkiltrcimond.supabase.co/storage/v1/...`) — the
   actual `PUT` of image bytes to the signed upload URL, plus the signed read
   `GET` of generated/preview images. This host is a different domain from the
   API, so its CORS is configured separately, in the Supabase project — not in
   `api.py`.

The Studio team is right: checking "both at once" is required.

## Origins to add (both surfaces)

```
https://app.brandverita.io                                                            # Studio
https://id-preview--b2d8d333-eb4f-49b0-8086-f5764b1a4938.lovable.app                 # working preview (testing)
```

Keep the existing origins on both surfaces:
`https://brandverita-image-lab.netlify.app`, `https://lab.brandverita.com`,
`http://localhost:8080`.

## 1. API CORS — code change in this repo

File: `backend/phase2b/api.py`, the `ALLOWED_ORIGINS` list (lines 146–150).

```python
ALLOWED_ORIGINS = [
    "https://brandverita-image-lab.netlify.app",
    "https://lab.brandverita.com",
    "https://app.brandverita.io",
    "https://id-preview--b2d8d333-eb4f-49b0-8086-f5764b1a4938.lovable.app",
    "http://localhost:8080",
]
```

No other change to the CORS middleware is needed:
- `allow_methods=["GET", "POST", "OPTIONS"]` already covers every API route the
  Studio client calls. The API itself never receives a `PUT` — the byte upload
  goes straight to Supabase Storage (see part 2).
- `allow_headers=["Authorization", "Content-Type"]` already covers the bearer
  token and JSON body the client sends.
- The `_cors_headers(request)` helper (used for hand-built error responses)
  reads the same `ALLOWED_ORIGINS` list, so error responses stay CORS-clean too.

After editing, redeploy the staging V6 app:

```bash
cd modal-project/phase1-v6-staging   # (wherever your deploy copy of api.py lives)
modal deploy api.py
curl -s https://brandverita--brandverita-api-v6-fastapi-app.modal.run/health
```

## 2. Supabase Storage CORS — action in the Supabase dashboard

This is the part that actually fixes the upload `PUT`. Supabase Storage CORS is
**not** settable from this repo or via SQL; it lives on the hosted project.

Project: `comfy-ui` (`thspgkedjkiltrcimond`).

In the Supabase Dashboard:

1. Open project `thspgkedjkiltrcimond` → **Storage** → **Settings** (or
   **Configuration** → **CORS** in newer dashboard layouts).
2. Add the same origins above to the Storage CORS allow-list:
   - `https://app.brandverita.io`
   - `https://id-preview--b2d8d333-eb4f-49b0-8086-f5764b1a4938.lovable.app`
   - `https://brandverita-image-lab.netlify.app`
   - `https://lab.brandverita.com`
   - `http://localhost:8080` (for local Studio dev)
3. Allow methods `GET`, `PUT`, `OPTIONS` (and `POST` if the dashboard offers a
   method list — the signed-upload `PUT` is the critical one). Allow headers
   `Content-Type`, `Authorization` (the signed URL carries its own token in the
   query string, but `Content-Type` is sent on the PUT).

The signed upload URL is built in `assets.py:storage_signed_upload_url` and
points at `{supabase_base}/storage/v1/object/upload/...`, and signed read URLs
point at `{supabase_base}/storage/v1/object/sign/...` — both on the
`thspgkedjkiltrcimond.supabase.co` host, so one Storage CORS entry covers both.

## Why two surfaces (for the Studio team)

- `POST /v1/assets/upload-authorizations` → API returns a signed `upload_url`
  that points at **Supabase Storage**, not at the API.
- The browser then does `PUT <upload_url>` directly to Supabase Storage. That
  request never touches the Modal API, so the API's CORS cannot allow it.
- `finalize` and everything after is back to the API.

So: API CORS = part 1 (code + redeploy). Upload PUT = part 2 (Supabase Storage
CORS). Both must list the Studio origin.

## Verification

After both are applied, from the Studio origin:
- `GET /v1/workflows?origin=studio` on the API returns 200 (no CORS error).
- A full asset upload round-trip succeeds: authorize → `PUT` to the signed
  storage URL (no CORS error) → finalize returns a ready asset.

If only the API CORS is done, the `PUT` will still fail with a CORS error from
`thspgkedjkiltrcimond.supabase.co` and the preview will fail exactly as
described.

## Scope

Staging only. No registry, RLS, frontend, or production changes. No new
secrets. The Studio team's `baseUrl` stays
`https://brandverita--brandverita-api-v6-fastapi-app.modal.run`.
