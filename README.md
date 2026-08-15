# BrandVerita Image Lab

Build a small production-shaped test application called “BrandVerita Generation Test”.

Purpose:

This is an isolated technical test for BrandVerita’s future image-generation service. It must not modify or replace the existing production Studio/Tela app at app.brandverita.io. Do not import, clone, or embed the ComfyUI repository into this frontend project. The frontend will call a separate BrandVerita Generation API, which will later invoke ComfyUI running on Modal.

Architecture:

- Frontend: this Lovable project.

- GitHub repository: create or sync to a new repository named brandverita/generation-test-ui.

- Database and authentication: the existing Supabase project named “comfy-ui”.

- Image-generation backend: a separate API, configured through VITE_GENERATION_API_URL.

- GPU backend: not called directly by this frontend. The Generation API will call Modal and ComfyUI server-side.

- Do not connect this project to the existing review-display-magic repository.

- Do not connect this project to the public brandverita/ComfyUI repository.

- Do not place Modal credentials, Supabase service-role keys, Hugging Face tokens, ComfyUI credentials, or STUDIO_HANDOFF_SECRET in frontend code.

Initial scope:

Build only a simple Flux Schnell text-to-image test interface.

The first version must support:

1. A prompt input.

2. Optional negative prompt input.

3. Width selector.

4. Height selector.

5. Optional seed input.

6. Generate button.

7. Job status display.

8. Progress/loading state.

9. Generated image preview.

10. Download button.

11. Clear error state.

12. Retry action.

13. A small developer/status panel showing job ID, workflow ID, status, and elapsed time.

14. A reset button to return to the empty state.

Do not build yet:

- Product upload.

- Product placement.

- Background removal.

- IP-Adapter.

- LoRA training.

- ControlNet.

- Inpainting.

- Outpainting.

- Video generation.

- Billing.

- Public sharing.

- Brand kit management.

- Tela integration.

- myaccount integration.

- Arbitrary ComfyUI workflow editing.

- Direct browser-to-Modal calls.

Visual direction:

Use a clean BrandVerita-style workspace interface:

- Light neutral background.

- Deep blue primary action color.

- Spacious but practical layout.

- Clear left-aligned headings.

- One primary Generate action.

- Responsive desktop and mobile layout.

- Use accessible labels and visible keyboard focus states.

- Do not use a futuristic neon style, purple gradients, glowing backgrounds, or decorative AI imagery.

- Make the interface feel like an internal creative production tool.

- Use clear empty, loading, success, and error states.

Page layout:

1. Header:

   - BrandVerita Generation Test title.

   - Small “Development environment” badge.

   - Connection status indicator.

2. Main area:

   - Left panel: generation form.

   - Right panel: result preview.

3. Below the main area:

   - Recent test jobs list from Supabase.

4. Footer/status:

   - Show configured API environment without displaying secrets.

   - Show whether the frontend is connected to Supabase.

   - Do not expose service credentials.

Environment variables:

Use only client-safe variables:

- VITE_GENERATION_API_URL

- VITE_GENERATION_ENABLED

- VITE_SUPABASE_URL

- VITE_SUPABASE_PUBLISHABLE_KEY

- VITE_SUPABASE_PROJECT_ID, if required by the Supabase integration

Assume:

- VITE_GENERATION_API_URL will point to the test Generation API.

- VITE_GENERATION_ENABLED should be true for this test.

- Never create or request a VITE_SUPABASE_SERVICE_ROLE_KEY.

- Never create or request Modal secrets in the frontend.

- Never put private API keys in source code.

Supabase:

Connect this Lovable project to the existing Supabase project named “comfy-ui”.

Create or use the following tables through safe migrations:

generation_jobs:

- id uuid primary key

- user_id uuid nullable or linked to auth.users

- workflow_id text not null

- status text not null

- prompt_hash text nullable

- modal_call_id text nullable

- output_path text nullable

- result_url text nullable only if the API returns a short-lived signed URL

- error_code text nullable

- error_message text nullable

- width integer not null

- height integer not null

- created_at timestamptz not null

- started_at timestamptz nullable

- completed_at timestamptz nullable

generation_usage:

- id uuid primary key

- user_id uuid nullable or linked to auth.users

- usage_period date not null

- jobs_count integer not null default 0

- gpu_seconds numeric not null default 0

- created_at timestamptz not null

Use Row Level Security:

- A user may read only their own generation_jobs.

- A user may not update job status directly from the browser.

- A user may not insert arbitrary completed jobs from the browser.

- The Generation API, using server-side credentials, is responsible for creating and updating job records.

- Do not expose Supabase service-role access to the client.

If authentication is needed for the test, implement simple Supabase email/password authentication:

- Sign up.

- Sign in.

- Sign out.

- Protected generation page.

- Display the current user email.

- Do not add social login yet.

- Do not use demo credentials in production code.

Generation API contract:

The frontend must call the API base URL from VITE_GENERATION_API_URL.

Use these endpoints:

POST /v1/generations

Request:

