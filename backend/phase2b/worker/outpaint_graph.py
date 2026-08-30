"""
Phase 2B WP1 — the one server-owned outpaint graph.

There is exactly one graph. It is built here, on the server, from a fixed
template plus a seed and a filename pair. No client can send a prompt, a node,
a model name, a sampler, a denoise value or a graph fragment: nothing in this
module reads request data.

`style_mode = preserve_source` is the only supported style, and it maps to the
fixed neutral conditioning below — deliberately content-free so the model
extends texture and background rather than inventing subjects.

Pins (see backend/phase2b/wp1-research-manifest.md):
    ComfyUI  comfyanonymous/ComfyUI @ 3d0003c24c1aec9f0c021dbc70ffb7cd8cf0685c (v0.3.69)
    model    sd-v1-5-inpainting.safetensors
             sha256 ef97ac1fe87ed0406433ad8710ff1da6e07e873de9a1a107b828844336d015ec
    nodes    built-in only, zero custom nodes
"""

from __future__ import annotations

CHECKPOINT = "sd-v1-5-inpainting.safetensors"
CHECKPOINT_SHA256 = "ef97ac1fe87ed0406433ad8710ff1da6e07e873de9a1a107b828844336d015ec"
COMFYUI_COMMIT = "3d0003c24c1aec9f0c021dbc70ffb7cd8cf0685c"
GRAPH_VERSION = "outpaint-v1-preserve-source-1"

# Fixed, server-owned conditioning for style_mode=preserve_source.
POSITIVE = "seamless continuation of the existing photograph, same lighting, same background, same texture"
NEGATIVE = "text, watermark, logo, letters, new objects, people, duplicated subject, frame, border, collage"

STEPS = 25
CFG = 7.0
SAMPLER = "dpmpp_2m"
SCHEDULER = "karras"
GROW_MASK_BY = 8


def build(*, canvas_file: str, mask_file: str, seed: int) -> dict:
    """Return the ComfyUI prompt graph. Only seed and the two server-written
    filenames vary between jobs."""
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": CHECKPOINT},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": POSITIVE, "clip": ["1", 1]},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": NEGATIVE, "clip": ["1", 1]},
        },
        "4": {
            "class_type": "LoadImage",
            "inputs": {"image": canvas_file, "upload": "image"},
        },
        "5": {
            "class_type": "LoadImageMask",
            "inputs": {"image": mask_file, "channel": "red", "upload": "image"},
        },
        "6": {
            "class_type": "VAEEncodeForInpaint",
            "inputs": {
                "pixels": ["4", 0],
                "vae": ["1", 2],
                "mask": ["5", 0],
                "grow_mask_by": GROW_MASK_BY,
            },
        },
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "seed": int(seed),
                "steps": STEPS,
                "cfg": CFG,
                "sampler_name": SAMPLER,
                "scheduler": SCHEDULER,
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["6", 0],
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["7", 0], "vae": ["1", 2]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"images": ["8", 0], "filename_prefix": "wp1_outpaint"},
        },
    }


def config_fingerprint() -> dict:
    """Recorded in provenance so any output can be traced to exact settings."""
    return {
        "graph_version": GRAPH_VERSION,
        "comfyui_commit": COMFYUI_COMMIT,
        "checkpoint": CHECKPOINT,
        "checkpoint_sha256": CHECKPOINT_SHA256,
        "steps": STEPS,
        "cfg": CFG,
        "sampler": SAMPLER,
        "scheduler": SCHEDULER,
        "grow_mask_by": GROW_MASK_BY,
        "custom_nodes": [],
    }
