# The log shows the test is near the end, not stuck

Reading the sequence in the API log:

```text
3 x POST /v1/generations -> 400      = checks 10a, 10b, 10c (disallowed preset,
                                       invalid direction/anchor pair, injected prompt)
1 x POST /v1/generations -> 200      = check 11a, the Flux regression job
GET  /v1/generations/f0e5fcdd... x7  = the script polling that Flux job every 2s
```

The `AsyncUsageWarning` comes from `adapters/modal_comfyui.py` — the Flux adapter — which
confirms the 200 is the text-to-image regression probe, not an outpaint request. The three
400s are the rejection checks passing, and they can only run after the outpaint job reached
`completed` and checks 5 through 9 executed. So the outpaint run finished; the terminal simply
prints all of it at once as it goes.

Nothing to do but let it finish. Remaining: the Flux poll completes (check 11a), the optional
V5 health check (11b, skipped unless `V5` was set), then the script pauses and asks you to set
both flags back to `false`.

## Final step when it pauses

1. In `phase1-v6-staging/api.py`, set `ADVANCED_WORKFLOWS_ENABLED` and `OUTPAINT_EVAL_ENABLED`
   back to `"false"` in the `.env({...})` block.
2. `modal deploy api.py`
3. Confirm `/health` reports `"advanced_flags_enabled": false`.
4. Press Enter. Check 12 verifies the 403 returns.

## Then paste for the build manifest

- The full script output, including the scroll-back for checks 4 through 9 and the latency line.
- The two SQL result sets the script printed: the `generation_assets` row (`source_region_sha256`,
  `classification`) and the `transformation_eval_runs` row (`source_region_verified`,
  `provider_latency_ms`, `total_latency_ms`, `gpu_seconds`, `estimated_cost`, `cold_start`).
- The two cleanup log lines: `wp1_temp_cleanup ... dir_exists=False` from the API and
  `wp1_worker_cleanup files=... dir_removed=1` from `comfyui-research-worker-2b`.

## Note on the async warning

`modal_comfyui.py` calls `_dispatcher.spawn(...)` synchronously inside FastAPI's async
handler. It is pre-existing V6 Flux behaviour, harmless, and unrelated to WP1 — Flux returned
200 and dispatched normally. Switching it to `await spawn.aio(...)` is a small optional
cleanup for a later pass; it is deliberately not touched during a test run whose whole point
is that the Flux path is unchanged.
