# 03 — Integration guide

Wiring order for the Studio app, using the code in `client/` and (optionally)
`reference-ui/`.

## Step 1 — configuration

One value per environment: the Generation API base URL. Studio already holds the
Supabase session, so the client only needs a token getter.

```ts
import { createGenerationClient } from "./client/generationClient";

export const generationClient = createGenerationClient({
  baseUrl: import.meta.env.VITE_GENERATION_API_URL,
  getAccessToken: async () => (await supabase.auth.getSession()).data.session?.access_token ?? null,
});
```

No other secret, key or provider setting belongs in Studio's client. See
`05-security-boundaries.md`.

## Step 2 — feature discovery, not hard-coding

Call `listWorkflows("studio")` on load and only render an entry point when the
matching key is present:

```ts
const workflows = await generationClient.listWorkflows("studio");
const hasOutpaint = workflows.some((w) => w.key === "outpaint");
const hasProductScene = workflows.some((w) => w.key === "product_scene");
```

Today both are absent by design (`research_only`, internal). Hide the buttons
rather than showing a broken feature; when the readiness list in
`04-production-readiness.md` is cleared, they appear with no Studio redeploy.

## Step 3 — input asset

`uploadInputAsset(file)` performs authorize → PUT → finalize and resolves with a
`ready` asset record, or throws a `TransformationApiError` with a user-safe
message. Keep only `asset_id` in your own state; treat `read_url` as ephemeral.

## Step 4 — submit and poll

```ts
const { phase, job, resultUrl, errorMessage, start, retry } = useTransformation(generationClient);

await start({
  module: "product_scene",
  source_asset_id: asset.asset_id,
  output_preset: "1080x1080",
  params: { scene_direction: "clean_studio", background_style: "neutral", preserve_subject: true },
});
```

The hook submits once, polls every 2 seconds, halts on any terminal status,
times out at 12 minutes, and exposes a manual `retry()` that reuses the same
idempotency key. Do not add a second polling loop or an optimistic "done" state.

## Step 5 — result

- Show the image from `resultUrl` with real alt text.
- Download straight from that URL; if it has expired, call `refreshResultUrl()`
  (`GET /v1/generations/{job_id}/result`) instead of caching the old one.
- Persist `output_asset_id` if Studio needs to reference the result later; fetch
  a fresh signed URL each time it is displayed.

## Step 6 — options UI

Both features are enum-only. Use dropdowns or segmented controls; never a text
field. For product scene, load labels from `GET /v1/scene-presets` and fall back
to the table in `02-catalogs.md` if the call fails. For outpaint, narrow the
anchor choices to those allowed for the selected direction
(`OUTPAINT_ANCHORS_BY_DIRECTION` in `client/types.ts`) so an invalid combination
cannot be submitted.

## Step 7 — states and accessibility

The reference UI covers all four states: empty ("No image yet…"), loading
(spinner, submit disabled), error (light red banner with a Retry action), and
success (preview plus a prominent Download). Keep visible focus rings, real
labels on every control, and descriptive alt text on both the source preview and
the result.

## Step 8 — what to check before shipping

- Both features are hidden when `listWorkflows("studio")` omits them.
- A rejected file (animated GIF/WebP, 20 MB, 6000 px) shows the validation
  message and no job is created.
- A failed job shows a retry, and retrying does not create a duplicate.
- No signed URL, storage path, token or request body appears in the console,
  logs or analytics.
- Expired-link download recovers via the refresh action.
