# Single Test Design: Magazine Promo Card

## Goal
Test one commercially useful editorial layout for product promotions and sales, inspired by the uploaded sample. The result should feel like a polished magazine advertisement rather than an AI-generated poster.

## The design
**Magazine Promo Card**

- A bright, evenly exposed commercial photograph built around the uploaded product.
- The product remains the visual focus and is placed away from the promotional copy.
- A translucent dark placard sits in the lower portion of the layout with restrained rounded corners.
- The placard contains a small campaign label, a bold condensed headline, and an optional short supporting line.
- A small brand or issue label may sit separately near a top corner to reinforce the magazine treatment.
- Typography is added locally after image generation, preserving exact spelling and allowing the clean picture to remain reusable.

## User choices for this test
Keep the interface intentionally narrow:

1. Upload the product picture.
2. Choose the final shape: square, landscape, or tall portrait.
3. Enter:
   - Promotion label, such as “Autumn Sale”
   - Headline, such as “Up to 30% off”
   - Optional supporting line
   - Optional brand label
4. Generate.

The test exposes no lighting, copy-zone, font, placard, or prompt controls. Those are fixed by the design so results can be compared fairly.

## Picture direction
The server-owned image instruction will request:

- High-key commercial lighting with even exposure.
- A clean, contemporary magazine-advertising setting.
- Bright or mid-tone background colours with controlled contrast.
- Clear separation between product and background.
- Reserved lower space for the promotional placard.
- Faithful product shape, colour, label text, orientation, and scale.

This replaces the current dark cover-style treatment for this test only. It does not alter Product Scene or the existing Editorial Layout presets.

## Local layout treatment
The existing typography stage will be extended for this design:

- Draw one translucent charcoal placard within a fixed safe area.
- Use bundled Oswald for the main promotional headline.
- Use Libre Franklin for labels and supporting copy.
- Use light text with automatic fitting and fixed spacing rules.
- Keep all copy inside safe margins and reject copy that cannot fit cleanly.
- Store both outputs: the clean generated picture and the finished promotional layout.

## Test set
Run a small, controlled batch across:

- One dark product.
- One light product.
- One packaged product with visible label text.
- Square, landscape, and tall portrait outputs.
- Short and medium-length headlines.

## What to score
Score each result separately for:

- Product fidelity.
- Exposure and colour quality.
- Magazine-advertising feel.
- Product and copy balance.
- Placard readability.
- Text accuracy and fitting.
- Suitability for a real product promotion.

The design passes when exposure is consistently usable, the product remains recognisable, all text is exact and legible, and the same composition works across the three shapes without manual repair.

## Technical impact
This is a contained extension of the existing Editorial Layout structure:

- Add one server-owned design key and one bright commercial picture instruction.
- Add one placard-based composition path to the local typography module.
- Map the three supported shapes to fixed product and placard regions.
- Add offline layout tests plus a capped provider evaluation batch.
- Keep enum-only requests, fingerprints, private assets, layered output, and staging-only gating unchanged.

No new provider, service, database table, or production integration is required.

## Scope boundary
This test does not publish Editorial Layout, expose it in Studio, add arbitrary design editing, accept free-form provider prompts, change Product Scene, or create additional templates. Those decisions follow only after this single design is evaluated.
