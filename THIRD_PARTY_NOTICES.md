# Third‑Party Notices

This project, `brandverita/ComfyUI`, includes software and other components from the following third-party projects. We are grateful to the open-source community for their work.

| Component | Version / Commit | License | Source |
|-----------|------------------|---------|--------|
| ComfyUI (upstream) | v0.3.69 | GPL‑3.0 | https://github.com/comfyanonymous/ComfyUI |
| Custom node: [name] | [SHA] | [license] | [URL] |
| Python package: [name] | [version] | [license] | [PyPI] |
| … | … | … | … |

For full license texts, refer to the respective source repositories.  
Model checkpoints (e.g., FLUX.1) are governed by their own licenses and are not included in this notice.

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

## Python Package Dependencies

This project relies on the following key Python packages and their dependencies. For a complete list, please refer to the `requirements.txt` or lock file in the repository.[reference:4]

| Package | License | Notes |
|---|---|---|
| torch | BSD-style | Core deep learning framework[reference:5] |
| transformers | Apache 2.0 | Hugging Face model library[reference:6] |
| safetensors | Apache 2.0 | Safe tensor serialization[reference:7] |
| einops | MIT | Tensor operations[reference:8] |
| scipy | BSD | Scientific computing[reference:9] |
