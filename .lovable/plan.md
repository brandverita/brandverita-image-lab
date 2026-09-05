# Accept Studio Supabase tokens in the Generation API (staging)

## What the Studio team actually needs

Their note says "the Image Lab side must accept login tokens". One correction: the
Image Lab **frontend** is not the verifier — the **Modal Generation API** is. The
API currently verifies every bearer token against one issuer only, the staging
`comfy-ui` project (`jwks_auth.py`, single JWKS endpoint, audience
`authenticated`). A token issued by Studio's Supabase project
(`bowhzbhwrflbsefxpucn`) fails that check today and falls back to the comfy-ui
REST check, which rejects it — surfacing as "session expired". So the change is
entirely in the API deployment: teach it a second trusted issuer.

Nothing changes in the Image Lab frontend, the Studio export package, the
registry, or any flag. Both advanced modules stay `research_only / internal /
staging-only` and `enabled_for_studio=false`, so even with an accepted token,
Studio dispatch of outpaint/product_scene is still refused by the registry until
a separate approval. This step only removes the auth wall.

## Changes (all in the Modal staging deployment)

1. **`jwks_auth.py` — multi-issuer verification**
   - Read an optional env var, e.g. `EXTRA_JWT_ISSUER_URLS`, a comma-separated
     list of Supabase project base URLs. For Studio:
     `https://bowhzbhwrflbsefxpucn.supabase.co`.
   - For each issuer: derive `{url}/auth/v1` as issuer, fetch
     `{url}/auth/v1/.well-known/jwks.json`, cache keys per issuer, require
     audience `authenticated`. The comfy-ui issuer stays first and unchanged.
   - A token is accepted if it verifies against **any** configured issuer;
     failure kinds (`token_missing` / `token_invalid` /
     `auth_backend_unavailable`) stay distinct as today.

2. **`api.py` — fallback routing only**
   - `get_verified_user_id` tries JWKS across all issuers first (no code change
     beyond passing the issuer list).
   - The Supabase REST fallback stays scoped to comfy-ui only. For tokens whose
     unverified `iss` claim names an extra issuer, skip the REST fallback and
     return `token_invalid` — the API holds no anon key for Studio's project and
     never should.

3. **No database or RLS changes.** API writes are service-role; ownership is
   stamped from the verified user id, which works identically for Studio-issued
   user ids. Row-level read policies are only exercised by the Lab frontend
   against the comfy-ui project, unaffected here.

## Your action (one step)

Add the env var to the Modal V6 API app and redeploy:

```text
EXTRA_JWT_ISSUER_URLS=https://bowhzbhwrflbsefxpucn.supabase.co
```

(Modal → the V6 API app → environment, same place the five advanced flags
live.) No new secret is needed — JWKS verification uses the public keys from the
well-known endpoint; nothing private from Studio's project is stored.

## Verification

1. `/health` reports unchanged for existing markers; a new marker
   `jwt_issuers: ["comfy-ui", "bowhzbhwrflbsefxpucn"]` (count only, no keys).
2. Existing Lab sign-in still works: run one Flux generation from the Lab.
3. With a Studio-project token: `POST /v1/generations` for `outpaint:v1`
   returns **403 `workflow_not_available`** (feature gate), not 401 — proving
   the token was accepted while the module stays closed. The same request
   without a token still returns 401 `token_missing`.

## Safety notes

- Audience stays pinned to `authenticated`; issuer list is server-side config,
  never client-supplied.
- Studio tokens grant no extra capability: registry gates, origin visibility,
  and flag checks run after auth exactly as before.
- The staging project remains user-free research infrastructure; Studio's own
  production deployment will get its own Supabase project per the readiness
  document, so this issuer addition is a staging-integration convenience, not
  the production identity design.
