-- Module C — registry candidate: editorial_layout:v1 (STAGING ONLY)
--
-- Run once in the Supabase `comfy-ui` SQL editor. Isolation is carried by this
-- row, not by application code: research_only + internal + staging-only means
-- Studio and production dispatch are refused server-side even with every flag on.
--
-- config_hash is computed exactly as registry.compute_config_hash does:
-- sha256 over canonical JSON of key, version, provider, provider_model,
-- provider_workflow_reference, input_schema, output_schema, allowed_dimensions.

insert into public.workflow_definitions (
  key, version, display_name, description,
  provider, provider_model, provider_workflow_reference,
  status, commercial_status, registry_visibility,
  production_enabled, enabled_for_studio, allowed_envs,
  requires_source_asset, allowed_output_presets,
  input_schema, output_schema, allowed_dimensions,
  input_envelope, artifact_pins, candidate_notes
) values (
  'editorial_layout', 'v1',
  'Editorial layout (research)',
  'Restyles a subject photograph into an editorial scene with a reserved copy zone, then typesets the headline locally. Research only.',
  'bfl_editorial_layout', 'flux-kontext-pro', null,
  'testing', 'research_only', 'internal',
  false, false, array['staging'],
  true,
  jsonb_build_array('1600x900','1080x1080','1080x1920','800x2000'),
  jsonb_build_object(
    'look_enum', jsonb_build_array('cover_shot','lifestyle_spread','flat_lay','documentary'),
    'people_enum', jsonb_build_array('none','background_figures','foreground_model'),
    'accepts_prompt', false,
    'copy_fields', jsonb_build_object('headline_max_chars', 90, 'standfirst_max_chars', 200, 'label_max_chars', 40),
    'preset_table_version', 'editorial-presets-1'
  ),
  jsonb_build_object('format', 'png', 'exact_preset_size', true, 'layered', true),
  jsonb_build_array(
    jsonb_build_object('width', 1600, 'height', 900),
    jsonb_build_object('width', 1080, 'height', 1080),
    jsonb_build_object('width', 1080, 'height', 1920),
    jsonb_build_object('width', 800, 'height', 2000)
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
      'source', 'https://api.bfl.ai/v1/flux-kontext-pro',
      'model', 'flux-kontext-pro',
      'pin_type', 'hosted_endpoint_version',
      'license', 'BFL API terms — commercial use subject to written confirmation',
      'notes', 'Hosted endpoint: no file digest is possible. Provider request ids are recorded per run for traceability.'
    ),
    jsonb_build_object(
      'component', 'typefaces',
      'provider', 'Google Fonts (SIL Open Font License)',
      'source', 'bundled in the server image (backend/phase2b/fonts)',
      'model', 'Libre Franklin / Libre Baskerville / Oswald',
      'pin_type', 'bundled_files',
      'license', 'SIL OFL 1.1',
      'notes', 'Text is typeset locally with these fonts; the picture model never draws type.'
    )
  ),
  'Module C research candidate. Instruction text is server-owned (editorial_presets.py) and hashed into provenance; client copy (headline/standfirst/label) is typeset locally and never reaches the provider. Copy-zone usability is measured per run; subject preservation is not byte-verifiable and is gated by human review. Research spend cap: $10, same shape as Module B.'
)
on conflict (key, version) do nothing;

-- config_hash: set it with the exact Python canonicalisation the API uses, not
-- in SQL (Postgres json_build_object does not reproduce Python's compact,
-- key-sorted encoding, so a SQL-computed hash trips the mismatch tripwire).
-- Run `python backend/phase2b/tools/set_config_hash.py editorial_layout v1`.

-- Verify. Expect: testing / research_only / internal / f / f / {staging} / t
select key, version, status, commercial_status, registry_visibility,
       production_enabled, enabled_for_studio, allowed_envs,
       requires_source_asset, provider, provider_model, allowed_output_presets
from public.workflow_definitions
where key = 'editorial_layout';
