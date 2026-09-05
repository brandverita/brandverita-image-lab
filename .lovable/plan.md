# Compliance finalisation + staging→production split

You confirmed: **all three modules** are commercially approved in intent
(Flux baseline, Outpaint, Product Scene), and the unchecked gates in
`LICENSE_REVIEW.md` are paperwork to back-fill, not blockers. The plan below
does both tracks in sequence: finish the compliance record first, then stand
up the production split it unblocks.

One honest caveat that survives even "all three approved": **Product Scene
dispatches to a hosted third party (BFL)**. A signed BFL commercial agreement
and data-processing review are *external* artefacts, not internal paperwork.
So Flux and Outpaint can go to production in the first cut; Product Scene is
sequenced as a later cut that waits on the executed BFL agreement. This does
not contradict your approval — it just separates "internally approved to
proceed" from "the third-party contract is in place," which the registry gate
enforces separately via `commercial_hosted` + `production_enabled`.

## Verified current state

Staging registry (comfy-ui, `thspgke…`), four rows:

| Row | status | commercial_status | visibility | envs | prod_enabled | studio_enabled |
| --- | --- | --- | --- | --- | --- | --- |
| `flux_text_to_image:v1` | active | pending_review | internal | staging | false | false |
| `flux_text_to_image:v1-commercial-candidate` | draft | pending_review | internal | staging | false | false |
| `outpaint:v1` | testing | research_only | internal | staging | false | false |
| `product_scene:v1` | testing | research_only | internal | staging | false | false |

Dispatch gate (`registry.assert_dispatch_allowed`) refuses unless
`status=active`, env in `allowed_envs`, and for Studio-origin **or**
`production` environment: `commercial_status ∈ {commercial_hosted,
commercial_self_hosted_approved, licensed_self_hosted}` **and**
`production_enabled=true`. Studio *visibility* additionally needs
`registry_visibility=studio_safe`, `enabled_for_studio=true`, non-research.
Registry rows are immutable once active, so every promotion is a **new
version row** with a fresh `config_hash`, never an in-place edit.

Compliance files now in this repo: `LICENSE_REVIEW.md`, `COMPLIANCE.md`,
`SOURCE_OFFER.md`, `THIRD_PARTY_NOTICES.md`, `BUILD.md`. Open gaps:
- `LICENSE_REVIEW.md` header says "Approved" but §2/§4 still mark Outpaint and
  Product Scene **Blocked** and §5.6/§6.4 gate checkboxes are all unchecked.
- `THIRD_PARTY_NOTICES.md` still has `[name]/[SHA]/[license]` placeholder rows.
- §5.3 required public materials (`LICENSE`, `CHANGES.md`, `SBOM.spdx.json`,
  immutable `v6-flux-prod` release tag) belong in the `brandverita/ComfyUI`
  **fork**, not this `generation-test-ui` repo; none are visible there.
- No separate production Supabase project or production Modal apps exist yet.

## Track A — finalise the compliance record

Goal: make `LICENSE_REVIEW.md` internally consistent and promotion-ready, and
move the artefacts that belong in the fork into the fork.

A1. **Reconcile `LICENSE_REVIEW.md`.** Header status stays "Approved", but the
body must agree: set the Outpaint and Product Scene decision rows to the
approved commercial status (Outpaint → `commercial_self_hosted_approved`,
Product Scene → `commercial_hosted`, target only — note the BFL agreement as
the one remaining external dependency). Check the §5.6 and §6.4 gate boxes
that internal review covers; leave the BFL-contract / DPA boxes unchecked and
label them "external — pending BFL execution".

A2. **Fill `THIRD_PARTY_NOTICES.md`.** Replace `[name]/[SHA]/[license]`
placeholders with the real custom-node, Python-package, and checkpoint rows
already pinned in the manifests (`wp1-research-manifest.md`,
`phase-2a-build-manifest.md`, `wp0-build-manifest.md`). Each row: component,
version/commit/SHA256, licence, source URL.

A3. **Map fork artefacts to the fork.** Confirm (do not create from this repo)
that `brandverita/ComfyUI` contains: `LICENSE`, `CHANGES.md` (changes vs
upstream at `344b4398…`), `SOURCE_OFFER.md`, `BUILD.md`, `THIRD_PARTY_NOTICES.md`,
`SBOM.spdx.json`, and the immutable tag `v6-flux-prod` on commit
`344b43989e8c56b5bb4a66cf028c834192ab59dd`. Record the fork commit/tag in
`LICENSE_REVIEW.md` §5.3 as the evidence link. This is a checklist for you to
complete in the fork repo — the plan does not create those files here.

A4. **Pin every artefact with the five-field rule** (source repo URL, immutable
full SHA, exact filename, SHA256, licence reference) inside `LICENSE_REVIEW.md`
§4 for: ComfyUI base (`3d0003c…`, v0.3.69), the fork (`344b4398…`), the
SD-1.5-inpainting checkpoint, and the BFL `flux-kontext-pro` model/API terms.

A5. **Cross-link.** Add a one-line pointer from `COMPLIANCE.md` to the approval
status per module, so the compliance index matches the registry promotion.

## Track B — production split

No new application logic — the code is already environment-parameterised
(`API_ENVIRONMENT`, worker app names via env, provider flags via env, registry
read from whichever Supabase the service-role key points at). This is naming,
configuration, and registry rows.

