# Third‑Party Notices

This project, `brandverita/ComfyUI`, includes software and other components from the following third-party projects. We are grateful to the open-source community for their work.

| Component | Version / Commit | License | Source |
|-----------|------------------|---------|--------|
| ComfyUI (upstream) | `3d0003c24c1aec9f0c021dbc70ffb7cd8cf0685c` (v0.3.69) | GPL‑3.0 | https://github.com/comfyanonymous/ComfyUI |
| BrandVerita ComfyUI fork | `344b43989e8c56b5bb4a66cf028c834192ab59dd` (tag `v6-flux-prod`) | GPL‑3.0 (inherited) | https://github.com/brandverita/ComfyUI |
| Custom nodes | *None installed* — the deployed graphs use only built-in nodes at the pinned commit | — | — |
| comfyui-frontend-package | 1.28.8 | GPL‑3.0 | https://pypi.org/project/comfyui-frontend-package/ |
| comfyui-workflow-templates | 0.2.11 | GPL‑3.0 | https://pypi.org/project/comfyui-workflow-templates/ |
| comfyui-embedded-docs | 0.3.1 | GPL‑3.0 | https://pypi.org/project/comfyui-embedded-docs/ |

For full license texts, refer to the respective source repositories.  
Model checkpoints (e.g., FLUX.1, SD‑1.5‑inpainting) are governed by their own licenses and are not included in this notice; they are inventoried in `LICENSE_REVIEW.md` §4.

## ComfyUI (Upstream)

- **Project:** ComfyUI
- **Source:** [comfyanonymous/ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- **Commit:** `3d0003c24c1aec9f0c021dbc70ffb7cd8cf0685c` (tag `v0.3.69`)[reference:0][reference:1]
- **License:** GNU General Public License v3.0[reference:2][reference:3]
- **Copyright:** Copyright (c) comfyanonymous

## BrandVerita Fork Modifications

- **Project:** brandverita/ComfyUI
- **Source:** [https://github.com/brandverita/ComfyUI](https://github.com/brandverita/ComfyUI)
- **Commit:** `344b43989e8c56b5bb4a66cf028c834192ab59dd`
- **License:** GNU General Public License v3.0 (inherited from upstream)
- **Note:** This fork contains modifications to the upstream ComfyUI codebase for the V6 Flux production worker.

## Model Checkpoints (licensed separately)

| Checkpoint | Repo commit / SHA256 | License | Source |
|---|---|---|---|
| `flux1-schnell.safetensors` | build-time SHA256 assertion | Apache‑2.0 | https://huggingface.co/black-forest-labs/FLUX.1-schnell |
| `sd-v1-5-inpainting.ckpt` | repo `8a4288a76071f7280aedbdb3253bdb9e9d5d84bb`, SHA256 `c6bbc15e3224e6973459ba78de4998b80b50112b0ae5b5c67113d56b4e366b19` | CreativeML OpenRAIL‑M | https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-inpainting |

## Python Package Dependencies

This project relies on the following key Python packages and their dependencies. The complete, per-release list is the SPDX SBOM retained as a release artefact alongside the container image digest.

| Package | License | Notes |
|---|---|---|
| torch | BSD-style | Core deep learning framework |
| transformers | Apache 2.0 | Hugging Face model library |
| safetensors | Apache 2.0 | Safe tensor serialization |
| einops | MIT | Tensor operations |
| scipy | BSD | Scientific computing |
| numpy | BSD | Array computing |
| Pillow | MIT-CMU | Image decoding, validation, compositing |
