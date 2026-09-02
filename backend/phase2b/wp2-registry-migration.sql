-- Phase 2B WP2 — Module B registry candidate: product_scene:v1 (STAGING ONLY)
--
-- Run once in the Supabase `comfy-ui` SQL editor. Isolation is carried by this
-- row, not by application code: research_only + internal + staging-only means
-- Studio and production dispatch are refused server-side even with every flag on.
--
-- config_hash is computed exactly as registry.compute_config_hash does:
-- sha256 over canonical JSON of key, version, provider, provider_model,
-- provider_workflow_reference, input_schema, output_schema, allowed_dimensions.

insert into public.workflow_definitions (
  key, version, title, description,
  provider, provider_model, provider_workflow_reference,
  status, commercial_status, registry_visibility,
  production_enabled, enabled_for_studio, allowed_envs,
  requires_source_asset, allowed_output_presets,
  input_schema, output_schema, allowed_dimensions,
  input_envelope, artifact_pins, candidate_notes
) values (
  'product_scene', 'v1',
  'Product background / scene (research)',
  'Replaces the background of a single-product image using a fixed set of server-owned scene presets. Research only.',
  'bfl_product_scene', 'flux-kontext-pro', null,
  'testing', 'research_only', 'internal',
  false, false, array['staging'],
  true,
  array['1080x1080','1080x1350','1200x627','1600x900'],
  jsonb_build_object(
    'scene_direction_enum', jsonb_build_array('clean_studio','premium_neutral','warm_lifestyle','natural_surface'),
    'background_style_enum', jsonb_build_array('neutral','soft_shadow','high_key','editorial'),
    'preserve_subject_required', true,
    'accepts_prompt', false,
    'preset_table_version', 'wp2-scene-presets-1'
  ),
  jsonb_build_object('format', 'png', 'exact_preset_size', true),
  null,
  jsonb_build_object('max_width', 4096, 'max_height', 4096, 'max_pixels', 16777216),
  jsonb_build_array(
    jsonb_build_object(
      'component', 'hosted_model',
      'provider', 'Black Forest Labs',
      'source', 'https://api.bfl.ai/v1/flux-kontext-pro',
      'model', 'flux-kontext-pro',
      'pin_type', 'hosted_endpoint_version',
      'license', 'BFL API terms — commercial use subject to written confirmation',
      'notes', 'Hosted endpoint: no file digest is possible. Provider request ids are recorded per run for traceability.'
    )
  ),
  'WP2 research candidate. Scene instruction text is server-owned (scene_presets.py) and hashed into provenance; no client text reaches the provider. Subject preservation is not byte-verifiable for this module (full-frame re-render) and is gated by human review. Research spend cap: $10.'
)
on conflict (key, version) do nothing;

-- config_hash must match registry.compute_config_hash for the same row.
update public.workflow_definitions w
set config_hash = encode(
  digest(
    json_build_object(
      'allowed_dimensions', w.allowed_dimensions,
      'input_schema', w.input_schema,
      'key', w.key,
      'output_schema', w.output_schema,
      'provider', w.provider,
      'provider_model', w.provider_model,
      'provider_workflow_reference', w.provider_workflow_reference,
      'version', w.version
    )::text,
    'sha256'
  ),
  'hex'
)
where w.key = 'product_scene' and w.version = 'v1';

-- Verify. Expect: testing / research_only / internal / f / f / {staging} / t
select key, version, status, commercial_status, registry_visibility,
       production_enabled, enabled_for_studio, allowed_envs,
       requires_source_asset, provider, provider_model, allowed_output_presets
from public.workflow_definitions
where key = 'product_scene';
