# WP1 — Module A: Smart Resize / Outpaint (internal staging research experiment)

All seven requirements are correct and doable against the WP0 framework, with three details to confirm below (they are noted, not blockers). WP2 / BFL / Replicate / Studio / billing / credits / production / customer UI stay untouched.

## Confirmations and corrections

1. **Parameter shape** — WP0's approved parser already uses `expansion_mode = "anchor_directional"` (the *mode*) plus `direction ∈ {left,right,top,bottom,symmetric}` and `anchor`, with the compatibility table: left→{right,center}, right→{left,center}, top→{bottom,center}, bottom→{top,center}, symmetric→{center}. Your five values are the `direction` enum. I keep the WP0 field names so the WP0 suite stays valid, and document the mapping. Say the word if you want the field literally renamed `expansion_mode` instead.
2. **Presets** — the registry row currently allows five presets. WP1 narrows `outpaint:v1` to exactly `["1200x627","1600x900"]` via a one-row data migration (row is `testing`, so the immutability trigger permits it).
3. **Manifest SHAs cannot be authored from memory.** Step 1 below fetches real upstream commits, file digests, and license texts and records the actual values. Nothing is installed, built, or deployed until you approve that manifest.

## Step 1 — Research workflow manifest (approval gate, no installation)

Deliverable: `backend/phase2b/wp1-research-manifest.md`, every entry with source URL, immutable full commit SHA, exact filename, SHA256, license reference and license file link:

- ComfyUI upstream repo + pinned commit (separate pin from the V6 worker's `344b4398…`; not shared).
- Inpainting/outpainting checkpoint (candidate: an SD-1.5-inpainting-class or FLUX-Fill-class model — license decides; recorded with license and any commercial restriction).
- VAE, text encoders / CLIP artifacts.
- Every custom node repo + commit + license (target: zero custom nodes; if the graph needs one, it is pinned and licensed explicitly).
- Python version, PyTorch version, CUDA version, base image digest, GPU class.
- Explicit statement: `research_only`, `staging_only`, no customer data, no production dispatch, no Studio exposure.

I will flag any artifact whose license is not clearly compatible with even internal research use, and stop rather than pick one for you.

## Step 2 — Separate Modal worker app

New app `comfyui-research-worker-2b`, its own `modal.App`, own image, own volume/model cache, own class `ResearchOutpaintWorker`. It shares no name, image, volume, secret, or deployment identity with `comfyui-generation-worker`, `comfyui-generation-worker-v6`, `brandverita-api`, or `brandverita-api-v6`. Deploying or breaking it cannot affect V5, V6, or Flux. Files delivered under `backend/phase2b/worker/` for you to copy into a new `modal-project/phase2b-research-worker/`.

## Step 3 — Server-owned outpaint pipeline

Adapter registered behind the existing flags (still false). Per job, inside a job-scoped temp dir, with a `finally` that unlinks every source/mask/output/intermediate file and the dir itself:

1. Resolve the asset through the WP0 gate only — ready, owned, `kind=input`, non-expired.
2. Download bytes via short-lived server-side signed URL; verify SHA256 against the asset row before use; abort on mismatch.
3. Compute padded canvas and mask **server-side** from `direction`/`anchor`/preset — no client geometry, no mask upload, no free text. `style_mode = preserve_source` fixes the graph's conditioning; there is no prompt field anywhere in the path.
4. Run the pinned graph on the research worker.
5. Composite the original source pixels back into their exact rectangle, unchanged.
6. Verify source-region integrity: crop the output at the computed rectangle, SHA256 it, and require an exact match against the same crop of the verified input. Mismatch → job `failed`, no asset row written.
7. Validate output bytes (WP0 `validate_output_bytes`: real image, MIME, dimensions, envelope limits), then upload to the private `generation-assets` bucket via `write_ready_output` — row goes `ready` only after upload and hash validation.
8. Write the output `generation_assets` row: `source_asset_id`, `job_id`, `workflow_key`/`workflow_version`, width/height, sha256, `kind=output`, provenance (worker version, config hash, artifact pins, preset, direction/anchor).
9. Update `generation_jobs.output_asset_id` / `output_preset` / `request_params`, and write the `transformation_eval_runs` row (timings, cold start, gpu_seconds, estimated cost, `source_region_verified`, `legal_status = pending`).

No prompt, dimensions, graph JSON, model choice, mask, batch count, or provider credential is reachable from any client.

## Step 4 — Flags stay false

`ADVANCED_WORKFLOWS_ENABLED`, `OUTPAINT_EVAL_ENABLED`, `OUTPAINT_DISPATCH_ENABLED`, and both product-scene flags remain false in the deployed config. The first controlled run is done by flipping the two outpaint-path flags for the duration of the test and setting them back. No Image Lab panel, no frontend change in WP1.

## Step 5 — Backend-only first test

Script `backend/phase2b/tests/test_wp1_outpaint.py`, run by you with `V6`, `TOK_A`, `SUPABASE_URL`:

1. Flags-off baseline: outpaint request → `403 workflow_not_available`.
2. Upload a BrandVerita-owned square asset with no edge text; confirm `ready`.
3. Flags on; submit `outpaint:v1`, preset `1200x627`, `direction=symmetric`, `anchor=center`, `style_mode=preserve_source`.
4. Poll to `completed` within the 90s p95 target; record total latency and cold-start.
5. Output dimensions exactly 1200x627.
6. Source-region crop SHA256 equals the input's crop hash (`source_region_verified = true`).
7. Lineage: output asset row has correct `source_asset_id`, `job_id`, workflow key/version, sha256, dimensions; job has `output_asset_id`.
8. Output is private: no public URL; only a short-lived signed URL after an ownership check; anonymous fetch of the storage path fails.
9. Temp cleanup: worker log shows the cleanup line and zero residual files in the job temp dir.
10. Rejections still hold: `1024x1024` preset → 400; `direction=left, anchor=left` → 400; any `prompt`/`nodes`/`image_url` key → 400.
11. Regression: V6 Flux text-to-image end-to-end unchanged; V5 `/health` healthy; WP0 suite still 28/28.
12. Flags returned to false; re-confirm check 1.

## Step 6 — Close-out

`backend/phase2b/wp1-build-manifest.md` recorded from your test output: worker revision, artifact pins, flag state, migration id, latency/cost, and rollback (delete the research app, revert the preset narrowing, flags already false — V5/V6 need no action).

## Technical notes

- Migration in WP1 is one row update on `workflow_definitions` (`allowed_output_presets`, `artifact_pins`, `worker_version`, `candidate_id`/`candidate_notes`). No schema change.
- `api.py`, `registry.py`, `jobs.py` are unchanged; WP1 lives in `advanced.py`'s adapter slot plus the new worker app.
- Rollback is deployment-isolated: removing `comfyui-research-worker-2b` restores the exact WP0 state.
