# Fix: Smart resize fails with "did not return a readable response"

## What is happening

That message is the one the app shows when the request never reaches the service at all — no status code, no body. It is not a Smart resize failure; the browser blocked the call before sending it.

Cause, confirmed in the code: the new test bench sends one extra label on the request (`Idempotency-Key`) that the service's browser-permission list does not include. The permission list currently allows only `Authorization` and `Content-Type`, so the browser refuses the whole request. Every other screen works because none of them send that label.

The same run number is already inside the request body (`idempotency_key`), so the label is redundant.

## The fix

1. Remove the extra header from the two new calls in `src/lib/advancedApi.ts` (Smart resize and Product scene). Repeat-protection is unchanged — the value still travels in the body, which is what the service reads.
2. Also add `Idempotency-Key` to the service's allowed header list in `backend/phase2b/api.py` (`allow_headers`), so a future client sending it is not blocked. This needs your usual copy-to-Modal + clear cache + redeploy, but step 1 alone makes the test bench work immediately without a redeploy.

## Also worth correcting while here

The service's allowed-origins list contains an old Lovable preview address (`id-preview--b2d8d333-…`). The current preview for this project is `id-preview--b64be2b1-…`. Testing on the Netlify staging site is unaffected, but if you ever test from the Lovable preview it would be blocked. I will add the current preview address alongside the existing entries.

## Out of scope

No change to Smart resize behaviour, presets, prompt wording, registry rows, config hashes, Product scene, or production. No Pixelcut wiring.
