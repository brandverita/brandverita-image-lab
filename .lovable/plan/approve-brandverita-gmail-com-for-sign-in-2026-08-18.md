# Approve brandverita@gmail.com for sign-in

The allow-list table is currently empty, so no one can get past the magic-link wall. This adds your address.

## Change

- Insert one row into the approved-emails list: `brandverita@gmail.com` (note: "primary test account"). Stored lowercase so the case-insensitive check matches.
- No code changes; no schema changes. The sign-in screen, allow-list check and job/usage read policies already exist.

## After it's applied

1. Open the app, enter `brandverita@gmail.com`, request the magic link.
2. Click the link from the same browser — it should land back signed in with the generation form visible.
3. Run one test generation. If "This generation job could not be found" appears again while signed in, the remaining fix is in the FastAPI service (persist the job row before returning its ID, and scope the lookup to the verified user) — not in this frontend.

## Technical note

Applied as a migration with an idempotent insert (skips if the address is already present), since the table is not writable from the browser by design.
