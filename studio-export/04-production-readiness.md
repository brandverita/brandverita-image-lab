# 04 — Production readiness

Nothing here is a Studio code task. This is what must be cleared before Studio
can run either feature for customers. Order matters: 1–4 are hard blockers.

## 1. Registry gating (blocker)

Both rows today:

| Field | `outpaint:v1` | `product_scene:v1` |
| --- | --- | --- |
| `status` | `testing` | `testing` |
| `commercial_status` | `research_only` | `research_only` |
| `registry_visibility` | `internal` | `internal` |
| `allowed_envs` | `{staging}` | `{staging}` |
| `production_enabled` | false | false |
| `enabled_for_studio` | false | false |

The server refuses Studio-origin or production dispatch unless a row is both
commercially approved **and** `production_enabled`. Flipping flags does not
bypass this — the registry is the gate. Each promotion is a new registry version
with a fresh config hash, not an in-place edit of an active row.

## 2. Commercial approval, per module (blocker)

- **Smart Resize / Outpaint** — self-hosted SD-1.5-inpainting checkpoint
  (`stable-diffusion-v1-5/stable-diffusion-inpainting`, pinned commit and
  SHA256). Needs a licence review concluding commercial self-hosted use is
  approved before the row moves off `research_only`.
- **Product Background / Scene** — hosted third-party provider (Black Forest
  Labs `flux-kontext-pro`). Needs a commercial agreement, a data-handling /
  customer-image review, and confirmation of output rights, because customer
  images leave the deployment.

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

| Metric | Outpaint | Product scene |
| --- | --- | --- |
| Accepted run | 44.7s end to end | 16.7s warm (first call 162.7s, provider warm-up) |
| Cost | self-hosted GPU seconds | ~$0.04 per image (recorded estimate) |
| Target | p95 ≤ 90s | p95 ≤ 90s |

Both samples sit inside the target, but p95 confidence needs more runs over time.
Collect a larger sample before publishing an SLA-style promise.

## 7. Known limitation to state in Studio's own review

Outpaint composites the original region back and verifies it byte-exactly — the
user's pixels are provably unchanged. Product scene re-renders the whole frame,
so there is no byte-exact region: provenance records
`subject_preserved: "unverified"` and fidelity is judged by human review. Studio
copy must not claim the product is untouched, and a human check before customer
publication is the expected workflow.
