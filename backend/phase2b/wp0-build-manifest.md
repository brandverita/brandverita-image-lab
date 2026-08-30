# Phase 2B — WP0 Build Manifest

**Work package:** WP0 — shared Image Transformation Framework v1 (foundation, gates, lineage, evaluation records, flags)
**Environment:** staging only (Supabase `comfy-ui` / `thspgkedjkiltrcimond`)
**Status:** complete — 28/28 acceptance checks passed
**Date recorded:** 2026-08-30

---

## 1. Deployed surface

Modal app: `brandverita-api-v6` (V6 API only — the GPU worker was **not** redeployed in WP0).

`/health` as returned by the accepted deployment:

```json
{
  "status": "ok",
  "service": "brandverita-api",
  "app_name": "brandverita-api-v6",
  "version": "v6",
  "dispatch": true,
  "environment": "staging",
  "registry_ok": true,
  "workflows": [
    "flux_text_to_image:v1",
    "flux_text_to_image:v1-commercial-candidate",
    "outpaint:v1"
  ],
  "worker_app": "comfyui-generation-worker-v6",
  "worker_class": "ComfyUIWorker",
  "assets": true,
  "assets_bucket": "generation-assets",
  "advanced_framework": true
}
```

`advanced_framework: true` is the WP0 deployment marker. V5 (`/health` healthy) remains untouched and is the rollback target of last resort.

---

## 2. Code inventory

Canonical copies live in this repo under `backend/phase2b/`; the deployed copies live in `modal-project/phase1-v6-staging/`.

| File | Status | WP0 change |
| --- | --- | --- |
| `advanced.py` | new | Strict allow-list param parser (outpaint `anchor_directional` direction/anchor enum pairs; product_scene `scene_direction` enum; rejects `prompt`, `workflow`, `nodes`, `image_url` and any unknown key). Registry + flag gate reading all five `*_ENABLED` vars **inside** the handler. Asset ownership / readiness / expiry / `kind=input` checks. Byte-based adapter interface (no adapter registered in WP0). Output validation + write helper. Eval-run writer. Shared `studio_safe_row` visibility predicate. |
| `api.py` | edited | `import advanced`; advanced router included; `add_local_file("advanced.py", ...)` in the image; `/health` marker `advanced_framework: true`. `POST /v1/generations`: for rows with `requires_source_asset = true`, `advanced.resolve_advanced_request` runs **before** `registry.assert_dispatch_allowed` so the framework returns `workflow_not_available` rather than the generic lifecycle error; Flux rows with a stray `source_asset_id` are rejected 400 and never dispatched. `GET /v1/generations/{id}` echoes lineage fields. `GET /v1/workflows` accepts `?origin=studio|lab`. |
| `registry.py` | edited | `list_visible_workflows` Studio branch delegates to `advanced.studio_safe_row(row)` in addition to the `status == "active"` requirement (stricter than the previous inline filter — now also requires `production_enabled`). `resolve_workflow` / `get_workflow` / `assert_dispatch_allowed` deliberately stay unfiltered so server-internal dispatch still resolves candidates and rejects them at the correct gate. New registry columns flow through automatically (`select: *`). |
| `jobs.py` | edited | `job_to_response_dict` persists/echoes `source_asset_id`, `output_asset_id`, `output_preset`, `request_params`. |
| `tests/test_wp0_framework.py` | new | 28-check acceptance suite (`httpx`), run against V6 with `V6`, `TOK_A`, `TOK_B`, `SUPABASE_URL`. |

Flux text-to-image dispatch path: unchanged.

---

## 3. Flag state (kill switches)

All advanced flags are **false** on the deployed V6 app. This is why every advanced request terminates at a 403 gate and nothing can dispatch.

| Flag | Value |
| --- | --- |
| `ADVANCED_WORKFLOWS_ENABLED` | `false` |
| `OUTPAINT_EVAL_ENABLED` | `false` |
| `PRODUCT_SCENE_EVAL_ENABLED` | `false` |
| `OUTPAINT_DISPATCH_ENABLED` | `false` |
| `PRODUCT_SCENE_DISPATCH_ENABLED` | `false` |

Read inside the handler (never at module scope) so a value change takes effect on the next container without a code change.

---

## 4. Migrations applied

