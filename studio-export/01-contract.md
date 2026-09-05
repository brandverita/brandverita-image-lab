# 01 — API contract

Base URL: the Generation API for the target environment (one value, injected as
configuration). All endpoints require `Authorization: Bearer <Supabase access
token>` for the signed-in user. All bodies are JSON unless stated.

The flow is always the same three phases:

```text
1. input asset    authorize upload -> PUT bytes -> finalize -> asset_id (ready)
2. transformation POST /v1/generations with asset_id + enums -> job_id
3. result         poll GET /v1/generations/{job_id} -> output_asset_id + read_url
```

---

## 1. Input assets

### POST /v1/assets/upload-authorizations

Request:

```json
{
  "file_name": "bottle.png",
  "content_type": "image/png",
  "file_size": 482113,
  "idempotency_key": "<uuid v4>"
}
```

Allowed content types: `image/png`, `image/jpeg`, `image/webp`.
Limits: 10 MB, max 4096 x 4096, max 16 777 216 pixels, single frame only
(animated PNG/WebP is rejected).

Response:

```json
{
  "asset_id": "uuid",
  "upload_url": "https://…",
  "method": "PUT",
  "content_type": "image/png",
  "expires_in": 300,
  "max_file_size": 10485760,
  "reused": false,
  "already_finalized": false
}
```

`upload_url` is short-lived and single-path. Keep it in the scope of the upload
call; never store, log or render it.

### PUT `upload_url`

Raw bytes, header `Content-Type` equal to the authorization's `content_type`. No
Authorization header. Any non-2xx is an upload failure — re-authorize and retry.

### POST /v1/assets/{asset_id}/finalize

No body. The server downloads the object, sniffs magic bytes, rejects animated
containers and decompression bombs, reads real dimensions, hashes it, and only
then marks the row `ready`. Returns the asset record.

### GET /v1/assets/{asset_id} and GET /v1/assets?limit=12

Asset record shape (the only fields a client ever sees):

```json
{
  "asset_id": "uuid",
  "status": "pending_upload | ready | rejected | deleted | expired",
  "kind": "input | output",
  "content_type": "image/png",
  "file_size": 482113,
  "width": 1024,
  "height": 1024,
  "sha256": "…",
  "created_at": "…",
  "finalized_at": "…",
  "expires_at": "…",
  "read_url": "https://… (short-lived, present only when readable)",
  "read_url_expires_in": 300
}
```

There is no `storage_path`, no bucket URL and no public URL. Assets expire 30
days after creation.

---

## 2. Option catalogs

### GET /v1/scene-presets

```json
{
  "scene_directions": [{ "scene_direction": "clean_studio", "label": "Clean studio" }],
  "background_styles": ["editorial", "high_key", "neutral", "soft_shadow"],
  "output_presets": ["1080x1080", "1080x1350", "1200x627", "1600x900"]
}
```

Instruction text behind each scene is never returned. Outpaint's options are
fixed enums with no catalog endpoint — see `02-catalogs.md`.

### GET /v1/workflows?origin=studio

Server-filtered list of workflows the caller may use. Fields are safe only:
`key`, `version`, `display_name`, `description`, `status`, `provider`,
`provider_model`, `commercial_status`, `allowed_dimensions`,
`estimated_credits`, `enabled_for_studio`, `production_enabled`.

**Today `origin=studio` returns neither `outpaint:v1` nor `product_scene:v1`** —
both are `research_only` / internal. Treat their absence as "feature not
available for this environment" and hide the entry points rather than failing.

---

## 3. Submit a transformation

### POST /v1/generations

Smart Resize / Outpaint:

```json
{
  "workflow_id": "outpaint",
  "workflow_version": "v1",
  "source_asset_id": "uuid of a ready, owned input asset",
  "output_preset": "1200x627",
  "params": {
    "expansion_mode": "anchor_directional",
    "direction": "left",
    "anchor": "right",
    "style_mode": "preserve_source"
  },
  "idempotency_key": "<uuid v4>"
}
```