B1. **Production Supabase project** (new, not `comfy-ui`). Replay into it:
all 13 migrations under `supabase/migrations/`, the private
`generation-assets` and `generation-outputs` buckets, grants, RLS policies, and
the retention job. Assets and job history do **not** migrate — production starts
empty. `comfy-ui` stays the permanent staging/Lab project.

B2. **Production Modal apps** (mirrored by name, secrets mirrored by name with
*different values*):

| Concern | Staging (unchanged) | Production (new) |
| --- | --- | --- |
| API app | `brandverita-api-v6` | `brandverita-api-prod` |
| Flux worker | `comfyui-generation-worker-v6` | `comfyui-generation-worker-prod` |
| Outpaint worker | `comfyui-research-worker-2b` | `comfyui-outpaint-worker-prod` |
| Supabase | `comfy-ui` (thspgke…) | new production project |
| `API_ENVIRONMENT` | `staging` | `production` |

B3. **Production secrets** (Modal Secrets, never copied from staging):
- `brandverita-supabase-prod` — production Supabase URL + service-role key.
- `bfl-production` — distinct BFL key from `bfl-research-2b`.
- `huggingface-secret` — build-time read-only token; reusable as-is.
- `EXTRA_JWT_ISSUER_URLS` — production points at the **Studio** Supabase issuer
  only (`bowhzbhwrflbsefxpucn.supabase.co`); the staging comfy-ui issuer is
  **not** carried across. The production Supabase project's own issuer is the
  primary for its auth.

B4. **Production opening flags** (decided explicitly, not inherited):
`ADVANCED_FRAMEWORK_ENABLED=true`, `OUTPAINT_DISPATCH_ENABLED=true` (once its
row is approved), `HOSTED_PROVIDER_DISPATCH_ENABLED=false` until the BFL
agreement is signed. Flux on by default.

B5. **Production registry v2 rows** (new rows, fresh `config_hash` each):

| Row | status | commercial_status | visibility | envs | prod_enabled | studio_enabled |
| --- | --- | --- | --- | --- | --- | --- |
| `flux_text_to_image:v2` | active | `commercial_self_hosted_approved` | `studio_safe` | `{production}` | true | true |
| `outpaint:v2` | active | `commercial_self_hosted_approved` | `studio_safe` | `{production}` | true | true |
| `product_scene:v2` | active | `commercial_hosted` | `studio_safe` | `{production}` | **false** until BFL agreement | **false** until BFL agreement |

Run `backend/phase2b/tools/set_config_hash.py <key> <version>` against the
**production** Supabase project for each new row. Staging rows stay
research-only and untouched — the Lab keeps its unrestricted surface.

B6. **Studio-token verification.** Production API verifies Studio-issued
tokens via the multi-issuer JWKS path already built (`jwks_auth.py` +
`EXTRA_JWT_ISSUER_URLS`); the production Supabase project's own issuer is
primary. Extra-issuer tokens never hit the comfy-ui REST fallback.

B7. **End-to-end check from a Studio token**: `GET /v1/workflows?origin=studio`
lists Flux + Outpaint (not Product Scene yet), and a dispatch returns 200
instead of 403. `GET /health` reports `environment: production`, production
worker names, and the Studio issuer label.

## Suggested order

1. Track A1–A5 (compliance record consistent + fork artefacts confirmed).
2. B1 production Supabase project (migrations, buckets, grants, RLS, retention).
3. B2–B4 production Modal apps: workers first, then API; verify `/health`.
4. B5 v2 registry rows + config hashes for Flux and Outpaint; leave Product
   Scene `production_enabled=false`.
5. B6–B7 Studio end-to-end against the production API.
6. Product Scene promoted separately once the BFL commercial agreement + DPA
   clear: flip `product_scene:v2` `production_enabled`/`enabled_for_studio` to
   `true` and enable `HOSTED_PROVIDER_DISPATCH_ENABLED`.

## Verification checklist

- [ ] `LICENSE_REVIEW.md` body matches "Approved" header; §5.6/§6.4 internal
      boxes checked; BFL-contract boxes labelled external-pending.
- [ ] `THIRD_PARTY_NOTICES.md` has no `[name]` placeholders.
- [ ] `brandverita/ComfyUI` fork has LICENSE, CHANGES.md, SBOM, tag
      `v6-flux-prod` on `344b4398…`; link recorded in §5.3.
- [ ] Production Supabase project exists; migrations + buckets + RLS applied;
      `comfy-ui` untouched.
- [ ] Production API `/health` shows `environment: production`, production
      worker names, Studio issuer label.
- [ ] `GET /v1/workflows?origin=studio` on production lists Flux + Outpaint.
- [ ] Studio-token dispatch to Flux + Outpaint returns 200; Product Scene
      still 403 `workflow_not_commercially_approved`.
- [ ] Staging registry rows unchanged (still research_only/internal).

## Decisions locked (2026-09-05)

- **Production app names** as proposed in B2: `brandverita-api-prod`,
  `comfyui-generation-worker-prod`, `comfyui-outpaint-worker-prod`.
- **Flux and Outpaint v2 rows are production-only**: `allowed_envs = {production}`.
  Staging keeps its own research rows; the Lab does not exercise the approved
  production versions.
- **Product Scene approval recorded 2026-09-05**, subject to the executed BFL
  commercial agreement and DPA. `product_scene:v2` is created with
  `production_enabled=false`, `enabled_for_studio=false`, and
  `HOSTED_PROVIDER_DISPATCH_ENABLED=false` until those close.

Track A is complete in this repo. Remaining work is Track B, executed against
Modal and the new production Supabase project, plus confirming the fork
artefacts in `brandverita/ComfyUI`.
