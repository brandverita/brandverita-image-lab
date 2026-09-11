# Answer for Studio + one required gate fix

## Direct answer to the Studio team

**POST /v1/generations: send nothing.** No `origin` in the body, no query parameter, no header. The endpoint does not read an origin value at all.

- `origin=studio` is only used on **GET /v1/workflows?origin=studio** (discovery). That one stays as-is.
- On POST, the dispatch gate runs with origin fixed to `lab` and the environment fixed to `staging`, so the commercial check is enforced by the registry row itself (status + allowed_envs + production_enabled), not by anything the client sends.
- Consequence: `flux_text_to_image:v2` (Generate image) dispatches from Studio **today, with no change**, as long as the request names `workflow_id: "flux_text_to_image"` + `workflow_version: "v2"` and the caller's token verifies.

## The gap: Smart Resize v3 would be rejected

`outpaint:v3` requires a source asset, so it goes through the advanced gate (`advanced.resolve_advanced_request`). That gate currently only admits **research** rows and refuses anything else:

- `commercial_status != "research_only"` → refused
- `registry_visibility != "internal"` → refused
- `status not in ("draft", "testing")` → refused

The new v3 row is `active` / `studio_safe` / `commercial_hosted` — so Studio's first Smart Resize call would get `403 workflow_not_available`. The same applies to a future active Product Scene row.

## Fix: extend the advanced gate for Studio-approved rows (backend only)

File: `backend/phase2b/advanced.py` (`resolve_advanced_request`), no signature change.

Replace the three research-only refusals with a two-path admission:

1. **Research path (unchanged):** `research_only` + `internal` + status in (`draft`, `testing`) + staging env — for Image Lab experiments (v1/v2 rows keep working exactly as before).
2. **Studio path (new):** admitted when ALL of:
   - `status == "active"`
   - `registry_visibility == "studio_safe"`
   - `production_enabled == true`
   - `commercial_status` in the approved set (same `COMMERCIAL_APPROVED` list the generic gate uses)
   - current environment in `allowed_envs`

Everything after the registry step (asset ownership/readiness/expiry, input envelope, output preset allow-list, strict params, flags, module flag) runs unchanged for both paths.

No changes needed in `api.py` (the call site already passes the row through), no schema change, no config-hash change (gate logic is code, not registry config), no new env vars.

### Verification

- `test_wp1_outpaint.py` / `test_wp2_product_scene.py` still pass (research rows take path 1).
- New check: synthetic Studio-shaped dispatch to `outpaint:v3` passes the gate; `outpaint:v2` (research) still passes; a hypothetical `testing` + `studio_safe` row fails (must be both active AND studio_safe).
- After deploy: one real Smart Resize run from app.brandverita.io staging wiring.

## Sequence

1. Reply to Studio: "send no origin on POST; only GET /v1/workflows?origin=studio uses it" — unblocks Generate image immediately.
2. Apply the gate change, run the research test suites, deploy API to Modal (clear `__pycache__`).
3. Studio retests Smart Resize against `outpaint:v3`.

## Technical details

- Files: `backend/phase2b/advanced.py` only.
- The approved-commercial set lives in `backend/phase2b/registry.py` (`COMMERCIAL_APPROVED`); import/reuse, don't duplicate.
- No registry rows, migrations, secrets, or env vars change. No Studio/myaccount-side work beyond the reply.
