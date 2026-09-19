# Module C — remaining deployment steps

**Status: editorial module deployed and healthy; registry row inserted.** Working
through the final steps.

## Done

- `advanced.py` swapped to the current 780-line version, cache cleared, redeployed.
  Health: `modules {outpaint, product_scene, editorial_layout}` all `true`;
  `editorial_layout_adapter: bfl_editorial_layout`.
- Registry migration run — `editorial_layout:v1` inserted (`testing` /
  `research_only` / `internal`, staging-only). It now appears in the health
  `workflows` list.

## Step 2 — Config hash (you, on the Mac) — directory correction

**Not from `phase1-v6-staging`.** That folder only holds the Modal deploy files;
the script isn't in it. It lives in the project repo at
`backend/phase2b/tools/set_config_hash.py`. The script imports only `httpx`
(already in `venv310` — `assets.py` uses it and imported fine) and reads nothing
else from the repo, so the working directory barely matters — just point Python
at the real script path.

```bash
# cd to the project repo root — the folder that contains backend/phase2b/tools/
cd <path-to-the-project-repo>

# venv310 active; set the two env vars inline (service-role key stays on your machine)
SUPABASE_URL=https://thspgkedjkiltrcimond.supabase.co \
SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key> \
python backend/phase2b/tools/set_config_hash.py editorial_layout v1
```

- Expected output: `editorial_layout:v1 config_hash=<64 hex chars>`.
- It must be this Python script, not SQL — the API recomputes the hash per request
  with Python's compact, key-sorted JSON, and a SQL-encoded value trips the
  `config_hash_mismatch` tripwire.
- The service-role key is a powerful secret — keep it local, don't paste it here.
  If you ever see `No module named httpx`, run `python -m pip install httpx` first.

## Step 3 — Capped evaluation batch (you)

Run a few editorial jobs from the Lab "Editorial layout" tab, score them (subject
changed / text unreadable), and confirm rows appear under `editorial_layout` in
the comparison table. Respect the $10 research spend cap.

## Step 4 — Close-out

BFL disclosures, then decide Studio exposure (separate approval).

## Note

`roadmap.md` Track I can't be updated right now (plan mode locks all files except
this plan). I'll mark the deploy + migration steps done once we're in build mode.
