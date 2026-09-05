# Removing the remaining blocks, and splitting staging from production

Two answers, then the work each implies.

## Verified current state

All four registry rows today (read from the staging registry):

| Row | status | commercial_status | visibility | envs | production_enabled | enabled_for_studio |
| --- | --- | --- | --- | --- | --- | --- |
| `flux_text_to_image:v1` | active | pending_review | internal | staging | false | false |
| `flux_text_to_image:v1-commercial-candidate` | draft | pending_review | internal | staging | false | false |
| `outpaint:v1` | testing | research_only | internal | staging | false | false |
| `product_scene:v1` | testing | research_only | internal | staging | false | false |

There is no `LICENSE_REVIEW.md` in this repository yet — it exists on your side. It needs to land here (or be linked by commit hash) because the registry promotion references it as the approval evidence.

## Question 1 — what "removing all blocks" actually means

The blocks are not one switch. Dispatch is refused by `registry.assert_dispatch_allowed` unless *every* one of these is true, and an internal-Pro-only audience does not bypass any of them:

```text
status == active
current environment in allowed_envs
if origin == studio OR environment == production:
    commercial_status in {commercial_hosted, commercial_self_hosted_approved, licensed_self_hosted}
    production_enabled == true
```
and, for Studio to even *see* a workflow, `registry_visibility == studio_safe`, `enabled_for_studio == true`, and it must not be `research_only`.

Registry rows are immutable once active, so this is not an UPDATE. Each promotion is a **new version row** (`outpaint:v2`, `product_scene:v2`, `flux_text_to_image:v2`) with a freshly computed `config_hash`, carrying the approved flags. The old research rows stay as-is for provenance.

Per module, what the licence review must actually conclude:

- **Flux baseline** — self-hosted FLUX.1-schnell, Apache-2.0. Straightforward: `pending_review -> commercial_self_hosted_approved`.
- **Outpaint (Module A)** — self-hosted SD-1.5-inpainting, pinned commit + SHA256. Needs the review to state commercial self-hosted use is approved: `research_only -> commercial_self_hosted_approved`.
- **Product scene (Module B)** — hosted third party (BFL `flux-kontext-pro`). A licence review alone is **not** sufficient here: customer images leave the deployment, so this needs a commercial agreement with BFL, a data-handling review, and confirmation of output rights. Target `commercial_hosted`. Expect this one to clear later than the other two, and it can ship later without holding them back.

So the removal sequence is:

1. Land `LICENSE_REVIEW.md` in this repo, one section per artefact, each naming source repo, immutable SHA, filename, SHA256, licence, and conclusion.
2. Stand up the production Supabase project and production API deployment (question 2) — `production_enabled = true` is meaningless until a production environment exists to be enabled *in*.
3. Insert v2 registry rows in the production registry with `status=active`, `commercial_status` per the table above, `registry_visibility=studio_safe`, `allowed_envs={production}` (add `staging` only if you also want them in the Lab), `production_enabled=true`, `enabled_for_studio=true`.
4. Run `tools/set_config_hash.py` for each new row.
5. Verify from a Studio-issued token: `GET /v1/workflows?origin=studio` now lists them, and a dispatch returns 200 instead of 403.

Staging rows are left untouched and stay research-only, so the Lab keeps its unrestricted experimentation surface.

## Question 2 — a separate production Modal app

Yes, it makes sense, and it is required rather than optional: the readiness document already treats "production Supabase project" and "production deployment" as hard blockers, and the `comfy-ui` project must never hold customer data.

Complexity: **moderate and mostly mechanical** — no new application logic. The code is already environment-parameterised (`API_ENVIRONMENT`, worker app names via env, provider flags via env, registry read from whichever Supabase the secret points at). What changes is naming and configuration, in five places:

| Concern | Staging (unchanged) | Production (new) |
| --- | --- | --- |
| API app | `brandverita-api-v6` | `brandverita-api-prod` |
| Flux worker | `comfyui-generation-worker-v6` | `comfyui-generation-worker-prod` |
| Research/outpaint worker | `comfyui-research-worker-2b` | `comfyui-outpaint-worker-prod` |
| Supabase | `comfy-ui` (thspgke…) | new production project |
| `API_ENVIRONMENT` | `staging` | `production` |

Secrets are **mirrored by name, not by value** — a separate Modal Secret per environment holding a *different* credential:

- `brandverita-supabase-prod` — production Supabase URL + service-role key.
- `bfl-production` — a distinct BFL key from `bfl-research-2b`, so staging spend and production spend are separately capped and separately revocable.
- `huggingface-secret` — build-time only; can be reused as-is (read-only token, no data flows through it).
- `EXTRA_JWT_ISSUER_URLS` — production points at Studio's Supabase issuer only; the staging comfy-ui issuer is **not** carried across.

Never copy a staging key into production. Same names, different values, is the whole discipline.

Also replayed into the production Supabase project: all migrations, the private `generation-assets` and `generation-outputs` buckets, grants, RLS policies, the retention job, and the registry v2 rows. Assets and job history do **not** migrate — production starts empty.

Flags in production are decided explicitly, not inherited. A sane opening posture: Flux on, outpaint on once its row is approved, `HOSTED_PROVIDER_DISPATCH_ENABLED=false` until the BFL agreement is signed.

## Suggested order

1. `LICENSE_REVIEW.md` into the repo (unblocks Flux + outpaint approval).
2. Production Supabase project: migrations, buckets, grants, RLS, retention.
3. Production Modal apps: workers first, then API; verify `/health` reports `environment: production` and the production worker names.
4. v2 registry rows + config hashes for Flux and outpaint; leave product scene research-only.
5. Studio end-to-end check against the production API with a Studio token.
6. Product scene promoted separately once the BFL commercial and data-handling review clears.

## What I need from you

- `LICENSE_REVIEW.md` (or the go-ahead to draft its skeleton here for you to fill).
- Confirmation of the production app names above, or your own naming.
- Whether product scene should be excluded from the first production cut, as recommended.
