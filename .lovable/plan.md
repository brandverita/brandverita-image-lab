# Smart resize fails in Studio — find the real cause, then fix it

Upload, options and dispatch all work now. The job itself is failing inside the
resize worker: "The transformation could not be completed." is the generic
client message the outpaint adapter writes whenever anything in the pipeline
raises. The real reason is already recorded server-side (exception detail plus a
full traceback in the Modal log, and the exception string in the evaluation
record), but it is deliberately not sent to the browser. So the cause is not yet
confirmed — step 1 confirms it instead of guessing.

## Step 1 — read the two facts that name the cause (no changes)

In the Supabase SQL editor of the staging project:

```sql
select job_id, status, error_code, error_message, provider_latency_ms,
       total_latency_ms, source_region_verified, gpu_seconds, worker_version,
       created_at
from transformation_eval_runs
order by created_at desc
limit 5;
```

`error_message` on the newest failed row carries the exception text.

Then, on the machine with Modal access:

```bash
modal app logs brandverita-api-v6 | grep -E "wp1_outpaint_(stage|failed)"
modal app logs comfyui-research-worker-2b | tail -n 200
```

The shape of the logs separates the candidates:

| What the logs show | Meaning |
| --- | --- |
| no worker container started | failed API-side before dispatch: asset download, SHA256 verify, or geometry |
| worker boot then traceback | ComfyUI/checkpoint problem in the research worker |
| boot ready, then graph error | graph/node rejection |
| stage log stops at upload | output write/storage step |

Because Supabase JWT keys were just rotated, a plausible API-side candidate is
the server-side asset download or storage write now failing with the old key —
the log will show this as a storage/auth error rather than a GPU error. Do not
assume it; the row and the log decide.

## Step 2 — fix the confirmed cause

Applied only after step 1 names it. Expected to be a one-place fix inside the
staging Modal app (adapter, worker, or the service credentials it reads). No
registry change, no Studio-side change, no change to Flux or Product Scene.

## Step 3 — verify

Re-run `backend/phase2b/tests/test_wp1_outpaint.py` (target 17/17), then repeat
the same Smart resize from Studio with the same image and 1200 x 627 preset and
confirm a result image and a `completed` row at the exact preset size.

## Notes

- Studio's own behaviour is correct here; nothing to change on their side yet.
- Registry stays testing / research_only / internal / staging-only.
- What I need from you: the SQL result set and the grep output from step 1.
