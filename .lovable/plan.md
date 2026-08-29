# Phase 2A Image Lab — deploy + verify (deploy already live)

## Acceptance: complete

- 28/28 automated checks pass (animated WebP/APNG rejection fixed, public-bucket check 16b passes).
- Manual 17 confirmed from here: `storage.buckets.public = false` for `generation-assets`.
- `usage_ledger` count = 0 (ledger unwired, as designed).
- Manual 18 confirmed by you: one Flux V6 generation completes; V5 `/health` still reports `version: v5`.

## Deployment: already shipped

- Phase 2A frontend files (`src/lib/assetsApi.ts`, `src/hooks/use-asset-upload.ts`, `src/components/generation/AssetTestPanel.tsx`, the `index.tsx` mount, vitest config) are pushed to `brandverita/generation-test-ui` `main`.
- Netlify built and deployed them at 8:24pm (Bangkok) to `brandverita-image-lab.netlify.app`.
- `VITE_GENERATION_API_URL` already points at the V6 API with `assets.py` deployed — no Netlify env change was needed.

## Remaining action: live smoke test (you, ~2 min)

On `https://brandverita-image-lab.netlify.app`:

1. Sign in as `brandverita@gmail.com`; the "Asset Test (internal)" panel appears below the generator.
2. Upload a small PNG → reaches "ready" with a SHA256 fingerprint and a thumbnail.
3. Upload a GIF → rejected with the "Only PNG, JPEG and WebP images are supported." message.
4. Run one text-to-image generation → confirms the main flow is untouched.
5. (Optional) Sign in as `hi@brandverita.io` and confirm you cannot see user A's assets (cross-user isolation in the live UI).

## After the smoke test passes

I'll record Phase 2A acceptance as complete in project memory (the Phase 2A outcome file), so the next session starts from a "done" baseline rather than re-deriving it.

## Rollback

If anything on the live site is broken: Netlify → deploys → republish the previous deploy. The panel is additive and fails gracefully if the API is unreachable, so risk is low.

## Out of scope (unchanged)

No outpainting, Replicate/BFL dispatch, Studio UI, billing, usage-ledger wiring, or production deployment.
