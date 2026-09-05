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
| *[Add other packages as needed]* | *[License]* | *[Notes]* |

## Custom Nodes

> **Action Required:** List each custom node used in your V6 Flux worker. Include its name, source URL, commit SHA (if available), and license. Most custom nodes that directly integrate with ComfyUI are derivative works and are generally expected to be under GPL-3.0 or a compatible license.[reference:10][reference:11]

| Name | Source | Version / Commit | License |
|---|---|---|---|
| *[e.g., ComfyUI-Manager]* | *[URL]* | *[SHA]* | GPL-3.0[reference:12]|
| *[e.g., WAS Node Suite]* | *[URL]* | *[SHA]* | MIT[reference:13]|
| *[Add other custom nodes]* | *[URL]* | *[SHA]* | *[License]* |

## Model Weights / Checkpoints

> **Action Required:** List the specific models used by your workflows (e.g., FLUX.1). These are governed by their own licenses and are distinct from the ComfyUI source code.[reference:14][reference:15]

| Model | Source | License / Terms |
|---|---|---|
| FLUX.1 [dev/schnell] | Black Forest Labs / Hugging Face | BFL Model License |
| *[Add other models]* | *[Source]* | *[License]* |

## How to Complete This Document

1.  **Inventory Python Dependencies**: Check your Modal worker's `requirements.txt` or `pyproject.toml` file for a complete list of Python packages[reference:16]. Use a tool like `pip-licenses` to help generate a list of licenses.
2.  **Identify Custom Nodes**: Examine the `custom_nodes` directory in your V6 Flux worker deployment. For each custom node, note its name, source URL, and the license stated in its repository[reference:17].
3.  **Review Model Licenses**: Document the specific model checkpoints (e.g., FLUX.1, upscale models) used in your workflows and confirm their commercial-use terms[reference:18].
4.  **Update This File**: Replace the placeholder entries in the tables above with your actual component details.
5.  **Generate Full SBOM**: For complete compliance, generate a full Software Bill of Materials (SBOM) in SPDX or CycloneDX format for each release. This can be a separate release artifact.

For any questions regarding this notice or open-source compliance, please contact `admin@brandverita.io`.

---