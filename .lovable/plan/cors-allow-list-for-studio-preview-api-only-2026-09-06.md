# CORS allow-list for Studio + preview (API only)

Only **one** CORS surface actually blocks the Studio today: the **Modal FastAPI
API** (`brandverita--brandverita-api-v6-fastapi-app.modal.run`) — the JSON calls
the Studio client makes: `GET /v1/workflows`, `POST /v1/assets/upload-authorizations`,
`POST /v1/assets/{id}/finalize`, `POST /v1/generations`, polling, result URL.

The second candidate surface — **Supabase Storage** (where the image-byte `PUT`
and signed read `GET` go) — was checked and is already wide open (`*`), so it
needs no change (see part 2).

The Studio team's "check both at once" instinct was right to raise; the answer
is that the storage side is already covered.

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

## 2. Supabase Storage CORS — NO ACTION NEEDED (verified)

The Studio team flagged this as a "worth checking both at once" risk. It is
already safe: I probed the Storage host directly and it returns
`Access-Control-Allow-Origin: *` with `PUT` allowed on signed upload URLs, for
every origin (Studio, Lab, anything). The dashboard has no CORS UI under
Settings or Policies — there is nothing to configure, and nothing to change.

Probe result (OPTIONS preflight to
`https://thspgkedjkiltrcimond.supabase.co/storage/v1/object/upload/...`):

```
access-control-allow-origin: *
access-control-allow-headers: content-type
access-control-allow-methods: GET,HEAD,PUT,PATCH,POST,DELETE,OPTIONS,TRACE,CONNECT
access-control-max-age: 3600
```

So the upload `PUT` and signed read `GET` are not blocked by Storage CORS. The
only CORS surface that blocks the Studio today is the Modal FastAPI API
(part 1). The Studio team does not need to add Storage origins or policies.

Note for the record: the `No policies created yet` message on the
`generation-assets` / `generation-outputs` buckets in the Policies tab is
expected and correct — these buckets are private by design and accessed only
via signed URLs issued server-side; no `storage.objects` RLS policies exist on
purpose (per Phase 2A manifest). Do not add public/anonymous storage policies.

## Verification

After part 1 is deployed, from the Studio origin:
- `GET /v1/workflows?origin=studio` on the API returns 200 (no CORS error).
- A full asset upload round-trip succeeds: authorize → `PUT` to the signed
  storage URL (already CORS-allowed, no change) → finalize returns a ready asset.

## Scope

Staging only. One code change: `ALLOWED_ORIGINS` in `backend/phase2b/api.py`, then
redeploy. No Supabase Storage change (verified open). No registry, RLS, frontend,
or production changes. No new secrets. The Studio team's `baseUrl` stays
`https://brandverita--brandverita-api-v6-fastapi-app.modal.run`.
