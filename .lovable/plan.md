# Deploy — Module C editorial layout (brandverita-api-v6)

**Status: READY to deploy.** All blockers are cleared. Run the deploy command,
then the health check. No code changes.

## Confirmed GOOD (from your checks)

- `editorial_presets.py`, `editorial_typography.py`, and `fonts/` are copied in —
  `presets OK` and `typography OK` pass.
- `import api` → clean, **no SyntaxError**; adapters in the safe sync shape.
- `venv310` is now aligned: Pillow 12.3.0 + modal 1.5.5 both import under
  Python 3.10 (`Pillow and Modal OK`), `modal client version: 1.5.5`, profile
  `brandverita`. The py3.8-vs-py3.10 mismatch that killed the last deploy is
  resolved.

## Deploy

```bash
cd ~/Desktop/modal-project/phase1-v6-staging
source ~/Desktop/modal-project/venv310/bin/activate
python -m modal deploy api.py
```

Use the `python -m modal` form here — it guarantees the deploy runs under
venv310's Python (with Pillow), sidestepping any leftover PATH fall-through to
the old py3.8 `venv`. The bare `modal deploy api.py` should also work now that
modal 1.5.5 lives in venv310, but the module form is deterministic.

This replaces only the `brandverita-api-v6` revision. V5 and the
`comfyui-generation-worker-v6` worker are untouched.

## Post-deploy verification

```bash
curl --fail-with-body --max-time 30 \
  https://brandverita--brandverita-api-v6-fastapi-app.modal.run/health
```

Expect `version: v6`, `app_name: brandverita-api-v6`, and in `modules` both
`editorial_layout: true` and an `editorial_layout_adapter` entry. A 200 means
the new revision started without a `ModuleNotFoundError`. Then watch the Modal
log for the new revision: no fresh `ModuleNotFoundError`, no `SyntaxError`.

```bash
# editorial presets catalog is auth-gated; expect 401 without a token
curl -s -o /dev/null -w "%{http_code}\n" --max-time 30 \
  https://brandverita--brandverita-api-v6-fastapi-app.modal.run/v1/editorial-presets
```

## Rollback

If the new revision fails health, redeploy the last-known-good `api.py` (without
the editorial additions), or stop `brandverita-api-v6` and keep Image Lab on V5.
Do NOT touch V5 or the worker.

## After the deploy (separate steps)

- Run `editorial-registry-migration.sql` in the Supabase `comfy-ui` SQL editor.
- Set the config hash: `python backend/phase2b/tools/set_config_hash.py editorial_layout v1`
  (from the workspace that has `backend/phase2b/`; needs the service-role secret).
- Run a capped editorial evaluation batch, then close BFL disclosures and decide
  Studio exposure.