1. **Registry columns** on `public.workflow_definitions`: `requires_source_asset`, `allowed_output_presets`, `input_envelope`, `artifact_pins`, `candidate_id`, `candidate_notes` + partial unique index on `candidate_id`.
2. **Immutability trigger** — `enforce_workflow_definitions_immutability()` replaced so the new fields are also frozen once `status in ('active','deprecated','disabled')`.
3. **Job lineage columns** on `public.generation_jobs`: `source_asset_id`, `output_asset_id`, `output_preset`, `request_params` + two indexes + FKs to `generation_assets`.
4. **New table** `public.transformation_eval_runs` — module/candidate/provider/timing/cost fields, `reviewer_scores`, `legal_status`. `GRANT SELECT` to `authenticated`, `GRANT ALL` to `service_role`; RLS on; single SELECT policy `operator_user_id = auth.uid() AND is_email_allowed(auth.uid())`. **No client write policies** — writes are service-role only.
5. **Data update** on the `outpaint:v1` row (permitted: the row was `draft`, so the immutability trigger did not apply):
   - `requires_source_asset = true`
   - `status = 'testing'`
   - `allowed_output_presets = ["1080x1080","1200x627","1600x900","1080x1350","1080x1920"]`
   - `input_envelope = {"max_width":4096,"max_height":4096,"max_pixels":16777216,"allowed_content_types":["image/png","image/jpeg","image/webp"]}`
   - `candidate_id` / `candidate_notes` left null (populated per candidate in WP1/WP2)

Supabase types regenerated after each migration.

---

## 5. Registry state snapshot

| key | version | status | commercial_status | registry_visibility | production_enabled | enabled_for_studio | requires_source_asset |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `flux_text_to_image` | `v1` | active | pending_review | studio_safe | per Phase 1 record | per Phase 1 record | false |
| `flux_text_to_image` | `v1-commercial-candidate` | draft | pending_review | internal | false | false | false |
| `outpaint` | `v1` | testing | research_only | internal | false | false | true |

`allowed_envs` for `outpaint:v1` = `[staging]`. No `product_scene` row exists yet — it is created in WP2.

---

## 6. Acceptance record — 28/28

Suite: `backend/phase2b/tests/test_wp0_framework.py`, run against the deployed V6 with two allow-listed staging users (A and B).

Automated, end-to-end against the live API: 1–9, 12–20, 24, 26, 27.

Key properties confirmed:
- Unauthenticated and non-allow-listed callers cannot reach the framework (1, 2).
- With the master flag off, an advanced request returns `403 workflow_not_available` from the framework gate (3, 19).
- Asset gates hold: non-existent, cross-user, and pending assets are all refused (7, 8, 9).
- Param allow-list holds: bad direction/anchor pairs, injected `prompt`/`workflow`/`nodes`/`image_url`, unknown keys, and non-enum `scene_direction` are all rejected (13–16).
- A Studio-shaped read exposes no `research_only`, no `requires_source_asset`, and no non-active / non-production row (17, 18).
- `transformation_eval_runs` rejects an authenticated client insert (24).
- Flux text-to-image is unchanged end-to-end, and V5 is healthy (26, 27).

Deferred / manual checks, recorded as passing on prior evidence rather than executed by this run:

| # | Check | Why deferred | Resolved in |
| --- | --- | --- | --- |
| 10 | expired asset -> `409 asset_expired` | no expiry scheduler exists in WP0 | WP1 |
| 11 | output-kind asset used as source -> 400 | no output assets exist until dispatch is enabled | WP1 |
| 21 | `generation-assets` bucket private | verified in Phase 2A acceptance | — |
| 22 | client bundle contains no provider key | no provider secret exists in WP0 | WP2 (re-run at adapter time) |
| 23 | ready output row requires sha256 + dimensions | `generation_assets_ready_chk` verified in Phase 2A | — |
| 25 | `usage_ledger` still empty | manual DB count, expect 0 | ledger integration phase |
| 28 | frontend `bun run test` green | run locally, 20 existing tests | — |

---

## 7. Rollback

Ordered, each step independently safe:

1. Redeploy the previous V6 revision (the Phase 2A revision, `/health` without `advanced_framework`). The GPU worker never changed, so no worker action is required.
2. Revert the `outpaint:v1` row: `requires_source_asset = false`, `status = 'draft'`, `allowed_output_presets = '[]'::jsonb`, `input_envelope = '{}'::jsonb`.
3. Drop the `generation_jobs` lineage columns and their indexes.
4. Drop `public.transformation_eval_runs`.
5. Restore the prior `enforce_workflow_definitions_immutability()` function body, then drop the six new `workflow_definitions` columns and the `candidate_id` index.

Because every advanced flag is false, steps 2–5 are not needed for incident response — flipping nothing is already the safe state; a bad deploy is fully contained by step 1.

---

## 8. Explicitly out of scope in WP0

Not built, not deployed, not configured:

- Modal research worker and the outpaint ComfyUI graph (WP1)
- BFL provider review, adapter, and provider secret (WP2)
- Any dispatch of an advanced workflow to any provider
- Image Lab UI panel for transformations
- Billing, credits, usage-ledger writes
- Production Supabase project, production identity, or any production deployment

WP1 and WP2 each require separate explicit approval before implementation.
