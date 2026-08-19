# Diagnose "Session expired" on generation

The UI shows "Session expired. Please sign in again." for any 401/403 from the Generation API. Since you are signed in and the magic link worked, the token exists in the browser — so the 401 is being produced by the API's token check, not by the app's login state. Which of the two possible causes it is has not been confirmed yet, so step 1 is to find out rather than guess.

Two candidate causes:

1. The API cannot verify the token — its Supabase credentials are not reaching the container, or the verification call fails. The current code catches every exception in the verification path and returns the same generic 401, so a missing `SUPABASE_URL` looks identical to a genuinely expired token.
2. The browser never sends the header — for example the request goes out before the session is restored after the magic-link redirect.

## Step 1 — Confirm which one it is (no code changes)

Run one authenticated request by hand against the deployed API using your current browser token, and read the response body. That distinguishes "missing bearer token" from "invalid or expired access token" from a credentials failure. I will give you the exact two commands to paste (one to print the token from the app, one curl).

## Step 2 — Make the API honest about failures

Regardless of the outcome, the API should stop collapsing every failure into one message. I will produce an updated `api.py` that:

- Returns `401` with `token_missing` only when there is no bearer header.
- Returns `401` with `token_invalid` only when Supabase actually rejects the token.
- Returns `500` with `auth_backend_unavailable` when the service cannot reach Supabase or its own secret is missing, so a misconfiguration no longer masquerades as an expired login.
- Attaches the Modal secret to the auth-verifying function explicitly and fails loudly at startup if `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` are absent.

You redeploy with `modal deploy api.py`.

## Step 3 — Frontend follow-ups, only if step 1 points there

- Map the new `auth_backend_unavailable` case to a "Generation service misconfigured" banner instead of "Session expired".
- If the token is genuinely missing on submit, hold the Generate button disabled until the Supabase session has finished loading, and refresh the token immediately before each request instead of reusing the one captured at render.

## Technical notes

- No secrets enter this repo; all Supabase service-role handling stays in the Modal app.
- Error copy stays in `src/lib/generationApi.ts` (`errorFromStatus`), which already parses FastAPI `detail` payloads, so richer API error codes surface without restructuring the client.
