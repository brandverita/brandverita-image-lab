# License Review and Commercial-Use Record

> **Document status: Approved – recorded on 2026‑09‑05

> **Scope:** Studio advanced-image modules: Smart Resize / Outpaint and Product Scene.
>
> **Last reviewed:** 2026-09-05
>
> **Owner:** BrandVerita Engineering & Legal Compliance
>
> **Repository:** https://github.com/brandverita/ComfyUI
>
> **Public ComfyUI fork:** https://github.com/brandverita/ComfyUI

## 1. Purpose

This document records the licensing, provenance, operational-boundary, and commercial-use review for Studio's advanced image-generation functionality. It is intended to ensure that production enablement occurs only after the applicable software licences, model licences, provider terms, and privacy/data-processing obligations have been reviewed and approved.

This document is an engineering and compliance record, not legal advice. Licence interpretation, including the scope of any copyleft obligation and the effect of service boundaries, must be confirmed by qualified counsel in the jurisdictions in which the service is offered.

## 2. Decision Summary

Recorded 2026-09-05. All three modules are internally approved to proceed. The registry remains the enforcement point: a module is only dispatchable once its production registry row carries the approved `commercial_status` **and** `production_enabled = true`.

| Module | Execution path | Approved commercial status | Production decision |
|---|---|---|---|
| Flux baseline (text-to-image) | Studio (`app.brandverita.io`) -> authenticated backend -> Modal worker (`comfyui-generation-worker-prod`) | `commercial_self_hosted_approved` | **Approved 2026-09-05.** Promote as `flux_text_to_image:v2`, `allowed_envs = {production}`, `production_enabled = true`, `enabled_for_studio = true` |
| Smart Resize / Outpaint | Studio (`app.brandverita.io`) -> authenticated backend -> Modal-hosted ComfyUI workflow (`comfyui-outpaint-worker-prod`) | `commercial_self_hosted_approved` | **Approved 2026-09-05.** Promote as `outpaint:v2`, `allowed_envs = {production}`, `production_enabled = true`, `enabled_for_studio = true` |
| Product Scene | Studio (`app.brandverita.io`) -> authenticated backend -> hosted-provider adapter -> Black Forest Labs API | `commercial_hosted` | **Approved in principle 2026-09-05**, subject to the executed BFL commercial agreement and DPA (external dependency, §6). Row `product_scene:v2` is created with `production_enabled = false` and `enabled_for_studio = false`, and `HOSTED_PROVIDER_DISPATCH_ENABLED = false`, until those execute |
| Studio application | Netlify-hosted Tela integration integrated with main app through JWT handoff | Proprietary / internal | Advanced-module dispatch enabled for Flux and Outpaint once the production registry v2 rows are in place |

No module may be commercially enabled merely because an API account is paid or funded. Commercial enablement requires a documented approval of every applicable layer: source code, workflow/custom nodes, model/checkpoint, hosted-provider terms, data handling, and operational controls.

Staging (`comfy-ui`, Image Lab) rows are unaffected by this approval and remain `research_only` / `internal` / staging-only.

## 3. Architecture and Boundaries

### 3.1 Components

- **Main app (`https://myaccount.brandverita.io/`):** Netlify and Supabase application for review management, review collection, embeddable widgets, Trust Wall pages, forms, QR-to-form links, and system of record for plans/entitlements.
- **Studio (`https://app.brandverita.io/`):** Secondary design application (Tela open-source Canva/Figma clone) integrated with the main app through a signed JWT handoff.
- **Staging / Lab UI (`https://brandverita-image-lab.netlify.app/`):** Internal Netlify staging environment for testing generation pipelines.
- **Outpaint service:** Python/Modal service running a controlled workflow based on the organisation's public ComfyUI fork (`comfyui-generation-worker-v6`).
- **Product Scene service:** Python backend adapter that requests image generation from Black Forest Labs (BFL) using provider credentials held only in server-side secrets.
- **Supabase:** Separate staging/Lab and production projects. Studio stores authorised job metadata, usage/audit events, and permitted output references; it must not expose provider credentials.

### 3.2 Intended request flow

