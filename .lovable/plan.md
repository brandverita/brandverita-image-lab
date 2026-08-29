# Phase 2A Acceptance Testing — Execution Plan

V6 API is deployed with the assets module live (`/health` reports `assets: true`, `assets_bucket: generation-assets`). This plan covers running the Phase 2A acceptance checks and the follow-up actions based on results. No code changes are part of this plan.

## 1. Automated backend test run (user's local machine)

From the local `test` directory containing `test_assets_phase2a.py`:

1. Install dependencies in the Python 3.10 venv: `pip install httpx pillow`.
2. Obtain two distinct staging user tokens (user A and user B, both on the allow-list):
   - Sign in to the Image Lab preview as user A.
   - Browser console: `Object.values(localStorage).map(v => { try { return JSON.parse(v).access_token } catch { return null } }).find(Boolean)`
   - Copy as `TOK_A`. Repeat in an incognito window as user B for `TOK_B`.
3. Run:
   ```bash
   export V6="https://brandverita--brandverita-api-v6-fastapi-app.modal.run"
   export TOK_A="<token A>"
   export TOK_B="<token B>"
   python test_assets_phase2a.py
   ```
4. Expected: `16/16 automated checks passed`, covering:
   - 401 unauthenticated; 400 disallowed MIME, ext/mime mismatch, 11 MB oversize
   - Authorization idempotency (repeated key reuses same pending asset)
   - PNG/JPEG/WebP happy paths to `ready` with sha256 + size + content_type
   - Idempotent repeated finalize
   - 422 rejections: corrupt bytes, 4096px dimension limits, animated WebP/APNG, decompression bomb, 6 foreign payloads renamed `.png`
   - Reused signed upload URL rejected by storage
   - Cross-user isolation (404 finalize/GET, absent from list)
   - Signed read works for owner; public bucket URL does not serve objects

Tokens expire after ~1 hour; re-copy fresh ones if unexpected 401s appear mid-run.

## 2. Manual verification checks (printed by the script)

- **17 — Bucket privacy (SQL Editor):** `select public from storage.buckets where id='generation-assets';` → expect `false`.
- **18 — Generation unaffected:** run one authenticated Flux V6 generation end-to-end; confirm it completes; `select count(*) from usage_ledger;` → expect `0` (ledger unwired by design in 2A).
- **V5 untouched:** `curl https://brandverita--brandverita-api-fastapi-app.modal.run/health` → still `version: v5`.

## 3. Frontend smoke test (Image Lab preview)

- Sign in to the preview, scroll to the Asset Test panel below the generation section.
- Upload a real PNG/JPEG/WebP: expect phases authorizing → uploading → finalizing → ready, with sha256 fingerprint and metadata shown.
- Confirm the asset appears in the panel's asset list with a working signed thumbnail.
- Negative check: a `.gif` or >10 MB file is rejected client-side with a clear message (no API call).

## 4. Outcome handling

- **All checks pass:** record results in the Phase 2A build manifest (`backend/phase2a-v6/phase-2a-build-manifest.md`) — test date, pass counts, and any observations — and mark Phase 2A verified. Phase 2A is then complete; outpaint, Replicate/BFL dispatch, Studio UI, billing, and production work remain explicitly out of scope pending separate phase approval.
- **Any failure:** paste the FAIL lines (and API response codes) here for diagnosis before retrying. Do not modify the deployed API or schema until the failure is understood.

## Technical details

- No database, storage, Modal, or Netlify changes are made by this plan.
- Test script location: user's local `test/` directory; canonical copy at `backend/phase2a-v6/tests/test_assets_phase2a.py` in this repo.
- The script never submits a Flux job (step 18 is manual), so the run is cheap and safe to repeat.
