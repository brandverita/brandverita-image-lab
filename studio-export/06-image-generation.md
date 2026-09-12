# 06 — Image generation (text to image) for Studio

Plan only. Nothing in this file has been wired into Studio; it describes how the
existing, already-working Flux text-to-image workflow is added to
`app.studiobrandverita.io` using the same client in `client/`.

## What already exists

- Workflow key `flux-schnell-txt2img-v1`, served by the same Generation API base
  URL Studio already uses for the two advanced features.
- No source asset: this is the one workflow where `source_asset_id` must be
  absent. The API rejects a request that attaches one.
- The result is a private asset plus a short-lived signed link, exactly as for
  smart resize and product scene.

## Request

```ts
POST /v1/generations
{
  "workflow_id": "flux-schnell-txt2img-v1",
  "inputs": {
    "prompt": "<user text, max 2000 chars>",
    "negative_prompt": "<optional, max 1000 chars>",
    "width": 1024,
    "height": 1024,
    "seed": 12345            // optional
  },
  "idempotency_key": "<uuid v4>"
}
```

Allowed sizes are a dropdown, never free numbers: `512x512`, `768x768`,
`1024x1024`, `1280x1024`, `1024x1280`.

## Lifecycle

Identical to the other features, so the polling code is reused unchanged:
submit once, poll `GET /v1/generations/{job_id}` every 2 seconds, stop on
`completed` / `failed` / `expired`, offer a manual retry that reuses the same
idempotency key. A cold worker can take a few minutes on the first run of the
day; keep the 12-minute ceiling rather than a short timeout.

## Result

`result_url` on the completed job, refreshed via
`GET /v1/generations/{job_id}/result` when a link has expired. Persist only
`output_asset_id`.

## Gating

Studio must discover the workflow instead of hard-coding it:

```ts
const workflows = await generationClient.listWorkflows("studio");
const canGenerate = workflows.some((w) => w.key === "flux_text_to_image");
```

The row is live as of 2026-09-10: `flux_text_to_image:v2`, `status = active`,
`commercial_self_hosted_approved`, `studio_safe`, `production_enabled = true`,
`enabled_for_studio = true`, allowed in staging and production. Send
`workflow_id: "flux_text_to_image"` with `workflow_version: "v2"` — the legacy
alias `flux-schnell-txt2img-v1` still resolves to the old internal research row
and will be refused for a Studio-origin call.

Self-hosted, no third-party provider, so none of the BFL disclosure obligations
in `03-integration-guide.md` step 8 apply to this tool. myaccount already sends
`image_generation` in its granted list, so nothing is needed on that side.

## UI notes

- One text area with a visible character count, one optional negative field, one
  size dropdown, one optional seed.
- Empty / loading / error / success states as in `reference-ui/ResultPane.tsx`.
- Never log the prompt, the signed link or the token.

## Out of scope for this document

Billing, credits, prompt suggestion or enhancement, batch generation, custom
workflows, and any raw provider setting. None of those are exposed by the API.

---

## Brand consistency mode ("Branding") — 2026-09-12

Text-to-image now accepts a **style request** instead of a prompt. The API
composes the prompt from three server-owned layers, so every picture in a
campaign shares the same setting and finish.

    Layer 1  occasion / seasonal atmosphere   (chosen per picture)
    Layer 2  setting & visual DNA             (the brand anchor — byte-identical every run)
    Layer 3  subject hero                     (what is being sold, one short line)
    + universal quality tail                  (fixed; only the aspect note follows the canvas)

### Catalogue

`GET /v1/prompt-layers` (bearer token required)

```json
{
  "seasons": [{ "key": "autumn", "label": "Autumn", "hint": "Golden afternoon light, harvest tones" }],
  "worlds":  [{ "key": "coastal_terrace", "label": "Coastal terrace", "hint": "Mediterranean stone, sea horizon" }],
  "subject_max_chars": 200,
  "layer_table_version": "prompt-layers-1"
}
```

The layer wording is never returned. Do not mirror, cache, or re-word it
client-side — a local copy is exactly how two apps drift apart.

### Request

`POST /v1/generations` — `style` replaces `prompt`; sending both is a 400.

```json
{
  "workflow_id": "flux_text_to_image",
  "workflow_version": "v2",
  "inputs": {
    "style": { "season": "autumn", "world": "coastal_terrace", "subject": "a hand-poured soy candle in an amber jar" },
    "width": 1024,
    "height": 1024,
    "seed": 20260912,
    "idempotency_key": "<uuid v4>"
  }
}
```

Rules enforced server-side: `season`/`world` must be catalogue keys (unknown
keys are rejected, never defaulted); `subject` is required, max 200 characters,
newlines collapsed; the composed prompt must stay within 2000 characters.

### Consistency guidance

* Keep one `world` per brand and change only `season` + `subject`.
* Reuse the same `seed` across a set for the tightest match; change it only when
  you want a genuinely different composition.
* Validation errors name the field, e.g.
  `invalid_request: style: unknown world: 'lagoon'`.

### Provenance

Each job records `request_params.style` with `season`, `world`, `aspect`,
SHA-256 of each layer's exact text, and `layer_table_version`. That is how an
older picture is traced to the wording that produced it. Wording changes ship as
a new `layer_table_version`, never as an edit in place.

Free-text generation is unchanged and remains fully supported in parallel.
