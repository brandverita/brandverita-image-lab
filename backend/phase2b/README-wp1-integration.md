# WP1 integration steps — Module A Smart Resize / Outpaint

> **Superseded 2026-09-01 — read `backend/phase2b/module-a.md` first.** Two steps below
> are now obsolete: the `huggingface-research-2b` Modal secret is no longer needed (the
> checkpoint moved to an ungated repo), and the manual flag-flip pauses are gone (staging
> research flags ship ON in the `api_image`). The file-copy list and the SQL steps still apply.

Everything below is staging only and `research_only`. No Studio, no production, no customer
data, no WP2 / BFL / Replicate.

Pins and licences: `backend/phase2b/wp1-research-manifest.md` — in use:
`sd-v1-5-inpainting.ckpt` from the ungated `stable-diffusion-v1-5/stable-diffusion-inpainting`
repo, SHA256-verified at image build time, no Hugging Face token.

## 1. New files

Copy into a **new** folder `modal-project/phase2b-research-worker/`:

| From | To |
| --- | --- |
| `backend/phase2b/worker/research_worker.py` | `research_worker.py` |
| `backend/phase2b/worker/outpaint_graph.py` | `outpaint_graph.py` |

Copy into the existing `modal-project/phase1-v6-staging/`:

| From | To |
| --- | --- |
| `backend/phase2b/outpaint_geometry.py` | `outpaint_geometry.py` (new) |
| `backend/phase2b/adapters/modal_research_outpaint.py` | `adapters/modal_research_outpaint.py` (new) |
| `backend/phase2b/api.py` | `api.py` (replace) |

`advanced.py`, `registry.py`, `jobs.py`, `assets.py` are unchanged from WP0.

## 2. New Modal secret (worker only)

```bash
modal secret create huggingface-research-2b HF_TOKEN=<hf read token>
```

Used only at image build time to fetch the gated checkpoint, on
`comfyui-research-worker-2b` only. It is never attached to `brandverita-api-v6`,
never sent to a browser, and never stored in Supabase.

## 3. Deploy the research worker (isolated)

```bash
cd modal-project/phase2b-research-worker
modal deploy research_worker.py     # app: comfyui-research-worker-2b
```

First deploy downloads ~4.3 GB and verifies the SHA256; a digest mismatch fails the
build instead of shipping unknown weights. This app shares no name, image, volume,
secret or class with `comfyui-generation-worker`, `comfyui-generation-worker-v6`,
`brandverita-api`, or `brandverita-api-v6`.

## 4. Deploy the API (flags still false)

```bash
cd modal-project/phase1-v6-staging
python -c "import api"      # import check
modal deploy api.py         # brandverita-api-v6 only
curl -s .../health | python -m json.tool
```

Expect `"outpaint_adapter": "modal_research_2b"`,
`"research_worker_app": "comfyui-research-worker-2b"`,
`"advanced_flags_enabled": false`.

## 5. Flags

Keep all five false in the deployed config. The controlled test flips exactly two
(`ADVANCED_WORKFLOWS_ENABLED`, `OUTPAINT_EVAL_ENABLED`) for the duration of the run
and sets them back at the end. `OUTPAINT_DISPATCH_ENABLED` and both product-scene
flags stay false throughout WP1.

## 6. Registry

Already applied by migration: `outpaint:v1` now has
`allowed_output_presets = ["1200x627","1600x900"]`, `provider = modal_research_2b`,
`worker_version = research-2b-outpaint-1`, full `artifact_pins`, and
`candidate_id = outpaint-a-sd15inpaint-2b`. Status remains `testing`,
`commercial_status = research_only`, `registry_visibility = internal`,
`production_enabled = false`, `enabled_for_studio = false`, `allowed_envs = [staging]`.

## 7. Run the controlled test

```bash
cd backend/phase2b/tests
V6=https://brandverita--brandverita-api-v6-fastapi-app.modal.run \
TOK_A=<staging JWT> \
SUPABASE_URL=https://thspgkedjkiltrcimond.supabase.co \
ASSET=/path/to/brandverita-square-source.png \
V5=<optional v5 base url> \
python test_wp1_outpaint.py
```

The script pauses twice and tells you exactly which flags to flip. Paste the output
back and I record `backend/phase2b/wp1-build-manifest.md`.

## 8. Rollback

1. Set both flags false (already the default) — advanced requests 403 immediately.
2. `modal app stop comfyui-research-worker-2b` / delete the app; V5, V6 and Flux are
   untouched by design.
3. Optional: revert `allowed_output_presets` to the five WP0 presets and clear
   `artifact_pins` / `candidate_id`.
4. Optional: redeploy the WP0 revision of `api.py`.

## 9. Note on the linter output from the migration

The four findings are pre-existing and unrelated to this data-only change:
`workflow_definitions` and `allowed_emails` intentionally have RLS enabled with no
client policies (backend/service-role only — that is the security property, not a
gap), `is_email_allowed` is a `SECURITY DEFINER` allow-list helper the RLS policies
depend on, and leaked-password protection is an Auth dashboard setting you can enable
under Authentication → Policies whenever you like.
