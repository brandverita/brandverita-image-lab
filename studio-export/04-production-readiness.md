# 04 — Production readiness

Nothing here is a Studio code task. This is what must be cleared before Studio
can run either feature for customers. Order matters: 1–4 are hard blockers.

## 1. Registry gating (cleared 2026-09-11)

The Studio-facing rows today:

| Field                 | `outpaint:v3`          | `product_scene:v2`     |
| --------------------- | ---------------------- | ---------------------- |
| `status`              | `active`               | `active`               |
| `commercial_status`   | `commercial_hosted`    | `commercial_hosted`    |
| `registry_visibility` | `studio_safe`          | `studio_safe`          |
| `allowed_envs`        | `{staging,production}` | `{staging,production}` |
| `production_enabled`  | true                   | true                   |
| `enabled_for_studio`  | true                   | true                   |

`outpaint:v2` and `product_scene:v1` stay `testing` / `research_only` /
`internal` / staging-only as score-bench rows.


The server refuses Studio-origin or production dispatch unless a row is both
commercially approved **and** `production_enabled`. Flipping flags does not
bypass this — the registry is the gate. Each promotion is a new registry version
with a fresh config hash, not an in-place edit of an active row.

## 2. Commercial approval, per module (blocker)

- **Smart Resize / Outpaint** — hosted BFL `flux-pro-1.0-expand` through the
  public API. It uses the same accepted public-terms basis and Studio-side
  disclosure/acceptable-use obligations described below for Product Scene.
- **Product Background / Scene** — hosted third-party provider (Black Forest
  Labs `flux-kontext-pro`). Legal basis settled 2026-09-06 on BFL's **public**
  Developer Terms of Service + FLUX API Service Terms (rev. 2026-08-04,
  non-EU versions): commercial use of API outputs is expressly permitted and
  no bespoke agreement, DPA, or weight licence will be sought. Accepted with
  the terms: BFL's clause 2b licence to Inputs/Outputs **including model
  training** (business-risk acceptance, to be disclosed to Studio users).
  Promoted to a Studio-facing row (`product_scene:v2`) on 2026-09-11. Studio
  still owes, and must complete: flowing the FLUX Usage Policy down into its
  end-user terms, disclosing third-party processing/training use in its UX,
  and prohibiting uploads containing identifiable personal data for this module.

## 3. Production Supabase project (blocker)

The `comfy-ui` project is the permanent staging/Lab project and must never hold
customer data. A dedicated production project is required, with migrations,
private buckets, grants, RLS policies and the retention job replayed there.
Assets and jobs do not migrate across.

## 4. Production deployment (blocker)

- Its own API deployment and provider credential (a separate provider key, held
  in the platform secret store only).
- Its own flags, decided explicitly rather than inherited from staging —
  including whether hosted-provider dispatch is on at all.
- Its own JWKS/identity configuration for the production Supabase project.

## 5. Metering handoff

This platform records usage only: a per-run evaluation/metering row plus the
usage ledger. It never enforces limits. Credits, plan allowance and user
privileges stay with `myaccount.brandverita.io`. Before launch, agree:

- which recorded fields myaccount consumes (module, provider, output preset,
  latency, estimated cost, job and asset IDs);
- where the pre-flight allowance check happens — Studio must call myaccount
  before submitting, because the Generation API will not refuse on credit
  grounds;
- how a failed job is treated for billing (no charge on `failed`).

## 6. Evidence to carry into the launch review

| Metric       | Outpaint                             | Product scene                                    |
| ------------ | ------------------------------------ | ------------------------------------------------ |
| Accepted run | Hosted v2 evaluation pending         | 16.7s warm (first call 162.7s, provider warm-up) |
| Cost         | ~$0.05 per image (recorded estimate) | ~$0.04 per image (recorded estimate)             |
| Target       | p95 ≤ 90s                            | p95 ≤ 90s                                        |

Product Scene's warm sample sits inside the target. Hosted outpaint v2 still
needs its first correctly routed quality/latency run, and both modules need a
larger sample before publishing an SLA-style promise.

## 7. Known limitation to state in Studio's own review

Outpaint composites the original region back and verifies it byte-exactly — the
user's pixels are provably unchanged. Product scene re-renders the whole frame,
so there is no byte-exact region: provenance records
`subject_preserved: "unverified"` and fidelity is judged by human review. Studio
copy must not claim the product is untouched, and a human check before customer
publication is the expected workflow.