Product Background / Scene:

```json
{
  "workflow_id": "product_scene",
  "workflow_version": "v1",
  "source_asset_id": "uuid of a ready, owned input asset",
  "output_preset": "1080x1080",
  "params": {
    "scene_direction": "clean_studio",
    "background_style": "soft_shadow",
    "preserve_subject": true
  },
  "idempotency_key": "<uuid v4>"
}
```

`workflow_id` may also be written as `"outpaint:v1"` / `"product_scene:v1"` with
`workflow_version` omitted.

**Rejected outright** (400 `invalid_request`), anywhere in the body or `params`:
`prompt`, `negative_prompt`, `workflow`, `graph`, `nodes`, `image_url`, `mask`,
`width`, `height`, `ratio`, `offset`, `seed_override`, `url`, `urls`, `base64`,
`data`, `loras`, `controlnet` — and any key not in the module's allow-list. The
canvas size, mask and every instruction word are derived server-side from the
preset and enums.

### GET /v1/generations/{job_id}

```json
{
  "job_id": "uuid",
  "status": "queued | dispatching | running | uploading_output | completed | failed | canceled | expired",
  "workflow_id": "outpaint",
  "workflow_version": "v1",
  "provider": "…",
  "provider_model": "…",
  "workflow_config_hash": "…",
  "progress": null,
  "width": 1200,
  "height": 627,
  "result_url": "short-lived signed URL when completed",
  "queued_at": "…",
  "started_at": "…",
  "completed_at": "…",
  "error_code": null,
  "error_message": null,
  "source_asset_id": "uuid",
  "output_asset_id": "uuid",
  "output_preset": "1200x627",
  "request_params": { "direction": "left", "anchor": "right", "…": "…" }
}
```

Poll every 2 seconds. Stop on `completed`, `failed`, `canceled`, `cancelled`,
`expired`, or on your own timeout (12 minutes is the value used in the Lab) and
offer a manual retry. The client never writes job status — only the platform
does.

### GET /v1/generations/{job_id}/result

`{ "job_id": "…", "result_url": "https://…" }` — a fresh signed URL for a
completed job. Use it when a previously issued URL has expired. Returns 409 if
the job is not completed.

---

## 4. Errors

Error bodies are one of `{"detail": "code: message"}` or
`{"detail": {"error_code": "…", "error_message": "…"}}`. Show the message; never
show or log a raw body.

| Code | HTTP | What to tell the user |
| --- | --- | --- |
| `invalid_request` | 400 | The selection was rejected — reset to valid options and retry. |
| `workflow_not_available` | 403 | This feature is not available in this environment. Hide the entry point. |
| `asset_not_found` / `asset_not_owned` | 404 | This image could not be found. Upload it again. |
| `asset_not_ready` | 409 | The image is still being checked — wait a moment. |
| `asset_expired` | 409 | The image has expired (30-day retention). Upload it again. |
| `asset_validation_failed` | 400 | Must be a single-frame PNG/JPEG/WebP, max 4096 x 4096, max 10 MB. |
| `source_integrity_failed` | 422 | The result failed its integrity check and was discarded. Retry. |
| `rate_limited` | 429 | Limit reached — wait before trying again. |
| `storage_unavailable` | 503 | Temporarily unavailable — retry in a moment. |
| 401 / `token_invalid` | 401 | Session expired — sign in again. |
| `token_missing` | 401 | The request had no login token — sign out and back in. |
| `auth_backend_unavailable` | 500 | Service configuration problem, not the user's session. |
| any 5xx | 5xx | Service temporarily unavailable — retry. |

Job-level failures arrive as `status: "failed"` with an `error_code` such as
`transformation_failed`, `dispatch_failed`, `worker_timeout` or
`provider_credential_missing`. All are retryable from the user's point of view;
`provider_credential_missing` is an operations problem and should also be
alerted internally.

Retry rule: reuse the **same** `idempotency_key` when retrying the exact same
submission after a transport failure; generate a new one for a new submission.