1. A user enters Studio (`app.brandverita.io`) through the main app's (`myaccount.brandverita.io`) JWT handoff.
2. Studio validates the token, establishes the authenticated user and tenant/workspace context, and checks that the requested module is available.
3. Before a generation request is accepted, Studio calls the `myaccount.brandverita.io` entitlement endpoint.
4. Studio dispatches only to a production-approved registry row.
5. The backend invokes either the Modal outpaint workflow or the BFL provider adapter; browser clients never receive Modal or BFL credentials.
6. Studio records an immutable job/audit event and reports usage to the designated metering interface.
7. Output is returned only to the authorised tenant, subject to Supabase RLS and storage access controls.

### 3.3 Licence boundary statement

Studio, the main app, the entitlement service, and the provider-adapter code are maintained as separate repositories/services from the public ComfyUI fork (`https://github.com/brandverita/ComfyUI`). This separation is an architectural fact, not a conclusion that copyleft obligations do or do not extend beyond the fork. Counsel must assess the actual integration, deployment, linking/communication pattern, modifications, and applicable licence text.

## 4. Inventory of Reviewed Materials

Maintain one row for every shipped or executed component. Every artefact is pinned with the five-field rule: source repo URL, immutable full SHA, exact filename, SHA256, licence reference.

| Component | Version / commit / model ID | Source | Licence / terms | Use | Status | Evidence |
|---|---|---|---|---|---|---|
| ComfyUI base (WP1 Research Pin) | `3d0003c24c1aec9f0c021dbc70ffb7cd8cf0685c` (tag `v0.3.69`) | `https://github.com/comfyanonymous/ComfyUI` | GPL-3.0 / AGPL-3.0 upstream terms | Upstream research reference | Verified | Upstream `LICENSE`, archived commit |
| Organisation fork (V6 Flux Production Pin) | `344b43989e8c56b5bb4a66cf028c834192ab59dd` (tag `v6-flux-prod`) | `https://github.com/brandverita/ComfyUI` | GPL-3.0 / AGPL-3.0, upstream plus documented changes | Production worker runtime (`comfyui-generation-worker-prod`) | Approved 2026-09-05 | Public repository, commit history, `CHANGES.md`, `SOURCE_OFFER.md` |
| Custom nodes | **None.** The outpaint graph uses only ComfyUI built-in nodes at the pinned commit | — | — | Workflow dependencies | Verified — no third-party nodes installed | `backend/phase2b/wp1-research-manifest.md` §4 |
| Flux baseline checkpoint | FLUX.1 [schnell], `flux1-schnell.safetensors` | Hugging Face `black-forest-labs/FLUX.1-schnell` | Apache-2.0 | Text-to-image inference | Approved 2026-09-05 | Repo `LICENSE` (Apache-2.0), build-time SHA256 assertion |
| Outpaint checkpoint | `sd-v1-5-inpainting.ckpt`, repo commit `8a4288a76071f7280aedbdb3253bdb9e9d5d84bb`, SHA256 `c6bbc15e3224e6973459ba78de4998b80b50112b0ae5b5c67113d56b4e366b19` (4,265,437,280 bytes) | `https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-inpainting` | CreativeML OpenRAIL-M (use-based restrictions; commercial use permitted subject to Attachment A restrictions) | Inpaint/outpaint inference | Approved 2026-09-05 | Repo licence file, build-time SHA256 verification, `wp1-research-manifest.md` §2 |
| Worker container image | digest `sha256:622e78a1d02c0f90ed900e3985d6c975d8e2dc9ee5e61643aed587dcf9129f42` | Modal-built image | Composite — see SBOM | Outpaint worker runtime | Verified | `wp1-research-manifest.md` §5, image digest assertion |
| Python packages | Pinned at the fork commit: `comfyui-frontend-package==1.28.8`, `comfyui-workflow-templates==0.2.11`, `comfyui-embedded-docs==0.3.1`, plus runtime deps pinned in the worker image | PyPI / Modal runtime | Predominantly MIT / BSD / Apache-2.0 — see `THIRD_PARTY_NOTICES.md` | Backend/runtime | Approved 2026-09-05 | SPDX SBOM retained per release image in the fork repo |
| BFL hosted API | `flux-kontext-pro` | Black Forest Labs | BFL API Commercial Terms | Product Scene inference | **External — pending executed agreement** | Contract/order, terms snapshot, approval memo |
| BFL privacy/DPA | To be executed | Black Forest Labs | Privacy policy, DPA, subprocessor terms | Processing of uploads/prompts | **External — pending execution** | DPA/privacy review record |
| Modal platform | `brandverita` workspace | Modal Labs | Modal Customer Agreement | GPU hosting for Flux and outpaint | Approved 2026-09-05 | Agreement/terms snapshot |
| Studio application | Tela integration release | Internal repository (`app.brandverita.io`) | Proprietary / internal | User interface and orchestration | Not a third-party component | Release record |

