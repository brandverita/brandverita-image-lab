# Route Studio Smart Resize to the hosted outpaint candidate

## Confirmed diagnosis

- The latest Smart Resize job at **2026-09-07 07:15 UTC** is recorded as `outpaint:v1` with provider `modal_research_2b`.
- Its output provenance identifies the old self-hosted SD-1.5 inpainting worker and checkpoint. It contains no BFL prompt-mode fields.
- The exported Studio client currently hardcodes `workflow_version: "v1"` for every transformation. This explains why deploying the updated BFL adapter did not change the result.
- For a square source placed into the selected **1600×900** preset, the original is correctly scaled to **900×900** and centred. Only the 350-pixel side bands are generated. Keeping the centre unchanged is intentional; inventing unrelated faces or objects in those side bands is not.
- No free-text instruction should be added to Studio. The BFL instruction remains server-owned.

## Fix

1. **Select the workflow version per feature**
   - Send `outpaint:v2` for Smart Resize.
   - Keep Product Scene on `product_scene:v1`.
   - Remove the shared hardcoded `workflow_version: "v1"` from the request builder and use the module-specific constants instead.

2. **Make result identity version-aware**
   - Include the selected workflow version in the transformation context key so a result from `outpaint:v1` cannot remain visible when `outpaint:v2` is selected.
   - Keep the existing source-image and run-ID stale-response protections.

3. **Align the Studio export contract**
   - Update the typed constants, API examples, catalogs, integration guide, and package summary so Smart Resize consistently names `outpaint:v2` / `bfl_outpaint`.
   - Retain `outpaint:v1` only as an internal comparison path; do not expose a version selector in Studio.

4. **Verify the first real hosted run**
   - Repeat the same seal image with the same 1600×900, symmetric, centred presets.
   - Confirm the new job row records:
     - `workflow_id = outpaint`
     - `workflow_version = v2`
     - `provider = bfl_outpaint`
   - Confirm output provenance records `prompt_mode = guided`, the instruction hash/length, source-region verification, and the expected 350-pixel left/right expansion.
   - Visually check that the generated bands continue the water, horizon, sky, lighting, and grain without unrelated subjects or visible seams.

5. **Run the bare comparison only if guided still fails**
   - Set the server-side Modal API image environment value `OUTPAINT_V2_PROMPT_MODE=bare`, redeploy `api.py`, and repeat the identical test.
   - Confirm provenance says `prompt_mode = bare` and `instruction_chars = 0`.
   - Compare guided and bare using the same source, preset, direction, and anchor.

## Acceptance and stop criteria

- Accept a mode only if the original region remains verified and both generated bands are coherent continuations without unrelated people, objects, duplication, or obvious seams.
- If guided and bare both fail, stop treating prompt wording as the cause. Keep `outpaint:v2` staging-only and evaluate the hosted expand model/endpoint parameters or a different commercially suitable hosted provider; do not add free-text UI controls or promote the workflow.

## Unchanged safeguards

Private assets, server-owned geometry and instruction, enum-only Studio controls, BFL credentials confined to the hosted background function, original-pixel compositing and integrity verification, cleanup, metering, staging-only registry status, and production/Studio registry gates remain unchanged.
