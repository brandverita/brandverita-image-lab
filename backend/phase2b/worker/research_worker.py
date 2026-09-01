"""
Phase 2B WP1 — isolated research worker.

    modal deploy research_worker.py

Deployment identity (deliberately unique — WP1 requirement 1):

    app    comfyui-research-worker-2b
    class  ResearchOutpaintWorker
    volume research-2b-models

It shares NO app name, image, volume, secret or class with
comfyui-generation-worker, comfyui-generation-worker-v6, brandverita-api or
brandverita-api-v6. Deploying, breaking or deleting this app cannot affect V5,
V6 or the Flux text-to-image path.

Classification: research_only, staging only, internal evaluation assets only.
No customer data. Never dispatched from production.

The worker receives only bytes: a server-built canvas, a server-built mask and
a seed. It has no Supabase credentials, no storage access, no asset ids, and no
way to receive a prompt or a graph — the graph is compiled in-image from
outpaint_graph.py.

Secrets: none. The checkpoint comes from an ungated Hugging Face repo and is
downloaded + SHA256-verified at image build time, so no token exists in this
app at request time.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
import uuid

import modal

APP_NAME = "comfyui-research-worker-2b"
WORKER_VERSION = "research-2b-outpaint-1"

COMFYUI_REPO = "https://github.com/comfyanonymous/ComfyUI"
COMFYUI_COMMIT = "3d0003c24c1aec9f0c021dbc70ffb7cd8cf0685c"  # tag v0.3.69

# Ungated source. The previous pin (benjamin-paine/...) is a gated repo: the
# HF token was valid but the account was not on its authorized list, so every
# container crashed in @modal.enter() with GatedRepoError. This repo is the
# community-maintained continuation of the removed runwayml repo, is not gated,
# and needs no token at all.
CHECKPOINT_REPO = "stable-diffusion-v1-5/stable-diffusion-inpainting"
CHECKPOINT_REVISION = "8a4288a76071f7280aedbdb3253bdb9e9d5d84bb"
CHECKPOINT_FILE = "sd-v1-5-inpainting.ckpt"
CHECKPOINT_SHA256 = "c6bbc15e3224e6973459ba78de4998b80b50112b0ae5b5c67113d56b4e366b19"

MODEL_DIR = "/models"
COMFY_DIR = "/opt/ComfyUI"
COMFY_PORT = 8188

app = modal.App(APP_NAME)
model_volume = modal.Volume.from_name("research-2b-models", create_if_missing=True)

CHECKPOINT_PATH = f"{MODEL_DIR}/checkpoints/{CHECKPOINT_FILE}"


def _fetch_checkpoint() -> None:
    """Download the pinned checkpoint into the volume, verified by SHA256.

    This runs at IMAGE BUILD time (`.run_function`), not at request time: a
    download or digest failure now fails `modal deploy` loudly instead of
    crash-looping every container while a submitted job hangs.
    """
    from huggingface_hub import hf_hub_download

    os.makedirs(f"{MODEL_DIR}/checkpoints", exist_ok=True)
    if os.path.exists(CHECKPOINT_PATH):
        print(f"wp1_checkpoint_present path={CHECKPOINT_PATH}")
        return
    print(f"wp1_checkpoint_download repo={CHECKPOINT_REPO} file={CHECKPOINT_FILE}")
    path = hf_hub_download(
        repo_id=CHECKPOINT_REPO,
        filename=CHECKPOINT_FILE,
        revision=CHECKPOINT_REVISION,
        token=os.environ.get("HF_TOKEN") or None,  # ungated repo: token optional
    )
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(8 << 20), b""):
            digest.update(chunk)
    if digest.hexdigest() != CHECKPOINT_SHA256:
        raise RuntimeError("checkpoint sha256 mismatch — refusing to build image")
    shutil.copyfile(path, CHECKPOINT_PATH)
    model_volume.commit()
    print(f"wp1_checkpoint_ready sha256={CHECKPOINT_SHA256}")


research_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04"
        "@sha256:622e78a1d02c0f90ed900e3985d6c975d8e2dc9ee5e61643aed587dcf9129f42",
        add_python="3.12",
    )
    .apt_install("git", "libgl1", "libglib2.0-0")
    .pip_install(
        "torch==2.6.0+cu124",
        "torchvision==0.21.0+cu124",
        "torchaudio==2.6.0+cu124",
        extra_index_url="https://download.pytorch.org/whl/cu124",
    )
    .pip_install(
        "torchsde==0.2.6",
        "einops==0.8.0",
        "transformers==4.48.0",
        "tokenizers==0.21.0",
        "sentencepiece==0.2.0",
        "safetensors==0.4.5",
        "aiohttp==3.11.11",
        "yarl==1.18.3",
        "pyyaml==6.0.2",
        "Pillow==11.0.0",
        "scipy==1.14.1",
        "tqdm==4.67.1",
        "psutil==6.1.1",
        "kornia==0.7.4",
        "spandrel==0.4.1",
        "soundfile==0.13.0",
        "av==14.0.1",
        "comfyui-frontend-package==1.28.8",
        "comfyui-workflow-templates==0.2.11",
        "comfyui-embedded-docs==0.3.1",
        "huggingface_hub==0.27.1",
    )
    .run_commands(
        f"git clone {COMFYUI_REPO} {COMFY_DIR}",
        f"cd {COMFY_DIR} && git checkout {COMFYUI_COMMIT}",
        # zero custom nodes by construction
        f"rm -rf {COMFY_DIR}/custom_nodes/* || true",
    )
    .add_local_file("outpaint_graph.py", "/root/outpaint_graph.py", copy=True)
    # Weights are fetched and digest-verified at BUILD time, so a bad pin or a
    # gated repo fails `modal deploy` instead of hanging a submitted job.
    .run_function(_fetch_checkpoint, volumes={MODEL_DIR: model_volume})
)


@app.cls(
    image=research_image,
    gpu="A10G",
    volumes={MODEL_DIR: model_volume},
    timeout=1200,
    scaledown_window=60,
    max_containers=2,
)
class ResearchOutpaintWorker:
    """One method, byte-in/byte-out. No storage, no database, no asset ids."""

    @modal.enter()
    def start(self) -> None:
        boot_started = time.time()
        if not os.path.exists(CHECKPOINT_PATH):
            # Should be impossible: the build step put it there. Fail fast and
            # loudly rather than trying to download at request time.
            raise RuntimeError(f"checkpoint missing at {CHECKPOINT_PATH}")
        print(f"wp1_worker_boot_start checkpoint={CHECKPOINT_FILE}")

        with open(f"{COMFY_DIR}/extra_model_paths.yaml", "w") as handle:
            handle.write(
                "research:\n"
                f"  base_path: {MODEL_DIR}\n"
                "  checkpoints: checkpoints\n"
            )

        self.process = subprocess.Popen(
            [
                "python",
                "main.py",
                "--listen",
                "127.0.0.1",
                "--port",
                str(COMFY_PORT),
                "--disable-auto-launch",
                "--disable-metadata",
                "--extra-model-paths-config",
                f"{COMFY_DIR}/extra_model_paths.yaml",
            ],
            cwd=COMFY_DIR,
        )
        deadline = time.time() + 240
        while time.time() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(
                    f"ComfyUI exited during boot with code {self.process.returncode}"
                )
            try:
                urllib.request.urlopen(
                    f"http://127.0.0.1:{COMFY_PORT}/system_stats", timeout=2
                )
                print(f"wp1_worker_boot_ready seconds={round(time.time() - boot_started, 1)}")
                return
            except Exception:  # noqa: BLE001
                time.sleep(1)
        raise RuntimeError("ComfyUI did not become ready within 240s")

    @modal.exit()
    def stop(self) -> None:
        try:
            self.process.terminate()
        except Exception:  # noqa: BLE001
            pass

    # -- helpers ---------------------------------------------------------- #

    def _post(self, path: str, payload: dict) -> dict:
        request = urllib.request.Request(
            f"http://127.0.0.1:{COMFY_PORT}{path}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as exc:
            # ComfyUI puts per-node validation errors in the 400 body; without
            # this the caller only ever sees 'HTTP Error 400'.
            body = b""
            try:
                body = exc.read()[:1500]
            except Exception:  # noqa: BLE001
                pass
            raise RuntimeError(
                f"comfy_http_{exc.code} on {path}: {body.decode('utf-8', 'replace')}"
            ) from exc

    def _get(self, path: str) -> bytes:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{COMFY_PORT}{path}", timeout=60
        ) as response:
            return response.read()

    # -- the only entry point --------------------------------------------- #

    @modal.method()
    def outpaint(self, canvas_png: bytes, mask_png: bytes, seed: int) -> dict:
        """Run the pinned graph. Returns {"image": bytes, "worker_version":...,
        "graph": {...}, "gpu_seconds": float}.

        Every temp file this method writes — canvas, mask, ComfyUI output — is
        deleted in the finally block, whatever the outcome.
        """
        import outpaint_graph

        started = time.time()
        job_dir = tempfile.mkdtemp(prefix="wp1-", dir="/tmp")
        token = uuid.uuid4().hex
        canvas_name = f"wp1_canvas_{token}.png"
        mask_name = f"wp1_mask_{token}.png"
        comfy_input = f"{COMFY_DIR}/input"
        comfy_output = f"{COMFY_DIR}/output"
        written: list[str] = []

        try:
            os.makedirs(comfy_input, exist_ok=True)
            for name, data in ((canvas_name, canvas_png), (mask_name, mask_png)):
                path = os.path.join(comfy_input, name)
                with open(path, "wb") as handle:
                    handle.write(data)
                written.append(path)

            graph = outpaint_graph.build(
                canvas_file=canvas_name, mask_file=mask_name, seed=int(seed)
            )
            client_id = uuid.uuid4().hex
            queued = self._post("/prompt", {"prompt": graph, "client_id": client_id})
            prompt_id = queued.get("prompt_id")
            if not prompt_id:
                raise RuntimeError("ComfyUI rejected the graph")
            print(f"wp1_worker_graph_queued prompt_id={prompt_id}")

            deadline = time.time() + 420
            image_meta = None
            while time.time() < deadline:
                history = json.loads(self._get(f"/history/{prompt_id}") or b"{}")
                entry = history.get(prompt_id)
                if entry:
                    status = (entry.get("status") or {}).get("status_str")
                    if status == "error":
                        messages = (entry.get("status") or {}).get("messages") or []
                        raise RuntimeError(
                            "graph execution failed: "
                            + json.dumps(messages)[:1500]
                        )
                    images = (entry.get("outputs", {}).get("9", {}) or {}).get("images")
                    if images:
                        image_meta = images[0]
                        break
                time.sleep(1)
            if image_meta is None:
                raise RuntimeError("graph execution timed out after 420s")
            print(
                f"wp1_worker_graph_done seconds={round(time.time() - started, 1)}"
            )

            query = (
                f"/view?filename={image_meta['filename']}"
                f"&subfolder={image_meta.get('subfolder','')}"
                f"&type={image_meta.get('type','output')}"
            )
            image_bytes = self._get(query)
            written.append(
                os.path.join(
                    comfy_output,
                    image_meta.get("subfolder", ""),
                    image_meta["filename"],
                )
            )

            return {
                "image": image_bytes,
                "worker_version": WORKER_VERSION,
                "graph": outpaint_graph.config_fingerprint(),
                "gpu_seconds": round(time.time() - started, 3),
            }
        finally:
            for path in written:
                try:
                    os.unlink(path)
                except OSError:
                    pass
            shutil.rmtree(job_dir, ignore_errors=True)
            print(f"wp1_worker_cleanup files={len(written)} dir_removed=1")
