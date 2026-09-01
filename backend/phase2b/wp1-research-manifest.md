# Phase 2B — WP1 Research Workflow Manifest (approval gate)

**Module:** A — Smart Resize / Outpaint
**Workflow:** `outpaint:v1`
**Classification:** `research_only`, **staging only**
**Worker app:** `comfyui-research-worker-2b` (new, isolated)
**Date compiled:** 2026-08-30

> **Nothing in this manifest has been installed, built, or deployed.** Every SHA below was
> retrieved from the upstream source at compile time, not written from memory. One decision
> is still open — see §7.

## 0. Classification statement

This workflow is **research_only** and **staging_only**. It runs exclusively in the staging
Supabase project (`comfy-ui` / `thspgkedjkiltrcimond`) on internal, BrandVerita-owned or
licensed evaluation assets. It processes **no customer data**, is **not** exposed to Studio,
is **not** production-enabled, and must not be dispatched from any production surface.
Registry row stays `status = testing`, `commercial_status = research_only`,
`registry_visibility = internal`, `production_enabled = false`, `enabled_for_studio = false`,
`allowed_envs = [staging]`. All feature flags remain `false` by default.

## 1. ComfyUI

| Field | Value |
| --- | --- |
| Source | https://github.com/comfyanonymous/ComfyUI |
| Tag | `v0.3.69` |
| Immutable commit | `3d0003c24c1aec9f0c021dbc70ffb7cd8cf0685c` |
| License | GPL-3.0 (repo `LICENSE`) |
| Pinned requirements at that commit | `comfyui-frontend-package==1.28.8`, `comfyui-workflow-templates==0.2.11`, `comfyui-embedded-docs==0.3.1` (upstream-pinned), plus unpinned runtime deps that we pin ourselves in §5 |

This pin is **separate** from the V6 production worker pin (`344b4398…`). The two workers
share no image, no volume, and no code path.

## 2. Inpainting / outpainting checkpoint

**In use (revised 2026-09-01 after the gated-repo failure):**

| Field | Value |
| --- | --- |
| Repo | https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-inpainting |
| Repo commit | `8a4288a76071f7280aedbdb3253bdb9e9d5d84bb` |
| Filename | `sd-v1-5-inpainting.ckpt` |
| SHA256 | `c6bbc15e3224e6973459ba78de4998b80b50112b0ae5b5c67113d56b4e366b19` |
| Size | 4,265,437,280 bytes |
| License | CreativeML OpenRAIL-M (use-based restrictions; research use permitted) |
| Access | **Ungated** (`gated: false`) — no Hugging Face token required |
| Contains | UNet + CLIP text encoder + VAE in one file |

Why this replaced the original pin: `benjamin-paine/stable-diffusion-v1-5-inpainting` is
gated (`gated: auto`). The research token was valid but the account was not on the repo's
authorized list, so `hf_hub_download` raised `GatedRepoError (403)` inside
`@modal.enter()`; every container crash-looped and the submitted job sat blocked until the
3600s function timeout. Trade-off accepted: this file is a pickle `.ckpt` rather than
safetensors. Mitigations — the digest above is verified at **image build time** before the
file is written to the volume, the worker holds no credentials and no network egress path
to our data, and the build fails outright on any mismatch.

Rejected alternatives: `benjamin-paine/...` (gated, cause of the outage);
`black-forest-labs/FLUX.1-Fill-dev` (access-restricted and non-commercial —
`flux1-fill-dev.safetensors` SHA256
`03e289f530df51d014f48e675a9ffa2141bc003259bf5f25d75b957e920a41ca`), kept on file only as a
possible quality upgrade if licensing is ever cleared.

## 3. VAE and text encoders

- **In-use checkpoint:** none needed — the SD-1.5-inpainting checkpoint embeds VAE + CLIP-L.
- **Only if option C is chosen:** `comfyanonymous/flux_text_encoders`, repo commit
  `6af2a98e3f615bdfa612fbd85da93d1ed5f69ef5` — `clip_l.safetensors` SHA256
  `660c6f5b1abae9dc498ac2d21e1347d2abdb0cf6c0c0c8576cd796491d9a6cdd`,
  `t5xxl_fp16.safetensors` SHA256
  `6e480b09fae049a72d2a8c5fbccb8d3e92febeb233bbe9dfe7256958a9167635`
  (Apache-2.0 repackaging of Google T5 / OpenAI CLIP weights).

## 4. Custom nodes

**None.** The graph uses only ComfyUI built-in nodes at the pinned commit:

```text
CheckpointLoaderSimple → CLIPTextEncode (fixed empty/neutral conditioning, server-owned)
LoadImage (server-written canvas) + LoadImageMask (server-written mask)
  → VAEEncodeForInpaint → KSampler → VAEDecode → SaveImage
```

Zero third-party custom nodes means zero additional licenses and zero unpinned code. If the
graph later needs one, it gets its own repo + commit + license row here before installation.

## 5. Runtime, image, and hardware

| Field | Value |
| --- | --- |
| Base image | `nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04` |
| Image digest | `sha256:622e78a1d02c0f90ed900e3985d6c975d8e2dc9ee5e61643aed587dcf9129f42` |
| Python | 3.12 |
| PyTorch | `torch==2.6.0+cu124` (`torch-2.6.0+cu124-cp312-cp312-linux_x86_64.whl`, index `https://download.pytorch.org/whl/cu124`), with matching `torchvision`/`torchaudio`/`torchsde` |
| CUDA | 12.4 (runtime from the base image, matching the cu124 wheels) |
| GPU class | A10G (same class as V6, separate app and container pool) |
| Volume | new dedicated Modal volume `research-2b-models` — not shared with any V5/V6 volume |
| Secrets | none for options A/B beyond an HF read token (see §7); no provider API keys, no `STUDIO_HANDOFF_SECRET`, nothing frontend-reachable |

## 6. Isolation guarantees

`comfyui-research-worker-2b` shares no name, image, volume, secret, or deployment identity
with `comfyui-generation-worker`, `comfyui-generation-worker-v6`, `brandverita-api`, or
`brandverita-api-v6`. Deploying, breaking, or deleting it cannot affect V5, V6, or Flux.

## 7. Resolved — checkpoint decision (closed 2026-09-01)

Originally decided as option A (gated SD-1.5-inpainting safetensors + HF read token). That
repo's gate rejected our token at runtime, so WP1 now runs the **ungated
`stable-diffusion-v1-5/stable-diffusion-inpainting` `.ckpt`** pinned in §2, with no Hugging
Face token required anywhere. The `huggingface-research-2b` Modal secret is no longer read by
the worker and can be deleted. FLUX.1-Fill-dev remains the only quality upgrade path and stays
blocked on licensing.
