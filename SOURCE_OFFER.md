# SOURCE_OFFER.md

## Source Code Offer & License Compliance

This document serves as the formal offer of Corresponding Source for modified software deployed within BrandVerita Studio (`app.brandverita.io`).

### Deployed Covered Software
* **Service / Feature:** Studio Advanced Image Module (Smart Resize / Outpaint)
* **Execution Environment:** Modal serverless worker (`comfyui-generation-worker-v6`)
* **Upstream Project:** [ComfyUI (comfyanonymous/ComfyUI)](https://github.com/comfyanonymous/ComfyUI)
* **Governing License:** GNU General Public License v3.0 / GNU Affero General Public License v3.0

### Source Code Availability
Users interacting with the Outpaint / Smart Resize generation features in BrandVerita Studio are entitled under the governing license to access the exact Corresponding Source code used in the active deployment.

* **Public Repository:** [https://github.com/brandverita/ComfyUI](https://github.com/brandverita/ComfyUI)
* **Production Commit SHA:** `344b43989e8c56b5bb4a66cf028c834192ab59dd`
* **Production Release Tag:** `v6-flux-prod`

### Included Components
The corresponding source code provided at the repository link includes:
1. Full source code of the modified ComfyUI base application at the pinned commit.
2. Custom node extensions and workflow dependencies integrated into the generation runtime.
3. Container definition and build instructions (see `BUILD.md`) required to build and execute the worker environment.

*Note: Model checkpoints, VAEs, and LoRA weights (such as FLUX.1) are governed by their respective model licenses and are distinct from the ComfyUI application source code.*