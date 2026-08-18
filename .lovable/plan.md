# Make repo safe to make public (for Netlify free-tier deployment)

## Context

Netlify's free plan cannot build from a private org repo. Making the repo
public is the path of least resistance. We verified the current committed
state to decide if that is safe.

## Safety verdict: ACCEPTABLE to make public

The security model is RLS-based, NOT key-secrecy-based. Everything in the
repo is already designed to ship to every browser visitor of the deployed
app, so "hiding" it in a private repo provides zero security.

Verified (read of tracked files + git history):
- Committed `.env` contains ONLY client-safe publishable/anon keys
  (`VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_PROJECT_ID`).
  These are meant to be embedded in the client bundle — they are public by
  design and protected by RLS.
- NO `sb_secret_` service-role key value anywhere (code reads
  `SUPABASE_SERVICE_ROLE_KEY` from env at call time in client.server.ts; the
  value is never committed).
- NO `MODAL_TOKEN`, `HUGGINGFACE_TOKEN`, or `STUDIO_HANDOFF_SECRET` in tracked
  files or git history.
- Migrations contain only `GRANT ... TO service_role` statements (standard SQL,
  fine to be public). No secret literals.
- `supabaseAdmin` is server-only code, loaded inside handlers, env read at
  call time — code being public is fine.

## Implications of going public (low concern for a test project)

1. Anyone can read the frontend source, the README, and the API contract.
   For an internal test tool this is low risk.
2. The publishable keys in `.env` are exposed — but they were always going to
   be exposed (they ship to the browser). RLS is the real control.
3. `VITE_GENERATION_API_URL`, when set, will also be public — it's just a URL,
   not a credential. FastAPI must enforce its own auth (Bearer token check).
4. No new attack surface from public-vs-private: RLS already assumes the keys
   are public.

## Recommended hardening (1 task)

`.env` is currently tracked but contains only safe values. The risk is that a
FUTURE edit to `.env` adds a secret, which would then leak on push. Prevent
that:

1. Add `.env` (and `.env.*`, `!.env.example`) to `.gitignore`.
2. Create `.env.example` with placeholder values documenting the required
   vars (`VITE_GENERATION_API_URL`, `VITE_GENERATION_ENABLED`,
   `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`,
   `VITE_SUPABASE_PROJECT_ID`) — no real values.
3. Keep real values in Netlify's Environment Variables UI for the deployed
   build; do not rely on a committed `.env` for production.
4. Optional: `git rm --cached .env` so the current file stops being tracked
   (this is a state-changing git op — only run if you approve; it does not
   delete the local file).

Note: `git rm --cached .env` is the one state-changing git op in this plan.
Everything else is file edits. The repo must remain buildable on Netlify, so
Netlify env vars must be set before/alongside this change.

## Out of scope

- Changing RLS policies (no migration).
- Any server routes in this project (frontend-only).
- Touching Modal/FastAPI code.
