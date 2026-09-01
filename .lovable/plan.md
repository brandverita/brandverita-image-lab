# Review and revised operating model: two usable advanced features, export-ready

## 1. What the log actually shows

Confirmed from `log-sep01.txt` (brandverita-api-v6 only — the worker's own log is not in this file):

- The WP1 outpaint job `54247e4e-7ece-47a9-8d98-f1b156edfd4e` was accepted and moved to
  `processing`, then never finished. The test script polled it for its full 900s window
  (00:16 → 00:31) and gave up.
- The API background function stayed blocked until Modal killed it at 01:16 on the
  function's own 3600s timeout: `Task's current input ... hit its timeout of 3600s`.
  The `finally` block still ran — `wp1_temp_cleanup ... files_removed=3 dir_exists=False`.
- Neither `wp1_outpaint_completed` nor `wp1_outpaint_failed` was ever printed, so the hang
  is inside the one unbounded call in the adapter: `worker.outpaint.remote(canvas, mask, seed)`
  against `comfyui-research-worker-2b`. The gate, download, digest check, and geometry all
  ran before it.
- The two `ClientClosed` tracebacks at 01:16 are shutdown noise from the cancellation, not
  the cause.
- Everything else in the run behaved: check 1's 403, the three 400 rejections at 00:31
  (preset / anchor pair / injected prompt), and the Flux regression job `f0e5fcdd` at 00:31
  → 200 and polling normally. V6 Flux is unaffected.
- Two unrelated observations: one `jwks_verify_fallback type=ExpiredSignatureError` → 401
  at 00:02 (an expired Lab token, expected), and the pre-existing `AsyncUsageWarning` in the
  Flux adapter (harmless).

So WP1's API-side pipeline is proven and the worker call is the open defect. Checks 4-8 did
not pass and the WP1 manifest cannot be written yet. The root cause of the worker hang is
**not yet confirmed** — it needs the worker log — so diagnosing it is the first task below,
not a claim.

## 2. Revised operating model (your adjustments, accepted)

Given the deployment is fully isolated from Studio and `app.brandverita.io`, has no users, no
customer data, and no billing, the process changes as follows:

**Kept, because they are cheap and they are the product:**
- Server-owned geometry and parameters; no client prompt, graph, mask, or dimensions.
- Private bucket, signed URLs only, ownership checks.
- Lineage: `source_asset_id` → job → output asset, provenance and artifact pins.
- Artifact pinning with SHA256 (this is the licence and reproducibility record Studio inherits).
- Registry gating so nothing marked `research_only` can be dispatched from a Studio origin.

**Relaxed:**
- **Flags default true in staging.** The flag flip / redeploy / flip-back dance goes away.
  `ADVANCED_WORKFLOWS_ENABLED` and the two module flags stay true on `brandverita-api-v6`.
  The safety property that matters — no Studio, no production — is enforced by
  `allowed_envs = [staging]`, `registry_visibility = internal`, `production_enabled = false`,
  and the Lab allow-list, not by an env var an operator has to remember.
- **Rollback sections shrink to one line.** "Stop the research app" is the whole rollback for
  an isolated staging worker. No more per-step rollback prose.
- **Tests become a short smoke script, not a 21-check acceptance suite.** One script per
  module: submit, poll, assert dimensions + `source_region_verified` + lineage + private
  read, print latency and cost. No interactive pauses. Rejection checks run once per module,
  not per run.
- **Documentation collapses to one living file per module** instead of plan + README +
  build manifest + research manifest. Each module gets `backend/phase2b/<module>.md`:
  artifact pins, API contract, params, presets, measured latency/cost, known limits.
- **Iterate on the deployed staging API directly.** No staged approval gate between code
  and deploy for anything inside `phase2b-*` / the advanced path. V5, V6 Flux, and the
  Phase 1 worker stay off-limits without a separate decision.

**Added, because export is now the goal:**
- Every module is built as a **contract first**: a workflow key, a fixed parameter envelope,
  a fixed preset list, and one adapter. Studio replicates the *call*, never the graph.
- No credits, plan, quota, or entitlement logic anywhere in this deployment. The API records
  `usage_ledger` / `transformation_eval_runs` rows (gpu seconds, estimated cost, latency) as
  **measurements for whoever bills**, and exposes them read-only. Enforcement is
  `myaccount.brandverita.io`. Studio does operative integration only.

## 3. Task list, in order

**T1 — Unblock the outpaint worker call (must be first)**
Pull `modal app logs comfyui-research-worker-2b` for the 00:16-01:16 window and find where
`ResearchOutpaintWorker.outpaint` stopped. Then fix whichever it is, and in the same pass make
the failure mode loud instead of silent:
- bound the worker call so a hang fails the job in minutes, not at the function's 3600s ceiling
- add progress prints around ComfyUI boot, graph submit, and result fetch on the worker
- lower the API background function timeout for the outpaint path to a realistic ceiling
A job that cannot finish must end as `failed` with an `error_code`, which is also what Studio
will need to render.

**T2 — Module A: Smart Resize / Outpaint, usable**
Once a job completes: confirm exact preset dimensions, `source_region_verified = true`, and
lineage; record measured latency and cost; add the two remaining presets if the results hold;
then build the Image Lab panel (source picker → preset → direction/anchor → result with
download). Flags stay on. Write `backend/phase2b/module-a.md`.

**T3 — Module B: Product Background / Scene**
BFL as decided, adapter behind the same framework, provider key in a Modal secret only,
server-side download or provider upload — the browser never sees provider auth. Same shape:
smoke script, Lab panel, `module-b.md`.

**T4 — Export package for Studio**
One document plus the OpenAPI-shaped contract: workflow keys and versions, parameter
envelopes, preset lists, asset upload/finalize/read flow, job lifecycle and error codes,
lineage fields, and the measurement fields Studio forwards to `myaccount` for credits. Plus
what Studio must *not* implement: graphs, prompts, model choice, provider credentials.

**T5 — Promotion checklist (single gate, later)**
The one place ceremony stays: moving a workflow from `research_only`/staging to
production-enabled needs licence clearance and a production Supabase project. Not now.

## 4. Technical notes

- `advanced.py` flag helpers stay as they are; only the deployed `.env({...})` values change to
  `true` for `ADVANCED_WORKFLOWS_ENABLED`, `OUTPAINT_EVAL_ENABLED`, and later
  `PRODUCT_SCENE_EVAL_ENABLED` / `PROVIDER_BFL_ENABLED`. `OUTPAINT_DISPATCH_ENABLED` keeps its
  current meaning.
- The registry row for `outpaint:v1` stays `testing` / `research_only` / internal / staging-only
  until T5. Making a module usable in the Lab does not change its commercial status.
- `transformation_eval_runs` keeps its cost and latency columns — they become the metering
  feed for `myaccount`, so the schema stays even though the "evaluation experiment" framing
  is dropped.
- `test_wp1_outpaint.py` is superseded by the short smoke script in T2; the rejection checks
  in it (10a/10b/10c) are worth keeping as a separate one-off contract test.

## 5. One decision needed

T1 needs the worker log to name the cause. Everything else in T2-T4 is unblocked and can
proceed as described.
