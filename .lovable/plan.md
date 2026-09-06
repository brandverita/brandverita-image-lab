# The finished picture exists — the app is just never told where it is

## What I found (confirmed from the database)

Your last three runs all succeeded and the finished files are safely stored:

| Run | Type | Size | State |
| --- | --- | --- | --- |
| 13:03 | Product scene | 1080 x 1080 | ready, 887 KB |
| 13:00 | Smart resize | 1600 x 900 | ready, 2.3 MB |
| 12:56 | Smart resize | 1200 x 627 | ready, 2.2 MB |

So nothing is lost and no picture failed. The problem is only in what the
service hands back to the app:

- The original text-to-image feature saves its picture in one place and reports
  a `result_url` link, which the app shows.
- The two new features save their picture as a **stored asset** instead, and the
  older reporting code only knows how to build a link from the first kind. It
  leaves the link empty.

That is exactly what you saw: no failed image request in the inspector, because
the app was never given an address to load. The "Refresh the link" action fails
the same way (it refuses with "result is not available").

## The fix (service side only, no Studio change)

In the Generation API:

1. When reporting a finished job, if there is no old-style path but there **is**
   a stored output asset, look that asset up and mint a short-lived signed link
   for it, returning it as `result_url` alongside the existing `output_asset_id`.
   This covers both the status check the app polls and the initial submit reply.
2. Apply the same rule to the "refresh the link" endpoint so an expired link can
   be renewed for the new features too.
3. Only the owner's own assets are ever looked up, links stay short-lived, and
   the storage stays private — no policy, bucket, or permission change.

Nothing changes for the existing text-to-image feature, and the Studio app and
the exported client need no edits: they already read `result_url`.

## Technical detail

- Files touched: `backend/phase2b/jobs.py` (response builder) and
  `backend/phase2b/api.py` (`GET /v1/generations/{job_id}/result`), reusing the
  existing signed-read helper from `assets.py` / `advanced.py`.
- Lookup keyed on `generation_assets.id = output_asset_id` with
  `owner_id = caller`, `status = 'ready'`, `deleted_at is null`; bucket
  `generation-assets`, path `<owner>/<asset>/original.png`.
- If signing fails, `result_url` stays null and the app's existing refresh
  action remains available — no error is invented.
- After the change you deploy the updated files to the Modal V6 app (clear
  `__pycache__`, `modal deploy api.py`), then re-run one Smart Resize and one
  Product Scene and confirm the picture appears. Existing WP1/WP2 test suites
  should still pass.

## Out of scope

No worker, graph, registry, provider, Studio UI, billing, or production
deployment changes.
