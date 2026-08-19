# Fix "Session expired" on generation

## What the checks show

The deployed Modal API is healthy and correct: `GET /health` returns ok, `POST /v1/generations` exists, and cross-origin preflight from `brandverita-image-lab.netlify.app` is allowed. Calling `POST /v1/generations` with no auth header returns exactly `401 {"detail":"Missing bearer token"}` — the response you are seeing. So the API is rejecting the request because **no bearer token arrived**, not because your login expired.

The second console line points the same way: the Supabase REST call to `generation_jobs` was rejected with "No API key found in request". Two unrelated clients both losing their headers on the live site is the thing to explain — and the Netlify build does have all five `VITE_*` values baked in, so this is not a missing-env-var build.

The `{"detail":"Method Not Allowed"}` line is a separate, smaller bug: it is a `GET` on the collection path, which happens when the polling call runs with an empty job id (`/v1/generations/` → redirect → `GET /v1/generations` → 405). That fires after the POST already failed.

The exact reason headers are absent is not yet confirmed, so step 1 confirms it before changing behaviour.

## Step 1 — Confirm where the headers are lost (no code changes)

I will give you a short snippet to paste into the console on the live site while signed in. It reports whether `supabase.auth.getSession()` currently returns a token, and sends one test `POST /v1/generations` with the header attached, printing the status only. Outcomes:

- Test call succeeds → the app is submitting before/without the session token; go to step 2.
- Test call also 401s → the token itself is being refused; we look at the Supabase session/JWT side instead.
- Headers missing even in the manual call → something in the browser (extension/shield) is stripping cross-origin headers; retest in a clean profile.

## Step 2 — Make the frontend always send a live token

Changes in the generation path:

1. Fetch the token at call time. `useGeneration` currently captures `session.access_token` from render. Instead, read a fresh token via `supabase.auth.getSession()` immediately before each POST and each poll, so a token refreshed after the magic-link redirect is always used.
2. If no token is available, fail with a clear "You are signed out — sign in again" state instead of firing an unauthenticated request.
3. Keep the Generate button disabled until the session has finished loading (currently it only depends on API health).
4. Guard polling: never issue a request when `job_id` is missing — surface "The API did not return a job id" instead, which removes the 405 noise.
5. Refresh the recent-jobs query after the session becomes available so it is not run in a signed-out state.

## Step 3 — Make the API distinguish failure kinds

Updated `api.py` (you redeploy) so a 401 tells the truth:

- `token_missing` when no bearer header is present.
- `token_invalid` when Supabase actually rejects the token.
- `500 auth_backend_unavailable` when the service cannot reach Supabase or its secret is absent — today that case is also reported as a 401, which reads as "session expired".

The frontend error mapping in `src/lib/generationApi.ts` gains a matching branch so a misconfiguration never shows up as a login problem.

## Technical notes

- No secrets enter this repo; service-role handling stays in the Modal app.
- Token retrieval stays client-side Supabase; no server routes are added.
- Error copy remains centralised in `errorFromStatus` in `src/lib/generationApi.ts`.
