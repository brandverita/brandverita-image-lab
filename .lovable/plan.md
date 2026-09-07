# Two fixes: usable Smart resize, and a result box that never shows the old picture

## What the tests show

Product scene is working well. Two separate problems remain.

**1. Smart resize quality.** Today the extension is created by a small
self-hosted model that was trained to imagine 512-pixel-sized content. When it
is asked to fill a wide band beside a picture it repeats objects, invents
unrelated subjects, leaves visible joins, or produces flat grey. Screenshots
four, five and six are all that same limitation, not a bug — tuning it can
reduce seams but cannot make it good. So Smart resize moves to the same outside
image service already used by Product scene, which has a dedicated
"extend the picture" capability.

**2. Stale result.** The result box kept the previous finished picture after a
new source picture was chosen, and "Refresh link" renewed that same old
picture. The shared result state is not tied to the source picture or to the
job it belongs to, so it survives a source change until a new run finishes.
Screenshot four is likely this too: an older run's extension displayed against
the newly chosen sunset.

## Part 1 — Smart resize on the hosted service

- Add a second Smart resize provider that calls the outside service's
  extend-the-picture endpoint, with the amount to add on each side computed
  from the chosen output size and the "where the new space goes" / "where your
  image sits" options exactly as today.
- Everything protective stays: the picture is sent from our side only (never
  from the browser), the provider credential never leaves the server, the
  result is fetched server-side, normalised to the exact chosen size, checked,
  stored privately, and **your original pixels are pasted back over the result
  and verified byte-for-byte** — the same guarantee as now.
- Cost is recorded per run (about $0.05 per picture) against the existing
  research spend cap; the current self-hosted path stays in place, switched
  off, so it remains available.
- Same disclosure that already applies to Product scene applies here: the
  picture is processed by an outside service.

## Part 2 — Result box can never show a stale picture

In the shared package the Studio team uses:

- The finished picture is stored together with the run it came from, and the
  view only shows it when that run is the current one.
- Choosing a different source picture, or switching between Smart resize and
  Product scene, clears the result immediately.
- "Refresh link" only ever renews the link for the current run, and is hidden
  when there is no current run.
- The reference panel is updated to match, so Studio can adopt it directly.

## Technical detail

- New `backend/phase2b/adapters/bfl_outpaint.py` calling
  `POST /v1/flux-pro-1.0-expand` (top/bottom/left/right pixel amounts, server
  preset instruction only, base64 input, bounded poll, server-side fetch),
  reusing `advanced.acquire_source_bytes`, `write_ready_output`,
  `write_eval_run`, the `bfl-research-2b` secret and the existing cleanup and
  gate order.
- `outpaint_geometry.plan` supplies the per-side pixel amounts;
  `composite_and_verify` and `pixel_digest` are reused unchanged so
  `source_region_verified` is still recorded true/false per run.
- Registry: new immutable `outpaint:v2` row, provider `bfl_outpaint`,
  status `testing`, `commercial_status research_only`, internal visibility,
  `allowed_envs = {staging}`, Studio and production disabled; selection by
  workflow version, so `outpaint:v1` is untouched.
- Studio export: `useTransformation` keys `resultUrl` to `job.job_id`, exposes
  a `sourceKey` so a source/module change resets state, and
  `refreshResultUrl` no-ops unless the current job is complete;
  `TransformationPanel.tsx` / `ResultPane.tsx` updated accordingly, plus a note
  in `03-integration-guide.md`.
- Docs: `module-a.md`, `LICENSE_REVIEW.md`, `COMPLIANCE.md`,
  `THIRD_PARTY_NOTICES.md`, `roadmap.md` record the hosted basis for Smart
  resize (same non-EU public terms and clause 2b acceptance already recorded).

## What you will need to do

Deploy the updated backend files to the Modal V6 app (clear `__pycache__`,
`modal deploy api.py`), run the new registry insert, then re-run one Smart
resize at 1200 x 627 and one Product scene. Studio pulls the updated export
files for the stale-result fix.

## Out of scope

No production deployment, no Studio-side billing, no change to Flux
text-to-image, no new provider beyond the one already in use.
