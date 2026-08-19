# Fix the 403 job history and the 401/unreachable Generation API

Two separate failures are in that console output. One is confirmed and fixable here; the other lives in the Modal API.

## 1. Confirmed: the database tables have no API privileges (the 403s)

A privileges query returns **zero rows** for `public.generation_jobs`, `public.generation_usage` and `public.allowed_emails`. The RLS policies exist and are correct (`auth.uid() = user_id AND is_email_allowed(auth.uid())`), but Supabase's Data API role has no `GRANT` on the tables, so every read is rejected with `403 permission denied` before RLS is even evaluated. That is exactly the repeated 403 on `/rest/v1/generation_jobs`.

Fix: one migration adding the missing grants.

```sql
GRANT SELECT ON public.generation_jobs   TO authenticated;
GRANT SELECT ON public.generation_usage  TO authenticated;
GRANT SELECT ON public.allowed_emails    TO authenticated;
GRANT ALL    ON public.generation_jobs   TO service_role;
GRANT ALL    ON public.generation_usage  TO service_role;
GRANT ALL    ON public.allowed_emails    TO service_role;
```

No `anon` grants and no INSERT/UPDATE for `authenticated` — job mutation stays with the API's service role, as specified.

## 2. The Generation API: 401 then "Could not reach"

"Could not reach the Generation API" is what the client reports when `fetch` itself throws, which on a browser means the response was blocked, not absent — a CORS/preflight failure. Alongside it the POST recorded a `401`. Both point at the Modal service rather than this frontend:

- If the API does not return `Access-Control-Allow-Origin` for `https://brandverita-image-lab.netlify.app` (and does not answer `OPTIONS`), the browser hides the real response and the app can only say "could not reach".
- The `401` means the request that did land was refused by token verification.

Frontend-side this is already as tight as it can get: `use-generation.ts` reads a fresh token from Supabase immediately before every POST, poll and re-sign.

Step: verify with the two console snippets against the live API to separate CORS from auth, then act:

- Preflight blocked → add explicit CORS middleware in `api.py` allowing the Netlify origin plus `Authorization` header and `OPTIONS`, and redeploy.
- Token refused with `token_invalid` → the API validates against a different Supabase project than the one issuing the magic link; align `SUPABASE_URL` in the `brandverita-supabase-comfy-ui` secret.
- `auth_backend_unavailable` (500) → the secret's service-role key is wrong or unreadable.

## Order of work

1. Apply the grants migration (fixes the recent-jobs panel immediately).
2. Confirm the jobs list loads without a 403 on the live site.
3. Run the API probe and, based on the result, hand you the corrected `api.py` CORS/auth block to redeploy on Modal.

## Technical notes

- The stray `has token: false` lines come from the earlier console snippet reading `window.supabase`, which this app never defines. It is not a signal; ignore it.
- No schema or policy changes beyond privileges; no frontend code change is required for item 1.
