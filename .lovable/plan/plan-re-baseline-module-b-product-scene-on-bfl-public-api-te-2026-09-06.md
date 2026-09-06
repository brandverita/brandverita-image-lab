# Plan — Re-baseline Module B (Product Scene) on BFL public API terms

Decision recorded 2026-09-06: BrandVerita will NOT pursue a bespoke BFL
commercial agreement or DPA. Module B's legal basis must rest entirely on
BFL's publicly offered terms. This plan records what those terms actually
say (verified 2026-09-06 against bfl.ai/legal), what they change, and what
must be documented before `product_scene:v2` can ever be promoted.

## 1. What the public terms grant (verified against the live documents)

Sources read in full:
- Developer Terms of Service (bfl.ai/legal/developer-terms-of-service, rev. 2026-08-04)
- FLUX API Service Terms (bfl.ai/legal/flux-api-service-terms, rev. 2026-08-04)
- BFL help center: "Can I use the API for a commercial application?" — "Yes. All images generated through the BFL API include full commercial usage rights."

Good news:
- Commercial use of API outputs is explicitly permitted under the public terms. No weight license, no tier purchase, no sales contact needed. The "license FLUX weights and self-host" tiers are irrelevant to us: we never host Kontext weights.
- Studio as a "Developer Application" with End Users is the intended use case — integrating the FLUX API so end users interface with the models inside our product is exactly what the license to the API allows.

Hard conditions we now accept by using the API:
- **Clause 2b (input/output license):** we grant BFL a perpetual, irrevocable, sublicensable license to use Inputs AND Outputs, *including to train and improve their models*. Customer product images sent to Kontext may be used for BFL training. A bespoke DPA would have removed this; the public terms do not. "Zero data retention" is an Enterprise-tier feature, not part of the public terms.
- **End-user terms duty (Developer Terms 2c, API Terms 7):** Studio's own end-user agreement and acceptable-use policy must be at least as restrictive as the FLUX Usage Policy. This is a Studio-side documentation obligation.
- **Content screening duty (API Terms 5):** the Developer (us) is responsible for reasonable content screening of submitted Input.
- **EU note:** the terms read are the non-EU versions; BFL publishes separate EU Developer Terms and EU API Service Terms. Which applies depends on the contracting entity's residence — must be confirmed and the EU versions read before sign-off (BrandVerita is an EU-facing business).
- **GDPR note:** without a DPA, sending images containing personal data (people, identifiable individuals) to BFL is not defensible. Product-only imagery materially reduces this risk; the scene presets are product-photography oriented, which helps.

## 2. What changes in the compliance record (documentation only, no code)

1. `LICENSE_REVIEW.md` §6.4 — rewrite the Product Scene gate: replace "pending BFL commercial agreement + DPA execution" with "public FLUX API Service Terms (rev. 2026-08-04) accepted as the legal basis", and list the four accepted obligations above (training license on inputs, end-user terms, content screening, EU-terms confirmation).
2. `COMPLIANCE.md` — update the Product Scene row to reference the public-terms basis and the residual obligations.
3. `studio-export/04-production-readiness.md` §2 — same correction for Module B, so Studio's team sees the actual gate: not a contract signature, but acceptance of clause 2b plus Studio-side terms updates.
4. `THIRD_PARTY_NOTICES.md` — add BFL FLUX API Service Terms + Developer Terms + Usage Policy as referenced third-party terms for Module B (hosted service, no distributed code).
5. `studio-export/03-integration-guide.md` — add a short "Customer-facing obligations" note: Studio's end-user terms must flow down the FLUX Usage Policy, and Studio copy must disclose that product images are processed by a third-party AI provider (BFL) which may use them for model improvement.

## 3. What stays unchanged

- Registry: `product_scene:v1` stays testing / research_only / staging-only. Promotion to `product_scene:v2` (production) still requires an explicit decision that clause 2b is acceptable for customer images — that is now a business risk acceptance, not a contract execution.
- No code changes. The adapter, secret (`bfl-research-2b`), $0.04/image metering, and $10 staging cap are untouched.
- Flux Schnell (Apache-2.0) and Outpaint (SD-1.5-inpainting, OpenRAIL-M) remain fully self-hosted and unaffected — they carry none of these third-party terms.
- A production BFL key (`bfl-production` secret) is still created fresh at production-split time, per the existing Track B plan.

## 4. Open question for you before I edit the compliance docs

1. Contracting entity: is BrandVerita's legal entity EU-resident (EU terms apply) or non-EU? This determines which version of the Developer/API Terms governs and should be cited in the docs.
2. Clause 2b risk acceptance: do you accept, as a business decision, that customer product images sent to Product Scene may be used by BFL for model training (with Studio disclosure), or should Product Scene stay research-only indefinitely unless that changes?
