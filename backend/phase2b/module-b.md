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

---

## WP2 acceptance — 2026-09-05 (ACCEPTED)

Module B passed the full suite **18/18, twice** (initial run + rerun after the
eval-recording fix), against the staging deployment only.

### Defect found and fixed during acceptance

The first 18/18 run produced no `transformation_eval_runs` row. Root cause:
`adapters/bfl_product_scene.py` wrote the provider reference under the key
`provider_request_id`, but the table column is `provider_call_id`; PostgREST
rejected the insert and `advanced.write_eval_run` swallowed the error by design.
Fixes: renamed the eval-row key, and `write_eval_run` now prints
`wp_eval_run_write_failed status=<code> body=<first 300 chars>` on failure so a
schema/key mismatch is visible in Modal logs. Rerun confirmed the row lands.

### Registry row

`product_scene:v1` — `status=testing`, `commercial_status=research_only`,
`registry_visibility=internal`, `allowed_envs={staging}`,
`production_enabled=false`, `enabled_for_studio=false`,
config_hash `4dfc6a2a...afea43`.

### Provider pin

BFL `flux-kontext-pro`, $0.04/image estimate, credential in Modal secret
`bfl-research-2b` attached only to the product-scene background function.

### Latency

| Run | Total | Provider |
| --- | --- | --- |
| 1 (first call) | 162.7s | — |
| 2 (warm) | 16.7s | 9.3s |

The first-call figure was provider/adapter warm-up; both samples are within the
p95 ≤ 90s target. p95 confidence still needs more samples over time.

### Evidence (rerun, 2026-09-05)

Asset row `d54e0700-63a8-42e5-88cf-ff0cca8e745d`:

- kind=output, status=ready, source_asset_id `a1db7262-7aba-4ff7-b77c-dbbf81027276`,
  job_id `ff911678-bc2b-4cd1-8b36-9fc3bafcfc26`
- sha256 `281c2a13e76cee7a28bc7b2194ca096ea0fc1623d5a89cff4263ec6b856dfeb9`, 1080x1080
- instruction_sha256 `a1eb5a26acdf1810cba8c03d9048ca82b918c64a5681f701814c996a6575fe64`
- subject_preserved=unverified, classification=research_only/staging

Eval row for job `ff911678-bc2b-4cd1-8b36-9fc3bafcfc26`:

- module=product_scene, provider=bfl_product_scene, status=completed
- output_preset=1080x1080, provider_call_id `f9826009-bf7f-46c6-819e-af4209ba26a5`
- provider_latency_ms=9251, total_latency_ms=16729, estimated_cost=$0.04
- source_region_verified=null (expected — not byte-verifiable for this module)
