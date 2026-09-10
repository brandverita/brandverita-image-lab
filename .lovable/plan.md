# Turning on Generate image for Studio, and choosing the Smart resize provider

Two separate asks, one shared root cause: the tool list the Studio reads is decided
entirely by the image service's registry, and today no row in it is marked as
production-approved. That is why Generate image stays hidden, and it is also the
switch that decides whether Smart resize runs on BFL.

## What the registry actually says right now

Read from the `comfy-ui` project today:

| tool | row | state | approved for production | visible to Studio |
|---|---|---|---|---|
| Generate image | `flux_text_to_image:v1` | active | no (`pending_review`) | no |
| Smart resize (BFL) | `outpaint:v2` | testing | no (`research_only`) | no |
| Smart resize (self-hosted) | `outpaint:v1` | testing | no | no |
| Product scene | `product_scene:v1` | testing | no | no |

Every row is staging-only and internal. Yet Product scene and Smart resize already
work inside app.brandverita.io, which means the Studio's calls are currently being
treated as internal Lab calls rather than Studio calls. That is the one thing I
could not confirm from here and it changes the work, so step 1 below is a check,
not an assumption.

## Step 1 — confirm two facts with the Studio team (blocking, no code)

1. The exact service address app.brandverita.io calls. If it is
   `brandverita--brandverita-api-v6-fastapi-app.modal.run`, Studio is on the
   staging service and shares the `comfy-ui` database with the Image Lab.
2. Whether their tool-list call sends `origin=studio` or `origin=lab`.

The answers decide whether Generate image needs only a registry change (Lab-style
calls) or also the production approval flags (Studio-style calls).

## Step 2 — turn Generate image on

Add a new immutable row `flux_text_to_image:v2` rather than editing v1, keeping the
existing research row untouched for comparison:

- same self-hosted Modal Flux worker and pinned graph as today
- `commercial_status = commercial_self_hosted_approved` (already recorded as
  approved on 2026-09-05), `status = active`
- `registry_visibility = studio_safe`, `enabled_for_studio = true`,
  `production_enabled = true`
- `allowed_envs` includes the environment Studio actually calls (confirmed in step 1)
- size list restricted to the five approved sizes, no source image required

Then run the config-hash tool for the new row, and confirm the row appears in the
service's tool list for a real Pro account.

Studio side, the only work is what `studio-export/06-image-generation.md` already
describes: discover the workflow instead of hard-coding it, one prompt box, one
optional negative box, one size dropdown, reuse the existing polling and result
handling. No new provider, no new credentials, no BFL disclosure obligations —
this one is self-hosted.

## Step 3 — Smart resize on BFL for production

What changes for the app.brandverita.io team: nothing in their UI. They keep calling
the same Smart resize entry point; the provider lives entirely in the service.

What changes here:

- add `outpaint:v3` as the production-approved BFL expand row (same adapter,
  same negation-free instruction and settings that are now running cleanly),
  marked `studio_safe`, `enabled_for_studio`, `production_enabled`
- keep `outpaint:v1` and `v2` as internal research rows for the score bench
- the Studio's shared client keeps pointing Smart resize at the newest approved
  row, so the Pixelcut path can be retired by the Studio team without touching
  the service

Provider choice is server-owned: the browser never names a provider. Switching
between Pixelcut and BFL is therefore a decision in two places only — which entry
point the Studio calls, and which registry row that entry point resolves to.

## Step 4 — confirm the money and the terms

- BFL Smart resize is about $0.05 per run against Pixelcut's $0.10; the credit
  price per tool is set by myaccount, so they need the final per-run cost for
  `smart_resize` before the switch.
- BFL's public API terms apply to Smart resize exactly as they do to Product
  scene: the usage policy must be flowed into Studio's end-user terms, users must
  be told a third party processes the image and may use it for model improvement,
  and images with identifiable personal data must be refused. Those three items
  are already open on the roadmap for Product scene and now cover Smart resize too.
- Generate image carries none of these, being self-hosted.

## What I am not doing in this plan

- No separate production Supabase project, workers or API yet. Everything above
  works on the service Studio already calls; the production split stays on the
  roadmap as its own piece of work.
- No Product scene provider change — it stays on BFL `flux-kontext-pro`, which is
  working.
- No changes to app.brandverita.io code from here; its handoff stays documentation.

## Docs I would still like

- The Studio team's tool-list request as they send it (address, origin, headers).
- The myaccount contract doc listing the five granted tools with the key naming,
  so the service's row keys and their tool keys line up (`image_generation` there
  vs `flux_text_to_image` here — that mapping should be written down once).
