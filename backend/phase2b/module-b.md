# Module B — Product Background / Scene (living doc)

Status: **implemented, staging research only** (WP2). Provider: Black Forest Labs
(`flux-kontext-pro`). Registry row: `product_scene:v1`, `status=testing`,
`commercial_status=research_only`, `registry_visibility=internal`,
`allowed_envs={staging}`, `production_enabled=false`, `enabled_for_studio=false`.

## What it does

One server-owned transformation: replace the background of a single-product
image with one of four fixed scenes, at one of four absolute output sizes.

Client may send exactly:

```json
{
  "workflow_id": "product_scene:v1",
  "source_asset_id": "<uuid of a ready, owned input asset>",
  "output_preset": "1080x1080 | 1080x1350 | 1200x627 | 1600x900",
  "params": {
    "scene_direction": "clean_studio | premium_neutral | warm_lifestyle | natural_surface",
    "background_style": "neutral | soft_shadow | high_key | editorial",
    "preserve_subject": true
  },
  "idempotency_key": "<uuid>"
}
```

Anything else is refused: `prompt`, `negative_prompt`, `image_url`, `width`,
`height`, graph/JSON fields are in `advanced.FORBIDDEN_KEYS`, and any unknown key
fails the allow-list parser before storage or the provider is touched.

## Where the words come from

`scene_presets.py` (server image) holds every instruction string. The request
only selects an enum; the assembled instruction is hashed and recorded in
provenance (`scene_preset.instruction_sha256`, `preset_table_version`). The text
itself is never returned to a client and never logged. Changing a preset is a
code change plus a registry version bump.

## Execution order (adapters/bfl_product_scene.py)

1. Re-run the framework gate at dispatch time (flags, ownership, readiness,
   expiry, strict enums).
2. Check `HOSTED_PROVIDER_DISPATCH_ENABLED` **and** `PROVIDER_BFL_ENABLED`.
3. Download the source server-side, verify SHA256 against the asset row.
4. Build the instruction from the preset table.
5. Call BFL with the image inlined as base64 — never a signed Supabase URL, and
   the browser never receives provider auth.
6. Fetch the provider result server-side; cover-fit to the exact preset size.
7. Validate → upload → hash → write the `ready` output asset row with lineage.
8. Delete every temp file in `finally`.
9. Patch the job and write the `transformation_eval_runs` row.

Bounds: submit 60s, poll every 2s, provider deadline 300s, Modal function
timeout 900s. A stuck provider fails the job with a real error code instead of
hanging (the WP1 lesson).

## Honest limitation

Unlike outpaint there is no byte-exact region to verify — the provider
re-renders the whole frame. Per run we record `source_region_verified = null`
and `provenance.subject_preserved = "unverified"`. Subject fidelity is judged by
human review (founder + independent reviewer) against the Phase 2B rubric, which
is why the row stays `research_only`.

## Credential

Modal secret `bfl-research-2b` → `BFL_API_KEY`. Attached **only** to the
`run_product_scene_job` function, never to the web app or the worker apps. The
key is never echoed, logged, or returned; a missing key raises
`provider_credential_missing` with no key material in the message.

## Cost and metering

Recorded estimate `$0.04`/image in `transformation_eval_runs.estimated_cost`,
alongside `provider_latency_ms`, `total_latency_ms` and `provider_request_id`.
Research spend cap for WP2: **$10**. Enforcement of credits, plan allowance and
privileges belongs to myaccount.brandverita.io — this deployment only records.

## Flags (staging steady state: ON)

| Flag | Staging | Effect when false |
| --- | --- | --- |
| `ADVANCED_WORKFLOWS_ENABLED` | true | all advanced requests → 403 |
| `PRODUCT_SCENE_EVAL_ENABLED` | true | Module B → 403 |
| `MODULE_B_ENABLED` | true | informational marker |
| `HOSTED_PROVIDER_DISPATCH_ENABLED` | true | no request leaves the deployment |
| `PROVIDER_BFL_ENABLED` | true | BFL specifically blocked |

Isolation does not depend on these flags — it comes from the registry row and
the Lab allow-list. The flags are the fast kill switch: flip
`HOSTED_PROVIDER_DISPATCH_ENABLED` to `false` and redeploy to stop all hosted
spend immediately.

## Test

`backend/phase2b/tests/test_wp2_product_scene.py` — 16 checks: gate rejections,
enum-only catalog, end-to-end job, exact preset size, lineage, private storage,
instruction non-leakage, Flux regression, studio invisibility.

## Export note for Studio

The contract Studio replicates is exactly the request body above plus
`GET /v1/scene-presets` for the option catalog. Studio never sees provider
names, instruction text, or asset storage paths — only enum keys, labels, job
state and short-lived signed URLs.
