# Module A — Smart Resize / Outpaint (staging, living doc)

Single source of truth for Module A. Supersedes the WP1 step-by-step README for
day-to-day work; the research manifest still holds the artifact pins.

## Current state

- API app: `brandverita-api-v6` — routes, registry gate, lineage, storage, ledger.
- Research worker: `comfyui-research-worker-2b` — bytes in, bytes out. No
  Supabase credentials, no asset ids, no prompt input, no secrets at all.
- Registry row: `outpaint:v1`, `status=testing`, `commercial_status=research_only`,
  `registry_visibility=internal`, `allowed_envs=[staging]`,
  `production_enabled=false`, `enabled_for_studio=false`.
- Staging flags are ON in the image (`ADVANCED_WORKFLOWS_ENABLED`,
  `OUTPAINT_EVAL_ENABLED`, `MODULE_A_ENABLED` = true; Module B and hosted
  dispatch still false). No flag-flip redeploy dance per test run. Isolation
  comes from the registry row and the Lab allow-list, not from the flags.

## 2026-09-01 incident and fix

First real job (`54247e4e-…`) hung and was killed at the 3600s function timeout.
Cause: the pinned checkpoint repo `benjamin-paine/stable-diffusion-v1-5-inpainting`
is gated; the HF token was valid but unauthorized, so `hf_hub_download` raised
`GatedRepoError (403)` inside `@modal.enter()`. Containers crash-looped while the
API sat in a blocking `.remote()` with no error to report.

Three changes, all shipped:

1. **Ungated checkpoint.** `stable-diffusion-v1-5/stable-diffusion-inpainting`
   @ `8a4288a76071f7280aedbdb3253bdb9e9d5d84bb`, `sd-v1-5-inpainting.ckpt`,
   sha256 `c6bbc15e3224e6973459ba78de4998b80b50112b0ae5b5c67113d56b4e366b19`.
   No Hugging Face token anywhere; the `huggingface-research-2b` secret is dead
   and can be deleted. Registry `artifact_pins` updated to match.
2. **Weights fetched at build time.** `research_image.run_function(_fetch_checkpoint)`
   downloads and digest-verifies before the image exists, so a bad pin fails
   `modal deploy` instead of a submitted job. `@modal.enter()` only asserts the
   file is present and prints `wp1_worker_boot_start` / `wp1_worker_boot_ready`.
3. **Nothing can hang silently.** Adapter uses `spawn` + `get(timeout=900)` and
   raises `worker_timeout`; ComfyUI boot capped at 240s and fails fast if the
   process exits; graph wait capped at 420s; API `run_outpaint_job` timeout
   1200s (was 3600).

## Deploy

```bash
cd modal-project/phase1-v6-staging
modal deploy worker/research_worker.py   # first build downloads ~4.3 GB
modal deploy api.py
curl -s https://<api>/health | jq '{advanced_framework, outpaint_adapter, research_worker_app, advanced_flags_enabled}'
```

Expect `advanced_flags_enabled: true` with no flag editing.

## Smoke test

`tests/test_wp1_outpaint.py` — no longer needs the interactive flag pauses; just
run it. Watch:

- API log: `wp1_outpaint_completed job=… verified=True`, `wp1_temp_cleanup … dir_exists=False`
- Worker log: `wp1_worker_boot_ready seconds=…`, `wp1_worker_graph_queued`, `wp1_worker_graph_done`

Failure vocabulary now: `worker_timeout`, `source_region_integrity_failed`,
`checkpoint missing at /models/…`, `ComfyUI exited during boot with code N`.

## Known trade-off

The in-use checkpoint is a pickle `.ckpt`, not safetensors. Accepted for staging
research: digest verified at build time, worker holds no credentials and no path
to customer data. FLUX.1-Fill-dev is the only quality upgrade and stays blocked
on licensing.

## Out of scope here

Credits, plan allowance, and user privileges are owned by
`myaccount.brandverita.io`. This deployment only records metering rows
(`usage_ledger`, `transformation_eval_runs`) so the main app can consume them
later; it never enforces limits.

## 2026-09-01 — WP1 run 2: job failed after a successful generation

Symptom: job `2823988f` reached 51.4s, output was exactly 1200x627, source-region
integrity verified — then `transformation_failed` with eval `error_message = "HTTPException"`.

Root cause: `advanced.write_ready_output` sent an app-computed `finalized_at` but
let Postgres default `created_at`, so `created_at` landed a few milliseconds later
and the `validate_generation_asset_expiry` trigger raised
`finalized_at cannot precede created_at`. The insert failed, the uploaded bytes
were rolled back, and no output asset row was created.

Fixes:
- `advanced.write_ready_output` now stamps `created_at`, `finalized_at` and
  `expires_at` from one instant.
- Adapter records `provider_latency_ms`, `gpu_seconds` and `worker_version` as
  soon as the worker returns, prints `wp1_stage` markers per step, and writes the
  real exception text (HTTPException `.detail` included) plus a traceback. Clients
  still receive only the generic `transformation_failed` message.
- Worker surfaces ComfyUI 400 bodies and per-node history error messages instead
  of bare `HTTP Error 400` / `graph execution failed`.

## 2026-09-01 — WP1 accepted

17/17 checks passed. Latency 44.7s end-to-end (target p95 ≤ 90s), output exactly
1200x627, `source_region_verified = true`, output served only via short-lived
signed URL, temp dirs removed on both sides, `outpaint:v1` invisible to
studio-origin registry reads, Flux text-to-image unaffected.

Pinned artifact in effect: `sd-v1-5-inpainting.ckpt` from the ungated mirror
`stable-diffusion-v1-5/stable-diffusion-inpainting`, SHA256 `c6bbc15e...`,
fetched at image build time (a bad pin now fails `modal deploy`, not a job).

Module A is the reference implementation for the shared framework: Module B
follows the same gate → download → verify → transform → validate → upload → hash
→ ready-row → cleanup order.
