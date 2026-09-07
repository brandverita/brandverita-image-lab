-- Phase 2B WP1b — Module A hosted candidate: outpaint:v2 (STAGING ONLY)
--
-- Run once in the Supabase `comfy-ui` SQL editor. `outpaint:v1` (self-hosted
-- SD-1.5 research worker) is left completely untouched and stays available for
-- comparison; it is simply no longer the row Smart Resize dispatches to.
--
-- Isolation is carried by this row, not by application code: testing +
-- research_only + internal + staging-only means Studio visibility and
-- production dispatch are refused server-side even with every flag on.

insert into public.workflow_definitions (
  key, version, display_name, description,
  provider, provider_model, provider_workflow_reference,
  status, commercial_status, registry_visibility,
  production_enabled, enabled_for_studio, allowed_envs,
  requires_source_asset, allowed_output_presets,
  input_schema, output_schema, allowed_dimensions,
  input_envelope, artifact_pins, candidate_notes
) values (
  'outpaint', 'v2',
  'Smart resize / extend (hosted research)',
  'Extends an existing image to a fixed preset size using a hosted expand model. The original pixels are pasted back and byte-verified. Research only.',
  'bfl_outpaint', 'flux-pro-1.0-expand', null,
  'testing', 'research_only', 'internal',
  false, false, array['staging'],
  true,
  jsonb_build_array('1200x627','1600x900'),
  jsonb_build_object(
    'direction_enum', jsonb_build_array('left','right','top','bottom','symmetric'),
    'anchor_enum', jsonb_build_array('left','right','top','bottom','center'),
    'expansion_mode', 'anchor_directional',
    'style_mode', 'preserve_source',
    'accepts_prompt', false,
    'geometry_owner', 'server'
  ),
  jsonb_build_object('format', 'png', 'exact_preset_size', true, 'source_region_verified', true),
  jsonb_build_array(
    jsonb_build_object('width', 1200, 'height', 627),
    jsonb_build_object('width', 1600, 'height', 900)
  ),
  jsonb_build_object(
    'max_width', 4096,
    'max_height', 4096,
    'max_pixels', 16777216,
    'allowed_content_types', jsonb_build_array('image/png','image/jpeg','image/webp')
  ),
  jsonb_build_array(
    jsonb_build_object(
      'component', 'hosted_model',
      'provider', 'Black Forest Labs',
      'source', 'https://api.bfl.ai/v1/flux-pro-1.0-expand',
      'model', 'flux-pro-1.0-expand',
      'pin_type', 'hosted_endpoint_version',
      'license', 'BFL public API terms (non-EU, rev. 2026-08-04) — clause 2b input/output licence accepted with user disclosure',
      'notes', 'Hosted endpoint: no file digest is possible. Provider request ids are recorded per run for traceability.'
    )
  ),
  'WP1b research candidate. Expansion amounts and placement are computed server-side by outpaint_geometry.plan from validated enums only; the extend instruction is server-owned and hashed into provenance. The original source rectangle is composited back and verified byte-for-byte; an unverified result fails the job. Research spend cap: $10. outpaint:v1 (self-hosted) remains untouched for comparison.'
)
on conflict (key, version) do nothing;

-- config_hash: run `python backend/phase2b/tools/set_config_hash.py outpaint v2`
-- (Python canonicalisation only — a SQL-computed hash trips the mismatch tripwire).

-- Verify. Expect two rows: v1 (modal_research_2b) and v2 (bfl_outpaint),
-- both testing / research_only / internal / f / f / {staging} / t
select key, version, status, commercial_status, registry_visibility,
       production_enabled, enabled_for_studio, allowed_envs,
       requires_source_asset, provider, provider_model, allowed_output_presets
from public.workflow_definitions
where key = 'outpaint'
order by version;
