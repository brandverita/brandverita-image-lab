# Wiring the test UI to the Modal Generation API

The Modal ComfyUI worker is proven end to end. The next step is the frontend half of the contract you specified: this project stays a test UI only, and the FastAPI service lives in your Modal deployment repo. No Modal, ComfyUI, Hugging Face, or service-role credentials enter this codebase.

## 0. Fix a blocking dependency

`@supabase/supabase-js` is imported by the generated Supabase client but is not in `package.json`, so the page currently fails to load. Install it first.

## 1. Align the API client with the final contract

`src/lib/generationApi.ts` currently sends `inputs: { prompt, ... }` and has no seed or health call. Update it to match your spec exactly:

- `POST /v1/generations` body: flat `workflow_id`, `prompt`, `negative_prompt`, `width`, `height`, `seed`, `idempotency_key`.
- `GET /v1/generations/{job_id}` response: read `status`, `progress`, `result_url`, `width`, `height`, `completed_at`, `error_code`, `error_message`.
- `GET /health` → `{ status: "ok" }`, used for the connection indicator.
- Enablement becomes strict: generation is allowed only when `VITE_GENERATION_ENABLED === "true"` AND `VITE_GENERATION_API_URL` is set. No hardcoded URL, no default-on.
- Failed jobs surface `error_message`; `error_code` is kept for the developer panel only. Nothing is logged to the console.
- Access token from the Supabase session is attached as a bearer on both calls so the API can resolve the user and write `generation_jobs` under service role.

## 2. Seed input + reset

Add to the form: an optional seed field (integer, blank = API picks a random seed) and a Reset button that clears the form and returns the result pane to the empty state. Dimensions stay locked to the five approved sizes, workflow stays fixed and read-only, and the submit button stays disabled while a job is in flight so a double click cannot create a second job.

## 3. Job status and developer panel

- Status display covers `queued`, `running`, `completed`, `failed`, plus request timeout, using the API's own values — never a simulated success.
- Determinate progress bar when the API reports `progress`, spinner otherwise.
- A small developer/status panel under the result showing job ID, workflow ID, status, progress, and elapsed time (client clock, from submit to terminal status).
- Retry re-submits the same inputs with a fresh idempotency key.
- Download button uses the signed `result_url`; if the signed URL expires the image slot shows a "link expired, re-run to view" note rather than a broken image.

## 4. Connection status

Header indicator and footer become live: on load (and on retry) the UI calls `GET /health` and reports reachable / unreachable / not configured. When the API URL is missing, `VITE_GENERATION_ENABLED` is not `"true"`, or `/health` fails, the Generate action stays disabled and a clear API-unavailable banner explains which of the three it is — without printing the URL.

## 5. Recent test jobs

Kept as is: read-only select of the signed-in user's own rows. Once your FastAPI service writes rows under service role, this table will start populating; polling terminal status already triggers a refresh. No database or RLS changes are proposed in this step — the existing `generation_jobs` / `generation_usage` tables and policies already match the contract (client read-own only, no client insert/update). If a schema change turns out to be needed, I will show the migration and ask before running it.

## What you need to do on the API side

For the frontend to light up, your Modal FastAPI service (in the Modal project, not here) needs to:

- expose `GET /health`, `POST /v1/generations`, `GET /v1/generations/{job_id}` at a public Modal URL, with CORS allowing this preview origin and the Netlify domain;
- accept the Supabase access token as `Authorization: Bearer`, verify it, and derive `user_id` from it;
- insert the `generation_jobs` row on submit and update status/result on completion using the service-role key (server-side only);
- upload the PNG to a private Supabase Storage bucket and return a short-lived signed URL as `result_url`.

Then set `VITE_GENERATION_API_URL` to that URL and `VITE_GENERATION_ENABLED=true` in this project's environment.

## Technical notes

- No new server functions or server routes in this project; the browser calls the Modal API directly. Nothing here touches Modal or ComfyUI.
- Uploaded `modal_worker.py`, `test_worker.py`, and the workflow JSON files stay out of this repository — they belong to the Modal deployment.
- The private Storage bucket and any signed-URL policy live in Supabase; creating that bucket is a Supabase-side step I can run separately if you want it here rather than in the API repo.
