# Roadmap — compliance finalisation + production split

## Milestone 2026-09-11 — production-ready image service

- [x] `MILESTONE-2026-09-11.md` records the accepted state of all three tools
      (Generate image, Smart resize, Product scene), their approval basis,
      measured cost/latency and settings fingerprints
- [x] `product_scene:v2` created: active, studio_safe, commercial_hosted,
      production_enabled, enabled_for_studio, `{staging,production}`, fingerprint
      `1fb1bd108b…`; `product_scene:v1` untouched as the research row
- [x] Handover pack + client constants point Product scene at `v2`
- [ ] Studio team: switch Product scene on with `workflow_version: "v2"` and drop
      the entitlement fallback for it
- [ ] Studio team: Track C disclosures now due for Product scene as well as
      Smart resize (promoted ahead of them by explicit decision)
- [ ] Duplicate environment: shape written up in the milestone document; which
      side keeps today's setup is still undecided


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

## Track G — Brand consistency layers (2026-09-12)

- [x] Server-owned three-layer prompt catalogue (`backend/phase2b/prompt_layers.py`):
      Layer 1 occasion (Autumn, Sales, Promotion, Christmas, Halloween, Spring),
      Layer 2 setting/visual DNA byte-identical per world (Coastal terrace,
      Forest cabin, Urban loft), Layer 3 subject framing, fixed universal quality
      tail (only the aspect note varies). Wording never leaves the server.
- [x] `GET /v1/prompt-layers` — keys/labels/hints only, no wording.
- [x] `POST /v1/generations` accepts `style {season, world, subject}` in place of
      `prompt` (mutually exclusive, enum-only, subject <= 200 chars, newlines
      collapsed); server composes and records a wording fingerprint (SHA-256 per
      layer + `layer_table_version`) in `request_params.style` / `inputs.style`.
      No registry version bump needed: normalized inputs are unchanged.
- [x] Lab UI: two parallel modes — existing "Describe the picture you want"
      free text kept exactly as before, plus a "Branding" picker; brand setting
      and occasion remembered per device; seed field reusable for repeat runs.
- [x] `test_prompt_layers.py` 14/14 (Layer 2 byte-identity, tail identity,
      enum rejection, subject limits, prompt-length ceiling, no wording leak).
- [ ] Deploy: copy `prompt_layers.py` + `api.py` to
      `modal-project/phase1-v6-staging/`, clear `__pycache__`, `modal deploy api.py` (user action)
- [ ] Studio handoff: adopt `style` request + `/v1/prompt-layers` (see studio-export/06)
