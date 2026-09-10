# Studio export package — Smart Resize / Outpaint + Product Scene

Handover package for the BrandVerita Studio team. It contains everything needed
to integrate the two image-transformation features that were built and accepted
in the isolated staging Generation Platform:

| Feature                               | Registry workflow                     | Status today (2026-09-10)      |
| ------------------------------------- | ------------------------------------- | ------------------------------ |
| Smart Resize / Outpaint (Module A)    | `outpaint:v3` (`bfl_outpaint`)        | approved, offered to Studio    |
| Generate image (text to image)        | `flux_text_to_image:v2` (self-hosted) | approved, offered to Studio    |
| Product Background / Scene (Module B) | `product_scene:v1`                    | research only, not offered yet |

Smart resize and Generate image are now `studio_safe`, commercially approved and
enabled for Studio, so `GET /v1/workflows?origin=studio` returns them. The older
`outpaint:v1` / `outpaint:v2` rows and `product_scene:v1` remain internal
research rows for the score bench — Studio must never call them. Team-by-team
actions still open are listed in `07-team-requests.md`.

## Read in this order

| File                         | What it is for                                                                          |
| ---------------------------- | --------------------------------------------------------------------------------------- |
| `01-contract.md`             | The API surface: endpoints, exact request bodies, responses, error codes, gating rules. |
| `02-catalogs.md`             | The option catalogs (enums + labels) and the output presets for each feature.           |
| `03-integration-guide.md`    | Step-by-step wiring, using the code in `client/`.                                       |
| `04-production-readiness.md` | Everything blocking customer use, in order.                                             |
| `05-security-boundaries.md`  | Hard rules for the Studio client.                                                       |

## Code

| Path                                   | What it is                                                                      |
| -------------------------------------- | ------------------------------------------------------------------------------- |
| `client/types.ts`                      | Request, response, asset and catalog types.                                     |
| `client/generationClient.ts`           | Dependency-free typed client: assets, catalogs, submit, poll, fresh result URL. |
| `client/useTransformation.ts`          | React hook: submit, 2s polling, terminal-state halt, timeout, retry.            |
| `reference-ui/TransformationPanel.tsx` | Reference two-pane screen for both features.                                    |
| `reference-ui/SourceAssetPicker.tsx`   | Input image upload/selection pane.                                              |
| `reference-ui/OptionControls.tsx`      | Enum-only controls (no free text anywhere).                                     |
| `reference-ui/ResultPane.tsx`          | Result preview, download, empty/loading/error states.                           |

The code is copy-in reference material: plain TypeScript and React with Tailwind
class names, no imports from this repository, no Supabase coupling. The client
takes a base URL and an async token getter, so Studio keeps its own session
handling.

## Two invariants behind the whole design

1. **Enums only.** A client can never send prompt text, geometry, a mask, a URL
   or workflow JSON. Every instruction that reaches a model is server-owned.
   Anything outside the allow-list is refused before storage or a provider is
   touched.
2. **Private assets, signed reads.** Images move by asset ID. The browser only
   ever receives short-lived signed URLs, issued after a server-side ownership
   check. Storage paths and provider credentials never leave the server.

Studio must not weaken either one; both are enforced server-side, so attempting
to is simply a rejected request.
