# Add observability: make future stalls obvious without a DB query

## Why

The multi-day debug saga came down to two invisible states: "which API build is live" and "did the worker ever get dispatched". Both are already knowable from `/health` and the job row, but the frontend surfaces neither — `checkHealth()` discards the version, and `modal_call_id` never leaves the database. This plan puts both on screen so the next stall is diagnosed in seconds, not hours.

## Current state (verified)

- `GET /health` returns `{"status":"ok","service":"brandverita-api","version":"v4","dispatch":true,"worker_app":"comfyui-generation-worker","worker_class":"ComfyUIWorker"}`.
- `src/lib/generationApi.ts` `checkHealth()` reads only `body.status === "ok"` and returns a boolean. Version/dispatch/worker info is discarded.
- `JobResponse` (api_v4.py line 153) includes `output_path` but **not** `modal_call_id`.
- `job_to_response` (line 471) likewise omits `modal_call_id`.
- The DB column `modal_call_id` exists and is written after `spawn` (line 576), with `"spawned"` as the fallback so NULL uniquely means "spawn never returned".
- `GenerationJob` interface (generationApi.ts line 36) has no `modal_call_id` or `output_path` field.
- `DeveloperPanel` (ResultPanel.tsx line 38) shows Job ID, Workflow, Status, Progress, Seed, Elapsed, Error code — no dispatch or output info.
- `HealthState` (index.tsx line 47) is `"checking" | "ok" | "unreachable" | "not_configured"` — carries no version.

## Changes

### 1. Backend — expose `modal_call_id` (api_v5.py → deploy as api.py)

Two small additions, no behavior change:
- Add `modal_call_id: Optional[str] = None` to the `JobResponse` model.
- In `job_to_response`, set `modal_call_id=job.get("modal_call_id")`.

No route logic changes. `/health` already reports version/dispatch, so nothing else is needed there.

### 2. Frontend — surface API version + dispatch health

In `src/lib/generationApi.ts`:
- Replace `checkHealth(): Promise<boolean>` with `checkHealth(): Promise<HealthInfo | null>` where `HealthInfo = { ok: boolean; version?: string; dispatch?: boolean; workerApp?: string; workerClass?: string }`. Parse the full `/health` body.
- Add `modal_call_id?: string | null` and `output_path?: string | null` to the `GenerationJob` interface.

In `src/routes/index.tsx`:
- Carry the `HealthInfo` in state instead of a bare boolean.
- Header: show the API version next to the status dot (e.g. "Generation API online · v4"). If `dispatch` is false, show a warning badge "dispatch off" (the single most important red flag — it means jobs will never run).
- Footer: show the worker app/class (`comfyui-generation-worker / ComfyUIWorker`) so the dispatch target is visible, not just the environment label.

### 3. Frontend — surface dispatch + output in the developer panel

In `src/components/generation/ResultPanel.tsx` `DeveloperPanel`:
- Add rows: "Modal call ID" (shows `modal_call_id` — `—` if absent, which after the v4 deploy uniquely means spawn never returned), and "Output path" (shows `output_path` once the image is stored).
- Keep `—` as the absent sentinel so a blank never looks the same as "dispatched".

### 4. Frontend — manual "Check now" action while polling

In `src/hooks/use-generation.ts`:
- Expose a `checkNow()` callback that forces an immediate poll (skips the 2s `setTimeout`) without cancelling or retrying. Useful when a job looks stuck and the user wants a fresh status without waiting or re-submitting.
- Wire a "Check now" button into `ResultPanel`'s loading state (next to the status text), only visible while `phase === "submitting" || "polling"`.

## Out of scope

- No RecentJobs thumbnail (the DB `result_url` is NULL by design — the API signs dynamically — so a thumbnail needs an API call per row, a separate change).
- No Netlify rebuild in this plan (still needed to fix the recent-jobs 403, but it's a deploy action, not code).
- No new DB columns or migrations.

## Technical notes

- All `/health` fields are non-secret; safe to render. No tokens, prompts, or URLs are exposed.
- `modal_call_id` values are either a Modal object id, the literal `"spawned"`, or NULL — all safe to display.
- The version string in the header is the same signal that resolved the v2-vs-v4 ambiguity, so it stays visible permanently.
