insert into public.workflow_definitions (
  key, version, display_name, description, status,
  provider, provider_model, provider_workflow_reference,
  input_schema, output_schema, allowed_dimensions, allowed_output_presets,
  input_envelope, artifact_pins, requires_source_asset,
  worker_version, comfyui_ref, model_manifest_ref, data_handling_profile,
  commercial_status, registry_visibility, production_enabled, enabled_for_studio,
  allowed_envs, rollout_percentage, provider_terms_reference, candidate_notes
)
select
  key, 'v2',
  'Generate image (Flux Schnell)',
  'Self-hosted Flux Schnell text-to-image on the pinned Modal/ComfyUI worker. Production-approved (commercial_self_hosted_approved, recorded 2026-09-05); no third-party provider and no BFL disclosure obligations.',
  'active',
  provider, provider_model, provider_workflow_reference,
  input_schema, output_schema, allowed_dimensions, allowed_output_presets,
  input_envelope, artifact_pins, requires_source_asset,
  worker_version, comfyui_ref, model_manifest_ref, data_handling_profile,
  'commercial_self_hosted_approved', 'studio_safe', true, true,
  array['staging','production']::text[], 100, null,
  'Studio-facing production row for text-to-image. Config cloned verbatim from flux_text_to_image:v1, which stays internal/pending_review for research comparison.'
from public.workflow_definitions
where key = 'flux_text_to_image' and version = 'v1';

insert into public.workflow_definitions (
  key, version, display_name, description, status,
  provider, provider_model, provider_workflow_reference,
  input_schema, output_schema, allowed_dimensions, allowed_output_presets,
  input_envelope, artifact_pins, requires_source_asset,
  worker_version, comfyui_ref, model_manifest_ref, data_handling_profile,
  commercial_status, registry_visibility, production_enabled, enabled_for_studio,
  allowed_envs, rollout_percentage, provider_terms_reference, candidate_notes
)
select
  key, 'v3',
  'Smart resize / extend',
  'Extends an existing image to a fixed preset size using the hosted expand model. Geometry and the extend instruction are server-owned; the original rectangle is composited back and pixel-verified. Production-approved under the BFL public API terms (non-EU, rev. 2026-08-04).',
  'active',
  provider, provider_model, provider_workflow_reference,
  input_schema, output_schema, allowed_dimensions, allowed_output_presets,
  input_envelope, artifact_pins, requires_source_asset,
  worker_version, comfyui_ref, model_manifest_ref, data_handling_profile,
  'commercial_hosted', 'studio_safe', true, true,
  array['staging','production']::text[], 100,
  'BFL Developer Terms + FLUX API Service Terms, rev. 2026-08-04 (non-EU); clause 2b input/output licence accepted with user disclosure.',
  'Studio-facing production row for Smart resize. Config cloned verbatim from outpaint:v2, which stays internal/research_only for the score bench alongside self-hosted outpaint:v1.'
from public.workflow_definitions
where key = 'outpaint' and version = 'v2';
