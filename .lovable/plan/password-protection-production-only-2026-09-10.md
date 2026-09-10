# Password protection: production only

## Decision

Leaked-password checking stays off in the staging test project. Staging has a
small, allow-listed set of internal test accounts, so the risk is negligible and
the notice can remain open there.

It becomes a required step on the production project, before any real person can
create an account and choose their own password.

## What gets recorded now

Add a production go-live item to `roadmap.md`, in the same section that tracks the
other production setup work:

- Turn on leaked-password protection in the production project's authentication
  settings (dashboard toggle, no code change, no migration).
- Set a minimum password length on the same screen.
- Do this before the first non-internal account is created.
- Note explicitly that the staging project is intentionally left as is, so the
  open warning there is not mistaken for an oversight later.

Also note the two other standing staging notices as expected, not defects: the
locked registry rows and the internal allow-list helper.

## Not changing

- No staging authentication settings.
- No database changes, no policy changes, no code changes.
- Storage stays private with signed-URL-only reads and owner-scoped rules.
