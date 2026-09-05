# Multi-Issuer JWKS — Integration README

Accept Studio-issued Supabase login tokens on the staging Generation API, in
addition to the existing comfy-ui tokens. Audience is pinned to
`authenticated`; verification is local JWKS against each issuer's public
`.well-known/jwks.json`. No database, RLS, frontend, or registry change.

Registry/flag gates run AFTER auth, so a verified Studio token still cannot
reach the research modules: those rows stay `research_only` / `internal` /
staging-only and return `403 workflow_not_available`.

## What changed

| File | Change |
|------|--------|
| `jwks_auth.py` | NEW drop-in replacement. Same public interface (`verify_via_jwks(token, url)`), now multi-issuer. Reads `EXTRA_JWT_ISSUER_URLS`. |
| `api.py` | `.env` gains `EXTRA_JWT_ISSUER_URLS`; `get_verified_user_id` routes the REST fallback (extra-issuer tokens never hit the primary REST endpoint); `/health` gains `jwt_issuers`. |

## Why jwks_auth.py is a full replacement

`jwks_auth.py` (and `supabase_rest.py`) live only in your local Modal staging
folder, not in this repo. So this repo carries a complete, reviewed drop-in
that keeps the exact interface the deployed `api.py` already imports. You will
overwrite the old file.

## Deploy steps

1. Copy `backend/phase2b/jwks_auth.py` into `modal-project/phase1-v6-staging/`,
   REPLACING the existing `jwks_auth.py`. (Same filename, same import.)
2. Copy `backend/phase2b/api.py` over `modal-project/phase1-v6-staging/api.py`.
   It already contains the `.env` entry below — no manual env edit needed:
   ```
   "EXTRA_JWT_ISSUER_URLS": "https://bowhzbhwrflbsefxpucn.supabase.co",
   ```
3. Clear the cache so the new files are bundled:
   ```
   rm -rf modal-project/phase1-v6-staging/__pycache__
   ```
4. Deploy:
   ```
   cd modal-project/phase1-v6-staging
   modal deploy api.py
   ```

No new Modal Secret is required — the issuer URL is a public project URL, not
a credential, so it belongs in `.env`, not a secret.

## Verify

1. Health shows both issuers (comfy-ui first, Studio second):
   ```
   curl https://brandverita--brandverita-api-v6-fastapi-app.modal.run/health
   ```
   Expect `jwt_issuers` containing `thspgkedjkiltrcimond` and
   `bowhzbhwrflbsefxpucn`.

2. Existing Lab (comfy-ui) auth still works — a Lab request that worked before
   still returns 200, not 401. (Primary issuer is tried first; behaviour is
   unchanged.)

3. Studio token is ACCEPTED by auth, then stopped by the gate — a request
   signed by the Studio project no longer returns `401 session expired`; it
   returns `403 workflow_not_available` on the research modules (they remain
   internal/staging-only). This is the intended end state.

4. Unauthenticated request still returns `401 token_missing`.

## Rollback

Restore the previous `jwks_auth.py` and `api.py` from your pre-change copy and
`modal deploy api.py`. Removing the `EXTRA_JWT_ISSUER_URLS` line (or emptying
it) also returns the API to single-issuer behaviour with no other change.