## 5. ComfyUI and AGPL/GPL Review

### 5.1 Facts to verify at the pinned source revision

Before approval, the compliance owner must archive and review the upstream `LICENSE`, `NOTICE` files, dependency manifests, and licence declarations at pinned commit `344b43989e8c56b5bb4a66cf028c834192ab59dd`. Do not rely on a licence label shown by a repository host, a later upstream release, or an unpinned default branch.

The review must distinguish:

- The licence for ComfyUI source code.
- Licences for every custom node, extension, frontend component, container base image, Python package, and binary included in the deployed Modal image.
- The licence and commercial-use terms for each model, checkpoint, LoRA, VAE, ControlNet, or Flux weight used by the workflow.
- Terms governing training data, output rights, trademarks, attribution, and any prohibited uses.

### 5.2 Current compliance posture

The organisation maintains its ComfyUI fork as a public repository at `https://github.com/brandverita/ComfyUI` and retains the applicable upstream licence and notices. Any local source modifications deployed to the V6 Flux worker are committed to that public repository at commit `344b43989e8c56b5bb4a66cf028c834192ab59dd`.

If the governing licence includes AGPL-3.0-or-later, the production review must specifically address its network-interaction requirements. Where the organisation operates a modified AGPL-covered program for remote users, the service must provide an effective and prominent opportunity for those users to obtain the Corresponding Source for the deployed modified version.

The source offer must be available from the user-accessible interface or service path that exposes the covered program. It must identify the exact release/commit in use (`344b43989e8c56b5bb4a66cf028c834192ab59dd`), the source URL (`https://github.com/brandverita/ComfyUI`), the applicable licence, the build/deployment instructions required to generate and run the covered work, and the notices needed by the licence.

### 5.3 Required public materials before enablement

The following artefacts must exist in `https://github.com/brandverita/ComfyUI` before enabling the outpaint module in production:

- `LICENSE`: the verbatim governing licence text for the covered source.
- `NOTICE` or `THIRD_PARTY_NOTICES.md`: copyright, attribution, and third-party notices required by included components.
- `CHANGES.md`: meaningful changes made to the fork, with version/date and commit references (`344b43989e8c56b5bb4a66cf028c834192ab59dd`).
- `SOURCE_OFFER.md`: a user-facing source-offer notice describing how to obtain the Corresponding Source of the deployed covered version.
- `BUILD.md`: reproducible build and runtime instructions, including the Modal deployment script, container build reference, workflow export/version, and required non-secret configuration.
- `SBOM.spdx.json` or CycloneDX equivalent: generated for each release image and retained as a release artefact.
- Release tags: immutable git tag matching commit `344b43989e8c56b5bb4a66cf028c834192ab59dd` (e.g., `v6-flux-prod-344b439`).

### 5.4 Example source-offer text

Use only after legal approval and replace placeholders with verified values:

> This service uses a modified version of ComfyUI covered by GPL-3.0 / AGPL-3.0. Users interacting with the covered program through this service may obtain the Corresponding Source for the deployed version, including our modifications and build instructions, at https://github.com/brandverita/ComfyUI under commit SHA `344b43989e8c56b5bb4a66cf028c834192ab59dd` (tag: `v6-flux-prod`). The applicable licence and notices are available at https://github.com/brandverita/ComfyUI/blob/main/LICENSE.

### 5.5 Prohibited assumptions

The following are not sufficient by themselves to clear an AGPL or other copyleft review:

- Maintaining a public fork without confirming that it contains the exact source deployed (`344b43989e8c56b5bb4a66cf028c834192ab59dd`).
- Paying a hosted API provider or Modal infrastructure bills.
- Treating a separate service, HTTP boundary, container, or repository as automatically excluding obligations.
- Assuming that ComfyUI source licensing covers Flux model/checkpoint rights.
- Relying on a dependency's package-manager metadata without reviewing the licence files and transitive dependencies.

### 5.6 Approval gate for self-hosted modules (Flux baseline and Outpaint)

Cleared 2026-09-05. Both self-hosted modules move to `commercial_self_hosted_approved`:

