# Brand-consistent image styles: a 3-layer picker

Give people three simple choices instead of a blank text box, so every picture in a campaign looks like it came from the same brand. The wording behind each choice is written once on the image service, so this test app and the Studio app produce identical results.

## What the person sees

```text
Season / occasion        World (brand anchor)      What you're selling
[ Autumn ]  [ Sales ]    [ Coastal terrace ]       [ short line of text ]
                         [ Forest cabin    ]
                         [ Urban loft      ]
Size: 512 · 768 · 1024 · landscape · portrait
[x] Keep the same look   (seed locked, shown, reusable / re-roll)
[ Create image · 2 credits ]
```

- Season and world are tiles, like the "Style" column in the reference screenshot.
- Only the subject line is typed (up to 200 characters, e.g. "a pair of matte black sunglasses with gold accents on folded cream linen").
- No prompt editing: choices plus subject only. The composed wording is never shown or editable, which is what keeps a campaign consistent.
- "Keep the same look" is on by default: the first picture fixes a seed, every later picture in that session reuses it, and a re-roll button gets a new one. The seed is visible and can be typed in to reproduce a picture later.
- The world choice is remembered on the device, so the app reopens on the same brand anchor.

## The three layers

1. **Season / occasion** — mood, time of day, palette, emotional tone. Ships with **Autumn** and **Sales** first; the structure takes Halloween, Christmas, Spring, Summer, Promotion later with no code change beyond adding wording.
2. **World** — location, architecture, surfaces, signature props, lighting behaviour, locked palette. Ships with **Coastal terrace**, **Forest cabin**, **Urban loft**. This block is emitted word-for-word identical on every run of that world — it is the consistency anchor and is never re-worded per request.
3. **Subject** — the typed line, wrapped in fixed framing sentences ("At the center of the frame, …, captured in sharp focus with shallow depth of field").

A fixed quality tail closes every prompt, identical across all combinations except the framing note, which follows the chosen size (landscape / portrait / square).

## Consistency rules built in

- World text and quality tail are constants on the server, covered by a fingerprint, so nobody can drift them per request.
- Seed is locked across a session by default.
- Only Layer 1 and Layer 3 vary between pictures of one campaign.
- Wording changes create a new numbered preset table version rather than silently editing a shipped one, so an older picture can still be traced to the exact wording that made it.

## Technical section

**Image service (Modal V6, `backend/phase2b/`)**

- New `prompt_layers.py`, modelled on `scene_presets.py`: `SEASON_PRESETS`, `WORLD_PRESETS`, `SUBJECT_TEMPLATE`, `QUALITY_TAIL`, `ASPECT_NOTES`, plus `compose(season, world, subject, size)` and `fingerprint(...)` returning `layer_table_version: "prompt-layers-1"`.
- New `GET /v1/prompt-layers` returning keys, labels and short descriptions only — never the instruction text (same rule as `/v1/scene-presets`).
- `POST /v1/generations` for `flux_text_to_image:v2` accepts an optional `inputs.style` object `{ season, world, subject }` as an alternative to `inputs.prompt`. Both present → 400. When `style` is used the server composes the prompt, so no client can inject world wording. Enum values validated against the tables; `subject` limited to 200 chars and rejected if it contains newlines. Composed layer keys + fingerprint are recorded in the job's provenance; the prompt itself continues to be handled as today.
- Registry: adding a server-composed input path changes the input envelope for `flux_text_to_image`. Insert an immutable `flux_text_to_image:v3` (same self-hosted Modal Flux Schnell, same approval basis, staging + production, studio-safe) rather than mutating `v2`; then run `tools/set_config_hash.py flux_text_to_image v3`. `v2` stays active so Studio keeps working through the switch.
- New `backend/phase2b/tests/test_prompt_layers.py`: enum rejection, prompt+style conflict, subject length/newline rejection, byte-identical world block across seasons and subjects, identical quality tail, seed passthrough, catalogue leaks no instruction text.

**This test app (`src/`)**

- `src/lib/promptLayers.ts`: typed client for `GET /v1/prompt-layers`, plus the `style` request shape.
- `src/components/generation/StylePicker.tsx`: season/world tiles, subject field, seed lock, all on light slate/blue tokens with visible focus rings.
- `GenerationForm.tsx` gains a two-mode switch: "Guided" (picker, default) and "Free text" (today's prompt box, kept for research).

**Studio handoff (`studio-export/`)**

- Update `06-image-generation.md` with the `style` request shape, the catalogue endpoint, `v3`, the seed-lock behaviour, and the rule that the app never composes or edits the layer text itself.
- Add a short entry to `07-team-requests.md` for the Studio switch to `v3`.
- `reference-ui/` gains a `StylePicker.tsx` reference component mirroring the Lab one.

**Not in scope:** brand kits, per-account saved worlds (device memory only for now), prompt enhancement, batch generation, and any change to Smart resize or Product scene.

**Roadmap note:** these tasks get added to `roadmap.md` when implementation starts (plan mode edits only this plan file).

**Your steps after approval:** copy the changed backend files into the Modal folder, clear `__pycache__`, deploy, run the new test file, then run the `v3` registry insert and config-hash tool.
