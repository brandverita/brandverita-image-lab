# Open Source Compliance & License Record

This repository (`brandverita/ComfyUI`) contains BrandVerita's public fork of ComfyUI, deployed as a serverless backend worker (`comfyui-generation-worker-v6`) powering advanced image tools in Studio (`app.brandverita.io`).

We are committed to open-source compliance and copyleft transparency. Below is the index of our licensing, build, and source availability records.

## Compliance Index

| Document | Purpose | Target Audience |
|---|---|---|
| [LICENSE](./LICENSE) | Verbatim GNU General Public License / AGPL text | General Public |
| [SOURCE_OFFER.md](./SOURCE_OFFER.md) | Official Corresponding Source offer for Studio end-users | Studio App Users |
| [BUILD.md](./BUILD.md) | Instructions to build, containerize, and deploy the Modal worker | Developers / Auditors |
| [LICENSE_REVIEW.md](./LICENSE_REVIEW.md) | Architectural boundary, provider terms, and commercial-use audit | Internal / Counsel |

## Deployed Pin & Provenance
* **Active Production Commit:** `344b43989e8c56b5bb4a66cf028c834192ab59dd`
* **Release Tag:** `v6-flux-prod`
* **Upstream Base:** `comfyanonymous/ComfyUI` @ `3d0003c24c1aec9f0c021dbc70ffb7cd8cf0685c` (v0.3.69)

## Approval Status by Module

Recorded 2026-09-05 in [LICENSE_REVIEW.md](./LICENSE_REVIEW.md). The registry, not this document, is the enforcement point.

| Module | Approved commercial status | Production registry row | Enabled |
|---|---|---|---|
| Flux baseline (text-to-image) | `commercial_self_hosted_approved` | `flux_text_to_image:v2`, `allowed_envs = {production}` | Yes |
| Smart Resize / Outpaint | `commercial_self_hosted_approved` | `outpaint:v2`, `allowed_envs = {production}` | Yes |
| Product Scene (BFL hosted) | `commercial_hosted` | `product_scene:v2` | No — held disabled pending the executed BFL commercial agreement and DPA |

For questions regarding our open-source compliance, reach out to `compliance@brandverita.io`.