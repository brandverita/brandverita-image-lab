# Fix — Module C editorial flag reads off (stale advanced.py)

**Status: diagnosed and confirmed by your screenshot. One stale file to replace,
then redeploy. No code changes needed.**

## Diagnosis (confirmed)

Your Finder screenshot settles it: `advanced.py` in `phase1-v6-staging/` is dated
**11 September** and its docstring opens with *"Phase 2B WP0 — shared Image
Transformation Framework v1"* — that's the pre-Module-C version. The Module C
work (the editorial branch in `module_flag`, `parse_editorial_params`, and
`SCORE_MODULES`) landed **today, 19 September**, so your Sep-11 copy doesn't
have it.

That is exactly why health reads:
- `outpaint: true`, `product_scene: true` — the Sep-11 file DOES know these two switches.
- `editorial_layout: false` — it has no editorial branch, so `module_flag("editorial_layout")` falls through to `False`.

All environment flags are set correctly (the shared image env proves it — the
other two modules read `true`). The adapter deployed fine and
`run_editorial_layout_job` is live. The only problem is this one stale file.

Everything else on your Mac is current — the Finder listing shows
`editorial_presets.py`, `editorial_typography.py`, `fonts/`, `prompt_layers.py`,
and `stale_jobs.py` all present. **`advanced.py` is the only stale file.**

## The fix

The current `advanced.py` is 780 lines and imports only siblings you already
have (`assets`, and lazily `editorial_presets` / `editorial_typography`), so it
drops straight in.

### 1. Get the current advanced.py onto the Mac

Either:
- **Repo pull** — if your local clone tracks the connected repo, `git pull` and
  use its `backend/phase2b/advanced.py`. Confirm it's the 780-line version
  (`grep -n "editorial_layout" advanced.py` should return several hits), or
- **I paste it** — tell me and I'll output the full current file to save as
  `phase1-v6-staging/advanced.py`.

Then:

```bash
cp <path-to-current>/advanced.py ~/Desktop/modal-project/phase1-v6-staging/advanced.py
```

### 2. Clear cache, verify, redeploy

```bash
cd ~/Desktop/modal-project/phase1-v6-staging
find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null
python -c "import advanced; print('editorial flag:', advanced.module_flag('editorial_layout'))"
# expect: editorial flag: True
python -m modal deploy api.py
```

Run the `python -c` check before deploying — it must print `True`.

### 3. Post-deploy health check

```bash
curl --fail-with-body --max-time 30 \
  https://brandverita--brandverita-api-v6-fastapi-app.modal.run/health
```

Expect `modules.editorial_layout: true` (outpaint/product_scene stay `true`).

## After the flag reads true (separate steps)

- Run `editorial-registry-migration.sql` in the Supabase `comfy-ui` SQL editor —
  this adds `editorial_layout:v1` to the `workflows` list in health.
- Set the config hash: `python backend/phase2b/tools/set_config_hash.py editorial_layout v1`
  (from the workspace with `backend/phase2b/`; needs the service-role secret).
- Run a capped editorial evaluation batch, then close BFL disclosures and decide
  Studio exposure.

## Rollback

If anything regresses, redeploy the prior `api.py` (editorial is additive and
staging-only; V5 and the worker are untouched).
