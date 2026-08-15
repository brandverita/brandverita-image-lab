# BrandVerita Generation Test — build plan

Supabase is still not attached to this project (no integration files, no `SUPABASE_*` env vars). The plan below is ordered so the frontend work happens first and the database step runs the moment the comfy-ui connection lands.

## 1. Frontend shell

Rewrite `src/routes/index.tsx` as the single test page:

- Header: title "BrandVerita Generation Test", a small "Development environment" badge, and a live connection status indicator (API reachability + Supabase session).
- Desktop two-pane layout: left = generation form, right = result preview. Stacks on mobile.
- Footer: API environment label (dev/staging derived from the URL, never the full URL) and Supabase connection status.
- Route `head()` with its own title/description and OG tags.

## 2. Design system

Light neutral surfaces (slate-50 / white), deep blue primary (blue-600/700) for actions and focus rings, clean sans-serif, left-aligned headings. Tokens go in `src/styles.css`; components use semantic classes only. No neon, purple gradients, glow shadows, or default dark mode.

## 3. Typed Generation API client

New `src/lib/generationApi.ts`, the only module that talks to the API:

- Base URL from `VITE_GENERATION_API_URL`; feature flag `VITE_GENERATION_ENABLED`.
- Workflow ID hardcoded to `flux-schnell-txt2img-v1`; no JSON/workflow uploads.
- `createGeneration()` → `POST /v1/generations` with a client-generated UUID v4 `idempotency_key`.
- `getGeneration(jobId)` → `GET /v1/generations/{job_id}`.
- Typed request/response shapes and a normalised error type mapping 401 → "Session expired", 429 → "Limit reached", 5xx → "Service temporarily unavailable".
- No logging of prompts, base64 payloads, or tokens.

## 4. Form + lifecycle

- Prompt (required, max 2000 chars), negative prompt (optional, max 1000), dimensions dropdown limited to 512x512, 768x768, 1024x1024, 1280x1024, 1024x1280. Live character counters and visible focus states.
- Submit disables the button, polls every 2s, halts on `completed` / `failed` / timeout with a manual Retry.
- States: empty ("No test generations yet. Create your first image from the form."), loading spinner, red-tinted error banner with Retry, success with image preview (descriptive alt text) and a prominent Download button. No mock successes.

## 5. Job history (after Supabase lands)

Read-only list of the signed-in user's recent jobs via `@supabase/supabase-js`, select-only — the frontend never inserts or updates job rows.

## 6. Database step (blocked on the connection)

Once comfy-ui is attached, inspect the existing schema first. Create only what is missing:

- `generation_jobs`: `id`, `user_id`, `workflow_id`, `status`, `prompt_hash`, `modal_call_id`, `output_path`, `result_url`, `width`, `height`, `created_at`, `updated_at`.
- `generation_usage`: `user_id`, `period`, `jobs_count`, `gpu_seconds`.
- Grants: `GRANT SELECT ON <table> TO authenticated;` and `GRANT ALL ... TO service_role;` — no `anon` access.
- RLS enabled; SELECT policy `auth.uid() = user_id` only. No client INSERT/UPDATE policies, so job mutation stays with the backend API.

## Technical notes

- Stack stays TanStack Start + Vite + TypeScript + Tailwind; no Lovable Cloud features used.
- Only client-safe env vars: `VITE_GENERATION_API_URL`, `VITE_GENERATION_ENABLED`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`, `VITE_SUPABASE_PROJECT_ID`. No service-role, Modal, HF, or handoff secrets anywhere in the frontend.
- No ComfyUI or Modal code in this repo; deployment remains GitHub (`brandverita/generation-test-ui`) to Netlify.
