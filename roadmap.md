# Roadmap — compliance finalisation + production split

## Track A — compliance record
- [x] Assign production app names (locked, see Track B)
- [x] Reconcile `LICENSE_REVIEW.md` decision summary + inventory with Approved status
- [x] Check §5.6 / §6.4 internal approval gates; label external BFL items
- [x] Fill `THIRD_PARTY_NOTICES.md` placeholder rows with real pins
- [x] Cross-link approval status from `COMPLIANCE.md`
- [ ] Confirm fork artefacts in `brandverita/ComfyUI` (LICENSE, CHANGES.md, SBOM, tag `v6-flux-prod`) — action on the fork repo

## Track B — production split (execution outside this repo)
- [ ] Production Supabase project: replay 13 migrations, private buckets, grants, RLS, retention job
- [ ] Modal apps: `comfyui-generation-worker-prod`, `comfyui-outpaint-worker-prod`, then `brandverita-api-prod`
- [ ] Production secrets: `brandverita-supabase-prod`, `bfl-production`, `huggingface-secret`, `EXTRA_JWT_ISSUER_URLS`
- [ ] Production registry v2 rows for `flux_text_to_image:v2` and `outpaint:v2` (`allowed_envs = {production}`), plus `product_scene:v2` held disabled
- [ ] Run `set_config_hash.py` per new row against production Supabase
- [ ] Studio-token end-to-end check on production
- [ ] Product Scene promotion once BFL agreement + DPA execute
