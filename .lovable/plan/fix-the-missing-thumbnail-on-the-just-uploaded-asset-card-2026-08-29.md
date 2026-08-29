# Fix the missing thumbnail on the just-uploaded asset card

## Live smoke test result

All five checks behaved correctly except one cosmetic gap:

- Test 1 — Asset Test panel present: PASS
- Test 2 — 348 KB PNG reached `ready` with SHA256: PASS, but the top "Ready:" card shows "no preview"
- Test 3 — GIF not selectable in the macOS file picker: **expected behaviour**, not a bug. The input's `accept="image/png,image/jpeg,image/webp"` makes macOS grey out GIFs, so the client-side rejection path can't be reached from the picker. The server-side GIF rejection is already proven by automated test 2 (`image/gif -> 400`) and test 13 (`gif renamed .png -> rejected`).
- Test 4 — Flux generation still completes: PASS
- Test 5 — `hi@brandverita.io` has the panel and uploads successfully, with the same missing top thumbnail: PASS with the same cosmetic gap

## Root cause (confirmed)

Two different endpoints supply the two cards, and only one returns a signed preview URL:

- `POST /v1/assets/{id}/finalize` returns `_safe_asset(updated)` — **no** signed read URL, so `read_url` is null and the card renders its "no preview" placeholder.
- `GET /v1/assets` returns `_safe_asset(row, storage_signed_read_url(...))` — includes the signed URL, which is why the recent list shows the thumbnail.

This is by design on the backend: finalize is the write/validate step and deliberately doesn't mint read credentials. The bucket is private, so a preview is only possible via a short-lived signed URL.

## Fix: frontend only, no backend redeploy

In `src/hooks/use-asset-upload.ts`, after a successful finalize that returns `status: "ready"`, fetch the asset once via the existing `getAsset(assetId, token)` and use that response (which carries `read_url`) as the hook's `asset` state. If that follow-up call fails, keep the finalize result as-is — the asset is still correctly `ready`, it just renders without a thumbnail, exactly as today. Nothing about validation, idempotency, or the upload path changes.

Result: the top card shows the same thumbnail as the recent list, from a 5-minute signed URL issued after the server's ownership check.

## Also worth adding (small, same file/component)

In `src/components/generation/AssetTestPanel.tsx`, note in the helper text that only PNG, JPEG and WebP can be selected, so a tester doesn't read the greyed-out GIF as a broken picker.

## Technical notes

- No change to `backend/phase2a-v6/assets.py`, the schema, RLS, grants, bucket privacy, or the API contract.
- No new endpoint calls beyond `GET /v1/assets/{id}`, which the typed client already exposes.
- Signed URLs stay short-lived and are never persisted or logged.
- After the change: `bun run test` (20 unit tests) must still pass, then push to `brandverita/generation-test-ui` `main` for Netlify to redeploy.

## Out of scope (unchanged)

No outpainting, Replicate/BFL dispatch, Studio UI, billing, usage-ledger wiring, or production deployment.
