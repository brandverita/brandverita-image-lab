# Lock the app to authorized emails (magic link)

Right now anyone who finds the Netlify URL can submit generation jobs. This adds a sign-in wall: only emails you have approved can get in, and they sign in with a one-time link sent to their inbox — no passwords.

## Access model

- A database table holds the approved email addresses. You add or remove people there; no redeploy needed.
- Sign-in flow: visitor enters their email, gets a magic link, clicks it, lands back on the app signed in.
- Approval is enforced in the database, not just the UI: a signed-in user who is not on the list can read nothing and, on the API side, has no job rows. The UI also shows a clear "This email is not authorized for the generation test" state and signs them straight back out.
- Everything is behind the wall: unauthenticated visitors see only the header and a sign-in card — no form, no result panel, no job history.

## What changes

1. **Database**: new `allowed_emails` table (email, optional note, timestamp), RLS on, plus a small security-definer helper so a signed-in user can check only whether their own email is approved. Your own email is seeded so you can log in immediately. Existing `generation_jobs` / `generation_usage` policies additionally require the email to be approved.
2. **Auth screen**: replaces the current email/password panel. Email field, "Send magic link" button, "check your inbox" confirmation, resend, and readable error states (unknown/unauthorized email, rate limited, expired link). Same light neutral / deep blue styling.
3. **Gate**: the page renders the sign-in screen until there is a session AND that session's email is approved. The generation form, result panel and recent jobs mount only after both are true.
4. **Header**: shows the signed-in email and a Sign out action next to the existing status indicators.
5. **Supabase config**: magic-link (OTP) sign-in enabled, redirect URL set to the Netlify site so links land back on the app correctly.

## About the failed test run

"This generation job could not be found" came from the polling step: the job was created but the follow-up lookup returned 404. That is the FastAPI service's job-lookup path, not the frontend — the request was almost certainly made without a signed-in user, so the API had no user-scoped job to return. Gating the app removes the unauthenticated case entirely; if it still 404s once signed in, the fix belongs in the FastAPI service (persist the job row before returning the ID, and scope the lookup to the verified user).

## Technical notes

- Auth stays client-side Supabase (`signInWithOtp` with `emailRedirectTo`); no server routes, no service-role key, nothing new in the public repo.
- Allowlist check runs through a `SECURITY DEFINER` function keyed on `auth.uid()`, so the table itself is never readable by clients — no email list leaks.
- Magic-link emails send through Supabase's built-in mailer on the comfy-ui project; volume for a test harness is well inside its limits.
- One new client-safe env var is not needed; nothing added to Netlify beyond the existing Supabase vars.
