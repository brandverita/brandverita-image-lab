# WP1 green — close it out, then start Module B (Product Background / Scene)

17/17 on `test_wp1_outpaint.py`, 44.7s end-to-end, source region byte-verified,
output private, Flux and V5 unaffected, `outpaint:v1` still invisible to Studio.
Module A is functionally done in staging.

## Step 1 — record the WP1 result (docs only, no code)

Append a "2026-09-01 — WP1 accepted" section to `backend/phase2b/module-a.md`
with: worker revision and API revision deployed, checkpoint pin
(`sd-v1-5-inpainting.ckpt`, sha256 `c6bbc15e…`), measured latency 44.7s against
the 90s p95 target, and the cost/gpu_seconds figures from the
`transformation_eval_runs` row. Paste that row (and the `generation_assets` row)
here and I will fold the real numbers in rather than leaving placeholders.

Registry row is unchanged: `testing` / `research_only` / `internal` /
`production_enabled=false` / `allowed_envs=[staging]`.

## Step 2 — Module A usability pass (small, staging only)

Two gaps between "the API works" and "an internal user can use it":

- Lab UI: add an outpaint panel next to the existing Asset Test panel — pick a
  ready asset, choose a preset from the registry's allowed list, choose
  direction/anchor/style, submit, poll, show before/after and a download.
  No prompt field, no free-form dimensions; the UI only offers what the
  registry allows.
- A second and third preset run (1080x1080 → 1200x627 already done; add
  1920x1080 and a portrait one) to confirm geometry and latency hold across
  aspect ratios before it is treated as a stable contract.

## Step 3 — Module B: Product Background / Scene via BFL

Reuses the WP0 framework unchanged — same `source_asset_id` in, same
validate → upload → hash → `ready` output rule, same eval-run row.

1. Registry candidate `product_scene:v1`, same conservative row shape as
   outpaint (`testing`/`research_only`/`internal`/staging-only), with its own
   allowed presets and `input_envelope`.
2. Server-side BFL adapter (`adapters/bfl_product_scene.py`): downloads the
   source asset server-side, uploads to BFL or sends bytes, polls, downloads the
   result, validates and writes the output asset. The browser never sees BFL
   auth and never receives a provider URL.
3. One Modal secret holding the BFL key, bound only to the V6 API app.
4. Spend control: Stage A cap $10 for this provider, tracked against the
   $75–$100 total ceiling already approved.
5. `MODULE_B_ENABLED` ships ON in staging like Module A; isolation stays with
   the registry row and the Lab allow-list.

Test file `tests/test_wp2_product_scene.py` mirrors the WP1 checklist:
rejections, lineage, privacy, output validation, Flux/V5 regression, Studio
invisibility.

## Step 4 — export package for Studio (after both modules pass)

A single document describing the two stable contracts Studio will replicate:
request/response shape, allowed presets and params per workflow, lineage fields,
and the metering rows this deployment writes for `myaccount.brandverita.io`.
No credits or entitlement logic here.

## Open question

Before I write Module B: what should the first BFL capability be —
background replacement from a text scene description, or a fixed set of
server-owned scene presets with no free text? The second is safer to expose and
matches how outpaint was locked down.
