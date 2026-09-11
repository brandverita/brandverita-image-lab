# Milestone — production-ready image service (2026-09-11)

This records the accepted state of the BrandVerita image service on
2026-09-11. All three customer-facing tools are approved, offered to
`app.brandverita.io`, and served by the API deployed at
`https://brandverita--brandverita-api-v6-fastapi-app.modal.run` against the
`comfy-ui` Supabase project.

## The three approved tools

| Tool             | Registry entry            | Runs on                                              | Approval basis                                                                                    | Measured           | Cost per run       | Settings fingerprint |
| ---------------- | ------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------- | ------------------ | ------------------ | -------------------- |
| Generate image   | `flux_text_to_image:v2`   | self-hosted Modal, ComfyUI fork, FLUX.1-schnell      | `commercial_self_hosted_approved` — Apache-2.0 fork, weights under their own permissive licence   | see baseline below | GPU seconds only   | `b99017d423…`        |
| Smart resize     | `outpaint:v3`             | Black Forest Labs hosted `flux-pro-1.0-expand`       | `commercial_hosted` — BFL public API terms, non-EU, rev. 2026-08-04, clause 2b accepted            | within p95 ≤ 90s   | ~$0.05             | `0d5c7737b3…`        |
| Product scene    | `product_scene:v2`        | Black Forest Labs hosted `flux-kontext-pro`          | `commercial_hosted` — same BFL public API terms basis, approved 2026-09-11                         | 16.7s warm         | ~$0.04             | `1fb1bd108b…`        |

All three entries: `status = active`, `registry_visibility = studio_safe`,
`production_enabled = true`, `enabled_for_studio = true`,
`allowed_envs = {staging, production}`. Each is immutable; a change means a new
version, never an edit.

Baseline for Generate image: recorded in `backend/phase2b/wp0-build-manifest.md`
and the Phase 1 manifest; self-hosted, so cost is Modal GPU time only.

## Kept as score-bench entries only

`flux_text_to_image:v1`, `flux_text_to_image:v1-commercial-candidate`,
`outpaint:v1` (self-hosted SD-1.5 inpainting), `outpaint:v2`, and
`product_scene:v1` remain research entries: `internal`, `research_only`,
staging only, not offered to Studio. They exist for quality comparison and must
never be called by a customer-facing client.

## Pinned artefacts behind the milestone

- Generate image worker: `brandverita/ComfyUI` commit
  `34443989e8c56b5bb4a66cf028c834192ab59dd`, tag `v6-flux-prod`
- Research outpaint worker (bench only): upstream `comfyanonymous/ComfyUI`
  commit `3d0003c24c1aec9f0c021dbc70ffb7cd8cf0685c`, tag `v0.3.69`
- Hosted entries carry no file digest; every run records the provider call id

## What is still open at this milestone

- Studio-side disclosures for both BFL-backed tools: flow the FLUX Usage Policy
  into end-user terms, tell users a third party processes the image and may use
  it to improve its models, and prohibit uploads containing identifiable
  personal data. Tracked on the roadmap (Track C); Product scene is switched on
  ahead of this as an explicit business decision on 2026-09-11.
- Modal redeploy of `advanced.py` and `outpaint_geometry.py` from the earlier
  tracks.
- Leaked-password protection and a minimum password length in the production
  project, before the first non-internal account.
- myaccount: credit price per run for each of the three tools.

## Doubling this state as a separate test environment

Decision deferred. What a second environment actually requires:

1. **A separate Supabase project.** All migrations, both private buckets,
   grants, access rules and the retention job replayed. Jobs and assets never
   copy across. Test data and customer data must never share one project — that
   rule is why the duplicate exists at all.
2. **Its own service deployments.** A second API app plus its own workers, each
   named for its environment, with `API_ENVIRONMENT` set accordingly.
3. **Its own provider key.** A separate BFL key in that environment's secret
   store, so spend and rate limits are attributable and revocable per side.
4. **Its own identity configuration.** JWKS issuers for that project, plus any
   extra issuer the Studio app presents on that side.
5. **Its own copies of the three approved entries**, each restricted to a single
   value in `allowed_envs`, each with a freshly computed settings fingerprint.
   Flags are decided explicitly per environment, never inherited.
6. **A decision on which side moves.** Either today's setup keeps serving
   customers and a fresh duplicate becomes the bench, or the reverse. The bench
   side additionally keeps the research entries and the score tables; the
   customer side should not carry them.

Cost of the duplicate is roughly a second Supabase project plus idle Modal
apps; provider spend stays usage-based.