- [x] Upstream ComfyUI licence verified at pinned commit `344b43989e8c56b5bb4a66cf028c834192ab59dd`.
- [x] Public fork `https://github.com/brandverita/ComfyUI` contains the exact deployed modifications; production release tag `v6-flux-prod` is immutable.
- [x] All custom nodes/extensions inventoried and commercially approved — the graph installs none; built-in nodes only at the pinned commit.
- [x] Container/image and Python dependency SBOM generated and reviewed for the Modal deployment (image digest `sha256:622e78a1…`).
- [x] Every model/checkpoint/weight is identified by source, version, hash, and commercial-use terms (§4).
- [x] Model/checkpoint terms expressly permit the intended commercial hosted-service use: FLUX.1-schnell Apache-2.0; SD-1.5-inpainting CreativeML OpenRAIL-M subject to Attachment A use restrictions, which the server-owned enum-only request surface enforces.
- [x] Required notices, source offer, build instructions, and change record are public and accurate in the GitHub repo (`LICENSE`, `NOTICE`/`THIRD_PARTY_NOTICES.md`, `CHANGES.md`, `SOURCE_OFFER.md`, `BUILD.md`).
- [x] Counsel has approved the copyleft analysis and source-disclosure implementation.
- [x] Security review confirms that public source artefacts contain no secrets, customer data, provider credentials, or private infrastructure details.
- [ ] Registry row is approved, `production_enabled=true`, and `enabled_for_studio=true` by authorised release personnel. *(Pending creation of the production registry v2 rows `flux_text_to_image:v2` and `outpaint:v2`, `allowed_envs = {production}`.)*

## 6. BFL Product Scene Review

### 6.1 Commercial terms

A funded BFL account and successful staging calls via `https://brandverita-image-lab.netlify.app/` demonstrate technical access only. Before commercial launch, retain the currently applicable terms, order form or subscription evidence, API product terms, price schedule, rate limits, and any use restrictions applicable to the chosen Product Scene model/API.

Confirm in writing that the intended use is permitted: a multi-tenant, user-facing Studio feature (`app.brandverita.io`) in which users submit images and prompts through the organisation's service and receive generated images. If terms distinguish internal evaluation, individual use, resale, redistribution, white-labeling, or use on behalf of customers, record the applicable interpretation and approval.

### 6.2 Data-processing review

Product Scene requests may contain customer-uploaded images, user prompts, brand assets, and potentially personal data. The privacy review must establish:

- Categories of data sent to BFL and whether special-category personal data must be prohibited.
- Purposes of processing and documented instructions.
- Retention, deletion, logging, training/improvement, and human-access terms.
- Data location/transfer mechanism and applicable GDPR safeguards.
- Current subprocessor list and notification/change process.
- Security measures, incident-notification process, and data-subject request support.
- Whether a data-processing agreement (DPA) is required and executed with Black Forest Labs.

The Studio UX (`app.brandverita.io`) must not promise that uploaded images are never retained, never used for improvement, or processed in a particular region unless the current provider terms and configuration support that promise.

### 6.3 Provider credential controls

- BFL keys are stored only in Modal secrets / Supabase Vault or protected server-side environment variables.
- BFL keys are never included in browser bundles, public Netlify environment variables, client-side logs, screenshots, source offers, or Supabase tables readable by end users.
- Production uses a distinct provider credential from staging (`brandverita-image-lab.netlify.app`).
- Key rotation, revocation, rate-limit response, budget alarms, and usage reconciliation are documented and tested.
- The provider adapter uses authenticated server-to-server calls and applies tenant/user/job correlation IDs without sending unnecessary personal data.

### 6.4 Approval gate for Product Scene

- [ ] Current BFL terms/product terms archived and approved.
- [ ] Commercial use of the selected API/model for the intended multi-tenant feature confirmed.
- [ ] Data-processing and GDPR review approved; DPA executed if required.
- [ ] Provider retention/training/data-use posture is accurately reflected in the privacy notice and Studio UX.
- [ ] Production credential is separate from staging and stored only server-side.
- [ ] Cost limit, timeout, retry policy, idempotency key, and provider outage behavior are tested.
- [ ] Registry row is approved, `production_enabled=true`, and `enabled_for_studio=true` by authorised release personnel.

## 7. Release Controls

### 7.1 Registry requirements

Studio (`app.brandverita.io`) must deny dispatch unless the resolved module registry row meets all conditions below:

```text
commercial_status = 'approved'
production_enabled = true
enabled_for_studio = true
approval_expires_at IS NULL OR approval_expires_at > now()
provider_dispatch_allowed = true  # explicit decision for hosted providers