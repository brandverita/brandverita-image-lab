# WP1 — outpaint job fails fast; make the real error visible, then fix it

## What the run tells us

- 12/17 passed. Every gate, rejection, privacy and regression check is green: the framework, geometry validation, registry visibility, Flux and V5 are all fine.
- The only defect is the job itself: `status=failed`, `error_code=transformation_failed`, at 40s after `started_at` — well inside the 900s worker timeout. So this is **not** the old hang: something raised.
- Checks 7, 7b, 8a, 8b are downstream consequences of check 4 — no output asset exists because the job failed. There is one bug, not five.
- `width/height = 1200x627` were written at submit time from the preset, which is why check 5 passes on a failed job.

The failing branch in `adapters/modal_research_outpaint.py` deliberately returns a generic message to the client and logs only `wp1_outpaint_failed job=... type=<ExceptionType>`. That means **the exception type is already recorded but not in the API response** — it is in the Modal log and in `transformation_eval_runs.error_message`. The root cause is therefore not yet confirmed and step 1 exists to confirm it rather than guess.

## Step 1 — read the two facts that name the cause (no code change)

```sql
select status, error_code, error_message, provider_latency_ms, total_latency_ms,
       source_region_verified, gpu_seconds, worker_version
from transformation_eval_runs
where job_id = '2823988f-1107-434b-8f64-970f7459c2c4';
```

`error_message` there holds the exception type name.

```bash
modal app logs brandverita-api-v6 | grep -E "wp1_outpaint_failed|wp1_temp_cleanup"
modal app logs comfyui-research-worker-2b
```

The worker log is the decisive one. Three distinguishable shapes:

| Worker log | Meaning |
| --- | --- |
| nothing at all, no container started | the failure happened API-side before dispatch (asset download, digest verify, or geometry) |
| `wp1_worker_boot_start` then a traceback / non-zero exit | ComfyUI boot problem — most likely the checkpoint path/`extra_model_paths.yaml` wiring, since the `.ckpt` is a new file type for this graph |
| `wp1_worker_boot_ready` then `graph execution failed` | the graph rejected a node/input — `VAEEncodeForInpaint` + `.ckpt` loader mismatch is the prime suspect |

40s with no GPU work strongly suggests one of the first two, but the log decides.

## Step 2 — stop losing the error (small, safe change)

Regardless of what step 1 shows, the diagnostic gap is itself a defect worth closing before Module B:

- In the adapter's `except`, print `traceback.format_exc()` (server-side log only) and set `eval_row["error_message"]` to the exception's own string, truncated. The client-facing message stays generic.
- In the worker, on `status == "error"`, include ComfyUI's own node error text from the history entry in the raised message so it reaches the API log.
- On boot failure, capture ComfyUI's stderr tail into the `RuntimeError`.

This is staging-only research code with no users, so richer server-side error text is an acceptable trade.

## Step 3 — fix the confirmed cause

Applied only once step 1 names it. Likely fixes, in order of probability:

1. **Checkpoint not visible to ComfyUI** — verify `/models/checkpoints/sd-v1-5-inpainting.ckpt` exists in the volume after build and that `extra_model_paths.yaml` resolves it; if the loader still misses it, symlink into `${COMFY_DIR}/models/checkpoints/` instead of relying on the extra-paths file.
2. **`.ckpt` load blocked** — the pickle checkpoint may need `--disable-smart-memory` / a torch `weights_only` accommodation at this ComfyUI pin; the fallback is the safetensors conversion of the same ungated repo, re-pinned with its own SHA256 in the manifest.
3. **Graph mismatch** — adjust the inpaint encode path to what the pinned commit exposes for SD-1.5-inpainting.

No registry, API, or framework change is expected; the fix stays inside the worker pair.

## Step 4 — re-run and close out

Re-run `test_wp1_outpaint.py` unchanged. Target: 17/17, with the SQL rows showing `source_region_verified = true` and the output asset `ready` at 1200x627. Then the WP1 result is recorded in `backend/phase2b/module-a.md` (worker revision, pins, latency, gpu_seconds, cost) and Module B (BFL product scene) starts.

## What is not changing

Registry row stays `testing` / `research_only` / `internal` / `production_enabled=false` / `allowed_envs=[staging]`. No Studio exposure, no V5/V6 Flux change, no credits or billing logic.
