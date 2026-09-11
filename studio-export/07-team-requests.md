# 07 — Open requests, by team (2026-09-10)

State of the image service after today's change, in the `comfy-ui` staging
project that `https://brandverita--brandverita-api-v6-fastapi-app.modal.run`
serves:

| Registry row                                                              | Provider                       | Approved                               | Offered to Studio     |
| ------------------------------------------------------------------------- | ------------------------------ | -------------------------------------- | --------------------- |
| `flux_text_to_image:v2`                                                   | self-hosted Modal Flux Schnell | `commercial_self_hosted_approved`      | yes                   |
| `outpaint:v3`                                                             | BFL `flux-pro-1.0-expand`      | `commercial_hosted` (BFL public terms) | yes                   |
| `product_scene:v2`                                                        | BFL `flux-kontext-pro`         | `commercial_hosted` (BFL public terms) | yes (new, 2026-09-11) |
| `flux_text_to_image:v1`, `outpaint:v1`, `outpaint:v2`, `product_scene:v1` | —                              | research                               | no — score bench only |

All three offered rows are `status = active`, `registry_visibility =
studio_safe`, `production_enabled = true`, `enabled_for_studio = true`,
`allowed_envs = {staging, production}`, each with its own config fingerprint.

---

## Request to the Studio team (`app.brandverita.io`)

1. **Generate image — nothing gated on us any more.** `GET
/v1/workflows?origin=studio` now returns `flux_text_to_image`. Show the entry
   point when that key is present, exactly as the four-gate list in
   `IMAGE-STUDIO.md` already does for `outpaint` / `product_scene`. Add the
   module mapping `image_generation` → `flux_text_to_image`.
2. **Send the version explicitly**: `workflow_id: "flux_text_to_image"`,
   `workflow_version: "v2"`. The legacy alias `flux-schnell-txt2img-v1` resolves
   to the internal research row and a Studio-origin call to it is refused.
   No source image may be attached to this workflow.
3. **Smart resize — switch the version to `v3`.** Same endpoint, same request
   shape, same presets (`1200x627`, `1600x900`) and the same direction/anchor
   enums; only `workflow_version` changes from `v2` to `v3`. `client/types.ts`
   in this package is already updated.
4. **Provider choice is ours, not yours.** Pixelcut vs BFL is decided by which
   registry row the Smart resize call resolves to. To move Studio off Pixelcut,
   point Smart resize at this API's `outpaint:v3` and retire the Pixelcut path;
   no per-provider option should ever reach the browser.
5. **`POST /v1/generations` needs no origin** — not in the body, not as a query
   parameter, not as a header. The endpoint does not read one; approval is
   enforced by the registry row itself. `origin=studio` is only used on `GET
/v1/workflows` for discovery.
6. **Product scene — switch it on.** As of 2026-09-11 it has an approved,
   `studio_safe` row: send `workflow_id: "product_scene"`,
   `workflow_version: "v2"`. Same request shape, same server-owned scene presets,
   same provider as the wiring you already have; only the version changes from
   `v1`. It now appears in the Studio-origin discovery list, so the entitlement
   fallback is no longer needed. `v1` must not be called — it is the research
   row. The Track C disclosures below are now due for this tool in the same way
   as for Smart resize.
7. **UI for Generate image**: prompt box with character count (2,000 max),
   optional negative box (1,000 max), size dropdown restricted to `512x512`,
   `768x768`, `1024x1024`, `1280x1024`, `1024x1280`, optional seed. Reuse the
   existing polling and result handling; see `06-image-generation.md`.

## Request to the myaccount team (`myaccount.brandverita.io`)

1. **Generate image needs no change** — `image_generation` is already in the
   granted list, and the image service now offers the workflow. Please confirm a
   real Pro handoff still lists it after your redeploy.
2. **Set the Smart resize credit price against the BFL cost.** Our per-run
   provider cost on `outpaint:v3` is about $0.05, against about $0.10 on
   Pixelcut. If `smart_resize` was priced on the Pixelcut cost, it can come
   down.
3. **Confirm the key mapping in the contract doc**, so all three sides agree:

   | myaccount tool key                                               | Studio module         | image service registry key |
   | ---------------------------------------------------------------- | --------------------- | -------------------------- |
   | `image_generation`                                               | Generate image        | `flux_text_to_image:v2`    |
   | `smart_resize`                                                   | Smart resize          | `outpaint:v3`              |
   | `product_scene`                                                  | Product scene         | `product_scene:v2`         |
   | `try_on`, `background_removal`, `upscale`, `generate_background` | Pixelcut-backed tools | not served by this API     |

   The last row matters: those four tools do not exist in our registry, so a
   Studio discovery call will never list them and they must stay gated on
   entitlements alone.

4. **Tell us the credit price per run for each tool we serve**, so our metering
   rows carry the same figure. We record usage only; we never enforce limits.

## Track C disclosures — still open, now due for both BFL tools

Product scene was promoted on 2026-09-11 as an explicit business decision rather
than waiting on these; they remain owed. They apply to **both** BFL-backed tools
(`outpaint:v3` and `product_scene:v2`), since each sends the customer's image to
Black Forest Labs:

1. Flow the FLUX Usage Policy into Studio's end-user terms and AUP.
2. Tell users, at the point of use, that a third party processes the image and
   may use it to improve its models (BFL public terms, clause 2b, accepted as a
   business risk on 2026-09-06).
3. Prohibit uploads containing identifiable personal data for these two tools.

Generate image is self-hosted and carries none of these.

## Still on our side

- Separate production Supabase project, workers and API (`brandverita-api-prod`,
  `comfyui-generation-worker-prod`, `comfyui-outpaint-worker-prod`). Until then
  both new rows are also allowed in `staging`, which is the environment Studio
  currently calls.
- Redeploy of the Modal V6 app is **not** required for this change: the registry
  is read from the database with a 60-second cache.
