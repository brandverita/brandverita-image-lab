# 05 — Security boundaries for the Studio client

Hard rules. Every one is also enforced server-side, so breaking them produces a
rejected request rather than a working shortcut — but the client must not try.

## Never in Studio's frontend

- Supabase service-role key.
- Any provider API key (BFL or otherwise), Modal token, or Hugging Face token.
- `STUDIO_HANDOFF_SECRET`.
- Storage bucket paths or object keys.
- Scene instruction text, prompt text, or any workflow/graph JSON.

The only client-side values needed are the Generation API base URL, the Supabase
URL and its publishable/anon key, and the user's own session token.

## Images

- Buckets are private. There are no client-side storage policies.
- The browser only ever receives short-lived signed URLs, issued after a
  server-side ownership check.
- Do not cache, persist, log or share a signed URL. Store the asset ID and ask
  for a fresh URL when the image is displayed again.
- Provider requests are made server-side with the image inlined; the browser
  never receives provider auth and the provider never receives a Supabase URL.

## Requests

- Send enum keys only. Free text, geometry, masks, URLs, base64 payloads and
  graph fields are refused — do not add fields "just in case".
- The client never writes job status, never inserts or updates job rows, and
  never writes to `generation_assets`. Job mutation belongs to the platform.
- Reuse the same idempotency key when retrying the same submission; generate a
  new one for a new submission.

## Logging and telemetry

- Do not log request bodies, tokens, signed URLs, asset SHA256 values or full
  error bodies. Log an error code and an HTTP status at most.
- Do not send image URLs or prompts to analytics.

## Errors

Show the user-safe message from the client's error mapping. Never surface a raw
server body — it can carry internal detail — and never reveal which flag,
provider or registry state caused a refusal. `workflow_not_available` means
exactly one thing to the user: this feature is not available here.
