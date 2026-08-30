# WP0: the 25/28 run used the pre-fix files, not the amended ones

The three failures are the exact same three as before the fix, and the output shows two signs that the run did not exercise the amended code:

1. **Check 17's label in your log is `no research_only/requires_source_asset row is reachable`.** The amended test in this project reads `... is reachable from Studio` and calls `GET /v1/workflows?origin=studio`. Your log's label (and the fact that it printed a full internal row) is the old test body, which read the default Lab-origin list — where an allow-listed operator seeing the internal research row is intended behaviour.
2. **Check 3 still returns `workflow_unavailable: workflow 'outpaint:v1' is not active`.** That string can only come from `registry.assert_dispatch_allowed` running *before* the advanced gate. The amended `backend/phase2b/api.py` (lines 394–410) runs `advanced.resolve_advanced_request` first for `requires_source_asset` rows, so it must answer `workflow_not_available`. `/health` does not distinguish the two revisions — `advanced_framework: true` was already true in the previous deploy.

`backend/phase2b/api.py` and `backend/phase2b/registry.py` in this project are correct as delivered (gate reorder present, `?origin=studio|lab` param present, Studio filter delegated to `advanced.studio_safe_row`). Nothing further needs changing in them.

## Steps for you

1. Copy the current `backend/phase2b/api.py` into `modal-project/phase1-v6-staging/api.py`, overwriting. Confirm with:
   `grep -n "resolved_origin\|requires_source_asset" api.py` — you should see `resolved_origin` in `list_workflows` and the `if row.get("requires_source_asset"):` branch above `assert_dispatch_allowed`.
2. Confirm `registry.py` on the Modal side contains `advanced.studio_safe_row` (`grep -n studio_safe_row registry.py`).
3. `python -c "import api"`, then `modal deploy api.py`.
4. Confirm the new routing is live without a token:
   `curl -i "https://brandverita--brandverita-api-v6-fastapi-app.modal.run/v1/workflows?origin=studio"` — a 401 is fine; a 422 would mean the old build (unknown query param handling differs) — the definitive check is step 5.
5. Copy the current `backend/phase2b/tests/test_wp0_framework.py` over your local copy, overwriting. Confirm with `grep -n "origin=studio" test_wp0_framework.py` (should match twice: the request and the checks).
6. Re-run with `V6`, `TOK_A`, `TOK_B`, `SUPABASE_URL` set. Expected: 28/28, with check 3 reporting `workflow_not_available`.

## If check 3 still fails after a confirmed redeploy

Then the deployed `advanced.py` is refusing before returning the framework error, or `advanced.py` is stale on the Modal side. Paste the full JSON body of check 3 and I will trace it against `backend/phase2b/advanced.py` — no guessing.

## Close-out

Once your output shows 28/28 I write `backend/phase2b/wp0-build-manifest.md` (deployed revision, flag values, migration id, test result, rollback). WP1 and WP2 still require your separate approval.
