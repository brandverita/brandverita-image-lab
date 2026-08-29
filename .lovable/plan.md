# Approve hi@brandverita.io for sign-in

The sign-in error is correct behavior: `hi@brandverita.io` completed magic-link signup (visible in the auth logs) but is not on the approved-emails allow-list, so `current_user_allowed()` returns false. The allow-list table is not writable from the browser by design, so the row is added through a privileged SQL path.

## Change

- Insert one row into `public.allowed_emails`: `hi@brandverita.io` (note: "second test user"). Stored lowercase so the case-insensitive `is_email_allowed` check matches.
- Idempotent: skips the insert if the address is already present.
- No schema changes, no RLS changes, no code changes. Same pattern previously used to approve `brandverita@gmail.com`.

## After it's applied

1. Have the second user click "Try again" (or re-request the magic link) at the sign-in screen — no new account needed, the user already exists in Supabase Auth.
2. Confirm the generation form and Asset Test panel appear for that account.
3. This also unblocks `TOK_B` for the Phase 2A acceptance test run: sign in as `hi@brandverita.io` in an incognito window and copy its access token from localStorage.

## Technical note

Executed as a data insert via the SQL tool (runs with elevated privileges; `auth.uid()` is not involved). Existing RLS on `generation_assets`, `generation_jobs`, `generation_usage`, and `usage_ledger` automatically extends to the newly approved user — no policy edits required.
