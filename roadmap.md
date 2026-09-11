# Roadmap — compliance finalisation + production split

## Track F — Studio go-live for Generate image + BFL Smart resize (2026-09-10)

- [x] `flux_text_to_image:v2` — approved, studio_safe, enabled, config hash set
- [x] `outpaint:v3` — hosted BFL expand, approved, studio_safe, enabled, config hash set
- [x] Studio package updated: Smart resize points at `v3`, text-to-image gating doc corrected
- [x] `studio-export/07-team-requests.md` — per-team asks for Studio and myaccount
- [ ] Studio team: show Generate image on discovery, switch Smart resize to `v3`, retire Pixelcut path, confirm `origin=studio` on dispatch
- [ ] myaccount team: reprice `smart_resize` on the BFL cost, confirm key mapping, confirm `image_generation` in a real Pro handoff
- [ ] Track C disclosures now cover Smart resize too (BFL processing + no personal data)

## Track A — compliance record

- [x] Assign production app names (locked, see Track B)
- [x] Reconcile `LICENSE_REVIEW.md` decision summary + inventory with Approved status
- [x] Check §5.6 / §6.4 internal approval gates; label external BFL items
- [x] Fill `THIRD_PARTY_NOTICES.md` placeholder rows with real pins
- [x] Cross-link approval status from `COMPLIANCE.md`
- [x] Re-baseline Product Scene on BFL public API terms (2026-09-06): non-EU terms, clause 2b training licence accepted with user disclosure, no DPA sought
- [ ] Confirm fork artefacts in `brandverita/ComfyUI` (LICENSE, CHANGES.md, SBOM, tag `v6-flux-prod`) — action on the fork repo

## Track C — Studio-side obligations for Product Scene (Studio app team)

- [ ] Flow the FLUX Usage Policy down into Studio's end-user terms and AUP
- [ ] Add user-facing disclosure: third-party AI processing, may be used for model improvement
- [ ] Prohibit uploads containing identifiable personal data for Product Scene

## Track B — production split (execution outside this repo)

- [ ] Production Supabase project: replay 13 migrations, private buckets, grants, RLS, retention job
- [ ] Modal apps: `comfyui-generation-worker-prod`, `comfyui-outpaint-worker-prod`, then `brandverita-api-prod`
- [ ] Production secrets: `brandverita-supabase-prod`, `bfl-production`, `huggingface-secret`, `EXTRA_JWT_ISSUER_URLS`
- [ ] Production registry v2 rows for `flux_text_to_image:v2` and `outpaint:v2` (`allowed_envs = {production}`), plus `product_scene:v2` held disabled
- [ ] Run `set_config_hash.py` per new row against production Supabase
- [ ] Studio-token end-to-end check on production
- [ ] Product Scene promotion once the Track C obligations close
- [ ] Before the first non-internal account: turn on leaked-password protection in
      the production project's authentication settings and set a minimum password
      length (dashboard toggles — no code, no migration)

### Staging security notices — expected, not defects

Staging is intentionally left as is; these open warnings are deliberate and
should not be "fixed" later by mistake:

- Leaked-password protection off — staging only has a small allow-listed set of
  internal test accounts. Decision 2026-09-10: production only.
- Locked registry rows — immutability is enforced by design.
- Internal allow-list helper — security-definer email gate, intended.


## Track D — Studio CORS (staging)

- [x] Add `app.brandverita.io` + Lovable preview origin to `ALLOWED_ORIGINS` in `backend/phase2b/api.py`
- [x] Verified Supabase Storage CORS already open (`*`, PUT allowed) — no storage/policy change needed
- [ ] Redeploy `api.py` to Modal staging (user action) and confirm Studio upload round-trip

## Track E — Smart resize integrity check (staging)

- [x] Diagnose `source_region_integrity_failed` on Studio uploads (PNG metadata, not pixel damage)
- [x] Replace encoded-PNG digest with canonical pixel digest in `backend/phase2b/outpaint_geometry.py`
- [ ] Copy `outpaint_geometry.py` to `modal-project/phase1-v6-staging/`, clear `__pycache__`, `modal deploy api.py` (user action)
- [ ] Re-run `test_wp1_outpaint.py` (17/17) and repeat the Studio Smart resize at 1200x627

- [x] WP1b (2026-09-07): Smart resize dispatches to the hosted expand model
      (`bfl_outpaint` / `flux-pro-1.0-expand`, new staging-only `outpaint:v2`
      row); self-hosted `outpaint:v1` kept for comparison. Shared Studio export
      hook now keys results to the current module + source image, so a finished
      picture from a previous run can never stay on screen.

- WP1b follow-up (2026-09-07): hosted Smart resize invented subjects (a face in
  the new side bands) because the server instruction listed things "not" to add
  and Flux-family models read negations as requests. Instruction rewritten
  negation-free, with a promptless `bare` comparison mode behind
  `OUTPAINT_V2_PROMPT_MODE`. Registry row and config hash unchanged; redeploy of
  the Modal V6 app required.

## Track F — Studio go-live (2026-09-11)

- [x] Answer Studio: POST /v1/generations reads no origin (body, query, or header); origin=studio is only for GET /v1/workflows discovery
- [x] Extend `advanced.resolve_advanced_request` with a second admission path: active + studio_safe + production_enabled + approved commercial status + env allowed (research path unchanged). Verified 6/6 gate cases, py_compile OK
- [ ] Copy `backend/phase2b/advanced.py` to `modal-project/phase1-v6-staging/`, clear `__pycache__`, `modal deploy api.py` (user action)
- [ ] Re-run `test_wp1_outpaint.py` / `test_wp2_product_scene.py` after deploy; then one real Smart Resize run from app.brandverita.io against `outpaint:v3`
- [ ] Studio: wire Generate image to `flux_text_to_image:v2` (works today, no origin needed); retire Pixelcut for Smart resize in favor of `outpaint:v3`
