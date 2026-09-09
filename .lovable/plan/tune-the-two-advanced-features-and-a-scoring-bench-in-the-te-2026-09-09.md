# Tune the two advanced features, and a scoring bench in the test app

Three pieces of work: a brighter set of Product scene options you can compare,
a Smart resize test bench in the staging app so the extension settings can be
tuned on BFL, and a written plan for adding image generation to the main app.

## 1. Product scene: brighter options, chosen by score

The current four scene texts read slightly dark. Rather than guessing a new
wording, each scene keeps its present text as `v1` and gains a brighter `v2`
variant (lifted exposure, brighter key light, cleaner mid-tones, softer
shadow). Variants stay server-owned: the app only ever sends a short name, no
free text. Which variant runs is chosen per test run in the staging app; the
main app keeps running the current default until you pick a winner.

## 2. Smart resize: tunable test bench on the staging app

Smart resize stays on BFL ($0.05). The reason new areas get invented content is
the generator's freedom, so the staging app gets an internal panel exposing the
few settings that control it, one run at a time:

- extension instruction: brighter/positive continuation text, or none at all
- how strongly the picture is followed (the equivalent of the "no imagination"
  setting that fixed this on the other provider) plus refinement effort
- picture, target size, which side to extend, and where the original sits

All of these are validated against fixed server-side lists — the panel picks
from options, it never posts raw text or numbers straight to the provider. Your
original pixels keep being pasted back and checked byte-for-byte, so a run that
alters the original still fails.

## 3. Scoring, in the staging app

Each finished run in the new panel shows the picture plus a small score card:
overall 1-5, a "did it invent anything" yes/no, brightness 1-5, and a note.
Scores are saved against the run so a table can be read back per feature and
per variant: run, settings used, cost, latency, average score. That table is
what selects the Product scene wording and the Smart resize settings.

## 4. Image generation in the main app (plan only, no code this round)

Written hand-off in the export package: the existing text-to-image workflow is
already live and needs no backend change. The main app needs the same client
call it already uses for the other two features with the text-to-image
workflow, a prompt box with the existing limits, the fixed size list, the same
2-second polling, and the same private-link result handling. Also documented:
the settings to add, what is deliberately not exposed (no custom workflows, no
raw settings), and the checks to run before it goes live.

## Technical detail

- `backend/phase2b/scene_presets.py`: add `SCENE_PRESET_VARIANTS`
  (`{scene_direction: {v1, v2}}`) with brighter v2 text; `build_instruction`
  gains a `variant` argument defaulting to `v1`; `fingerprint()` records
  variant id + instruction sha256. Variant is accepted only from the internal
  Lab origin allow-list, never from Studio; default path is unchanged.
- `backend/phase2b/adapters/bfl_product_scene.py`: pass the variant through to
  `build_instruction`, record it in provenance and the eval run.
- `backend/phase2b/adapters/bfl_outpaint.py`: promote the BFL request knobs to
  server constants with enum-bounded overrides (`prompt_mode`:
  `guided|bare|bright`, plus `guidance` and `steps` from a fixed allow-list of
  values). Defaults unchanged; overrides only via the Lab-origin research
  params. `prompt_upsampling` stays `false`.
- `backend/phase2b/advanced.py`: extend the research-params validator with the
  new enum keys, gated on the internal allow-list; free text stays in
  `FORBIDDEN_KEYS`.
- Migration in `comfy-ui` staging: `transformation_eval_scores`
  (`eval_run_id`, `job_id`, `user_id`, `overall`, `invented_content`,
  `brightness`, `notes`, `created_at`), owner-scoped RLS SELECT/INSERT,
  explicit GRANTs; plus `variant_id` / `provider_params` JSON on
  `transformation_eval_runs` if absent.
- API: `POST /v1/generations/{job_id}/score` (owner-checked) and
  `GET /v1/eval-runs?module=` returning the comparison table. Both internal
  origin only.
- Frontend `src/`: new `TransformationLabPanel` (Smart resize + Product scene,
  enum controls, variant/settings selectors), `ScoreCard`, `EvalTable`, wired
  into `src/routes/index.tsx` behind the existing access check; API calls go in
  `src/lib/advancedApi.ts` alongside `generationApi.ts`.
- `studio-export/`: new `06-image-generation.md` hand-off; no client code
  changes this round.
- Registry, `outpaint:v2` / `product_scene:v1` config hashes, Studio
  enablement, and production stay untouched — variants live behind the
  research-params gate, so no re-hash is required.

## What you will need to do

Run the staging migration, copy the changed backend files to the Modal V6 app,
clear `__pycache__`, redeploy, then run a handful of Smart resize and Product
scene tests in the staging app and score them. I read the table back and
recommend the defaults to promote.

## Out of scope

No Pixelcut wiring, no Studio UI change, no production deploy, no billing, no
free-text prompt anywhere.