{

  "workflow_id": "flux-schnell-txt2img-v1",

  "prompt": "string",

  "negative_prompt": "string",

  "width": 1024,

  "height": 1024,

  "seed": 123456789,

  "idempotency_key": "uuid"

}

Expected response:

{

  "job_id": "uuid",

  "status": "queued",

  "workflow_id": "flux-schnell-txt2img-v1",

  "created_at": "ISO timestamp"

}

GET /v1/generations/{job_id}

Expected response while running:

{

  "job_id": "uuid",

  "status": "queued|running",

  "workflow_id": "flux-schnell-txt2img-v1",

  "progress": 0,

  "created_at": "ISO timestamp",

  "started_at": "ISO timestamp or null"

}

Expected response when completed:

{

  "job_id": "uuid",

  "status": "completed",

  "workflow_id": "flux-schnell-txt2img-v1",

  "progress": 100,

  "result_url": "short-lived signed URL",

  "width": 1024,

  "height": 1024,

  "completed_at": "ISO timestamp"

}

Expected response when failed:

{

  "job_id": "uuid",

  "status": "failed",

  "error_code": "string",

  "error_message": "user-safe message"

}

Frontend request behavior:

- Validate prompt is present.

- Limit prompt length to 2,000 characters.

- Limit negative prompt length to 1,000 characters.

- Allow only approved dimensions:

  - 512x512

  - 768x768

  - 1024x1024

  - 1280x1024

  - 1024x1280

- Generate a UUID idempotency key for every new request.

- Disable Generate while a request is being submitted.

- Never submit duplicate jobs because of double clicks.

- After POST /v1/generations, poll GET /v1/generations/{job_id} every 2 seconds.

- Stop polling when status is completed, failed, or cancelled.

- Stop polling after a reasonable timeout and show a retry option.

- Do not expose raw backend stack traces.

- Do not silently swallow API errors.

- If the API returns 401, show “Your test session has expired. Please sign in again.”

- If the API returns 429, show “Generation limit reached for this test account.”

- If the API returns 500, show “The generation service is temporarily unavailable.”

Job history:

Display the current user’s recent jobs from generation_jobs:

- Newest first.

- Show status.

- Workflow ID.

- Dimensions.

- Created time.

- Thumbnail/result when available.

- Retry failed jobs.

- Do not display another user’s jobs.

- Do not display prompts to other users.

- Handle the empty state with:

  “No test generations yet. Create your first image from the form.”

Result handling:

- Treat result_url as a short-lived signed URL.

- Do not permanently store result URLs in frontend state beyond what is needed for the current view.

- Do not assume the result URL is public.

- Add an accessible alt text such as “Generated test image”.

- Use a download button that downloads the current result.

- If the result URL expires, show a clear message and offer “Refresh result” if supported by the API.

Security:

- Never include Modal credentials in frontend requests.

- Never include Supabase service-role keys in frontend requests.

- Never include STUDIO_HANDOFF_SECRET.

- Never accept arbitrary workflow JSON from the user.

- The only initial workflow ID allowed by the UI is:

  flux-schnell-txt2img-v1

- Do not allow users to edit node IDs or ComfyUI graph structure.

- Avoid logging full prompts or tokens to the browser console.

- Do not use localStorage for secrets.

- Do not create public storage buckets.

- Do not create open CORS behavior in the frontend.

Developer experience:

- Use TypeScript.

- Use a clean API client module, for example:

  src/lib/generationApi.ts

- Use a Supabase client module, for example:

  src/integrations/supabase/client.ts

- Use typed request and response models.

- Keep API calls separate from UI components.

- Add loading, empty, success, and error states.

- Add comments where the API contract is intentionally temporary.

- Add a README section explaining:

  - Required environment variables.

  - Supabase project connection.

  - Generation API URL.

  - Local development command.

  - Netlify deployment configuration.

  - Which secrets must never be placed in the frontend.

- Do not modify any external repository.

- Do not import Tela or ComfyUI code into this project.

Acceptance criteria:

The implementation is complete only when:

1. The project is connected to the new Supabase project “comfy-ui”.

2. The project is synced to a new GitHub repository under the brandverita organization.

3. The project does not use brandverita/ComfyUI as its GitHub repository.

4. The frontend runs without the Generation API by showing a clear unavailable state.

5. The frontend can submit a valid request to VITE_GENERATION_API_URL.

6. The frontend polls the job status.

7. A completed job displays the generated image.

8. A failed job displays a friendly error and retry action.

9. Job history is restricted by Row Level Security.

10. No service-role key, Modal token, Hugging Face token, or STUDIO_HANDOFF_SECRET appears in frontend code.

11. The UI works at desktop and mobile widths.

12. The app has no mock success state pretending that an image was generated.

13. The app uses a visible development badge and is clearly separated from production BrandVerita Studio.

14. Existing production app.brandverita.io is not changed by this project.

Before making major architectural changes, explain what you plan to change and ask for confirmation. Start by creating the frontend shell, connecting Supabase, adding the schema and RLS policies, and implementing the typed Generation API client with the API URL controlled by VITE_GENERATION_API_URL.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/b64be2b1-6229-4e5a-9db3-93ec98ded2cf).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
