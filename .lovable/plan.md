# Deploy Image Lab frontend with the Phase 2A Asset Test panel

## Status of acceptance

- 28/28 automated checks pass, including the fixed animated WebP/APNG rejection (tests 11) and the public-bucket check (16b).
- Manual check 17 confirmed from here: `storage.buckets.public = false` for `generation-assets`.
- `usage_ledger` count = 0 confirmed (ledger still unwired, as designed).
- One check left to you: run a single Flux V6 generation in Image Lab and confirm it completes (regression), plus V5 `/health` still reports `version: v5`.

## What ships

Frontend changes already in this repo, deployed via the existing GitHub (`brandverita/generation-test-ui`) → Netlify pipeline to `brandverita-image-lab.netlify.app`:

- `src/lib/assetsApi.ts` — typed asset API client (upload authorization, finalize, list, signed read URL)
- `src/hooks/use-asset-upload.ts` — authorize → upload → finalize state machine with idempotent retry
- `src/components/generation/AssetTestPanel.tsx` — Asset Test panel mounted at the bottom of `src/routes/index.tsx`, gated on session + allow-list
- Unit tests (20 passing) and `vitest.config.ts`

No backend, schema, env var, or workflow changes. `VITE_GENERATION_API_URL` already points at the V6 API that has `assets.py` deployed — no Netlify env change needed.

## Steps

1. Final regression check (you, ~1 min): one Flux generation in the current preview/Image Lab → completes with an image; `curl $V5/health` → `version: v5`.
2. Commit and push the current working tree to `main` on `brandverita/generation-test-ui`. Netlify builds and deploys automatically.
3. Verify the Netlify deploy log succeeds (no env or build changes expected).
4. Smoke test on the live Image Lab URL:
   - Sign in as `brandverita@gmail.com`; the Asset Test panel appears below the generator.
   - Upload a small PNG → reaches "ready" with a SHA256 fingerprint.
   - Upload a GIF → rejected with a clear validation message.
   - Run one text-to-image generation to confirm the main flow is untouched.

## Rollback

Netlify → deploys → republish the previous deploy. The panel is additive and fails gracefully (shows "unavailable" rather than breaking the page) if the API is unreachable, so risk is low.

## Out of scope (unchanged)

No outpainting, Replicate/BFL dispatch, Studio UI, billing, usage-ledger wiring, or production deployment.
