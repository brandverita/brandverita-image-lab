# How to flip the two WP1 flags for the controlled test

The test script is paused waiting for `ADVANCED_WORKFLOWS_ENABLED` and `OUTPAINT_EVAL_ENABLED`
to be true on `brandverita-api-v6`.

## Where the flags come from

`advanced.py` reads them with `os.environ.get(...)`, defaulting to false. The deployed
`api.py` sets no env values anywhere, so both are currently false — which is exactly why
check 1 passed. All three Modal functions (the web app, the generation background function,
and the outpaint background function) share the single `api_image`, so one env layer on the
image covers every path.

## Turn them on (temporary, for the duration of the run)

In `phase1-v6-staging/api.py`, add one `.env(...)` call at the end of the `api_image` chain,
immediately after `.add_local_dir("adapters", "/root/adapters", copy=True)`:

```python
    .env({
        "ADVANCED_WORKFLOWS_ENABLED": "true",
        "OUTPAINT_EVAL_ENABLED": "true",
        "OUTPAINT_DISPATCH_ENABLED": "false",
        "PRODUCT_SCENE_EVAL_ENABLED": "false",
        "PROVIDER_BFL_ENABLED": "false",
        "PROVIDER_REPLICATE_ENABLED": "false",
    })
```

The three false flags stay false throughout WP1. Then, in a second terminal (leave the test
script paused — do not press Enter yet):

```bash
cd ~/Desktop/modal-project/phase1-v6-staging
modal deploy api.py
curl --fail-with-body --max-time 30 \
  https://brandverita--brandverita-api-v6-fastapi-app.modal.run/health
```

Wait for `"advanced_flags_enabled": true` in the health payload before returning to the test
terminal and pressing Enter. Pressing Enter early makes check 3 fail with a 403.

Note: this rebuilds the image layer above the copies, so the deploy is fast but not instant.
The first outpaint job will also be a cold start on the research worker — the script expects
that and prints the latency separately.

## Turn them back off at the end

The script pauses a second time (step 12) and asks for the flags to be false. At that point,
edit the same block back to `"false"` for both, redeploy, confirm `/health` reports
`"advanced_flags_enabled": false`, then press Enter. Check 12 verifies the 403 returns.

The deployed steady state for WP1 is all five flags false — the flag-on window exists only
for the duration of this test run.

## After the run

Paste the full script output plus the two SQL result sets it prints (the
`generation_assets` row and the `transformation_eval_runs` row) and the two cleanup log
lines, so the WP1 build manifest can be recorded.
