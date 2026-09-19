# Module C — Editorial layouts (text-on-image)

Feasibility study and build plan. Nothing is implemented until approved.

## What you asked for

An editorial counterpart to Product scene: the uploaded subject stays exactly as
it is, the surroundings become an editorial picture, generated people are
allowed, and the result is a layout with a headline on it — in banner, square and
tall banner shapes.

## The one honest constraint

Image models do not render reliable text. Asking the picture model for a headline
produces misspelt, unusable type at every quality tier — that is a model
property, not a tuning problem. So the module splits in two:

1. **Picture stage** — the scene is generated with a deliberately empty area
   reserved for copy (a "copy-safe zone"): calm surface, low detail, no subject
   and no face inside it.
2. **Type stage** — the headline is drawn afterwards as real text by the server,
   with a chosen font, size and colour. Perfect spelling, perfect kerning,
   editable later, and exactly reproducible.

This is how every real editorial tool works, and it is the only way to get
publishable type. It also means the headline can be changed without paying for a
new picture.

## Doability verdict on the current stack

The existing stack carries about 80% of this with no new infrastructure:

- Subject-untouched restyling: already proven by Product scene (hosted
  subject-preserving edit model), same adapter shape, same private-asset flow.
- Server-owned preset wording, enum-only requests, config-hash immutability,
  provenance fingerprints, private storage + signed URLs, evaluation scoring:
  all reusable as-is.
- Output size presets, aspect handling and the result/asset contract: reusable.

What genuinely does not exist yet:

- A **typography layer**: fonts, text fitting, line breaking, colour contrast
  check, and composition of type over the picture.
- A **copy-zone model**: where the empty area sits per shape, and a check that
  the generated picture actually left it usable.
- **Tall banner** output presets.

No alternative platform is needed. The one new dependency is a server-side image
compositor for the type stage. Recommendation: keep it in the existing Python
worker image (Pillow, already present for validation, plus bundled fonts) rather
than adding a browser or headless-renderer service — it stays inside the
provider-neutral gateway, stays testable offline, and adds no new vendor.

## What gets built

### 1. Editorial presets (server-owned, new file `editorial_presets.py`)

Enum-only, wording never leaves the server, same discipline as
`scene_presets.py`. Starting set of looks, each written to leave the copy zone
clear:

- Cover shot — single subject, strong key light, deep calm background
- Lifestyle spread — generated people present, candid mid-distance, warm daylight
- Flat-lay — overhead, arranged surface, even light
- Documentary — natural location, cooler light, reportage feel

Plus a people switch per run (`none` / `background_figures` / `foreground_model`)
so the same look can be ordered with or without people. Uploads containing
identifiable people stay prohibited, unchanged.

### 2. Copy-zone geometry

Per output shape, a fixed zone: left third (banner), lower third (square), upper
third (tall banner). The zone is chosen from an enum, never free coordinates. The
instruction text tells the model to keep that region quiet, and after generation
the server measures detail and contrast inside the zone; a zone that came back
too busy is reported so the run can be reordered rather than shipped.

### 3. Type stage

- Headline (required, short limit), optional standfirst, optional small label.
- A small set of server-owned type presets (font, weight, scale, alignment,
  colour pair) — no arbitrary fonts or CSS from the client.
- Automatic contrast check against the pixels behind the text, with an optional
  scrim.
- Two deliverables per run: the clean picture and the typeset layout, so the
  picture can be reused with different copy.

### 4. Output presets

Banner `1600x900`, square `1080x1080`, tall banner `1080x1920` and a quarter-page
tall `800x2000`. Exact pixel sizes only, resized server-side after the provider
call, as Product scene already does.

### 5. Registry, cost and gating

New immutable registry row `editorial_layout:v1`, research/staging only,
`enabled_for_studio` false and `production_enabled` false until it is evaluated
and the disclosure work closes. Per-run cost is one hosted edit call (same order
as Product scene, about $0.04) plus free local typesetting. Spend cap set at the
same shape as Module B's.

### 6. Lab UI + evaluation

A third tab beside Smart resize and Product scene: pick source asset, look,
people option, shape, copy zone, type preset, enter the copy, generate, then
score the result on the existing eval table (subject fidelity, zone usability,
type legibility, overall).

## Sequencing

1. Presets + copy-zone geometry + fingerprints, with offline tests (no spend).
2. Typography layer and composition, offline tests on fixed pictures (no spend).
3. Adapter wiring to the hosted edit model, registry row, capped evaluation run.
4. Lab UI and scoring.
5. Read the scores, pick the winning preset variants, then decide on Studio
   exposure and the disclosure items separately.

## Decisions confirmed (2026-09-19)

- Sizes: the four presets above stand as proposed. Per-run cost is a flat hosted
  call (~$0.04) regardless of pixel size, so no 20% reduction is needed.
- Fonts: open-licence families only (type presets select from bundled open
  fonts; no licensed font files required).
- Output: layered — every run stores the clean picture and the typeset layout as
  separate assets, with the text and type-preset settings recorded as metadata
  so copy can be re-typeset later without re-generating the picture.

## Out of scope

Studio exposure, production dispatch, billing/credits, free-text prompts into
this module, uploads containing people, multi-page layouts, and any change to the
existing three shipped tools.
