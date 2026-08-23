create table public.workflow_definitions (
  id uuid primary key default gen_random_uuid(),
  key text not null,
  version text not null,
  status text not null default 'draft',
  display_name text,
  description text,
  provider text not null,
  provider_model text,
  provider_workflow_reference text,
  commercial_status text not null default 'pending_review',
  provider_terms_reference text,
  provider_terms_verified_at timestamptz,
  data_handling_profile text,
  allowed_envs text[] not null default '{}',
  production_enabled boolean not null default false,
  enabled_for_studio boolean not null default false,
  registry_visibility text not null default 'internal',
  rollout_percentage integer not null default 0,
  allowed_workspace_ids uuid[],
  feature_flag text,
  input_schema jsonb not null default '{}'::jsonb,
  output_schema jsonb not null default '{}'::jsonb,
  allowed_dimensions jsonb not null default '[]'::jsonb,
  estimated_credits numeric,
  config_hash text,
  worker_version text,
  comfyui_ref text,
  model_manifest_ref text,
  created_at timestamptz not null default now(),
  retired_at timestamptz,
  constraint workflow_definitions_key_version_unique unique (key, version),
  constraint workflow_definitions_status_check check (status in ('draft','testing','active','deprecated','disabled')),
  constraint workflow_definitions_commercial_status_check check (commercial_status in ('research_only','commercial_hosted','commercial_self_hosted_approved','licensed_self_hosted','pending_review','blocked')),
  constraint workflow_definitions_visibility_check check (registry_visibility in ('internal','studio_safe','hidden')),
  constraint workflow_definitions_rollout_check check (rollout_percentage between 0 and 100)
);

grant all on public.workflow_definitions to service_role;

alter table public.workflow_definitions enable row level security;
-- No policies for anon/authenticated: direct client reads are denied.
-- The Generation API reads the registry with the service role and applies
-- server-side visibility filtering before returning any workflow metadata.

create or replace function public.enforce_workflow_definitions_immutability()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if old.status in ('active','deprecated','disabled') then
    if new.key is distinct from old.key
       or new.version is distinct from old.version
       or new.provider is distinct from old.provider
       or new.provider_model is distinct from old.provider_model
       or new.provider_workflow_reference is distinct from old.provider_workflow_reference
       or new.config_hash is distinct from old.config_hash
       or new.input_schema is distinct from old.input_schema
       or new.output_schema is distinct from old.output_schema
       or new.model_manifest_ref is distinct from old.model_manifest_ref
       or new.comfyui_ref is distinct from old.comfyui_ref then
      raise exception 'workflow_definitions: immutable fields cannot be changed once a version is activated; create a new version instead';
    end if;
  end if;
  return new;
end;
$$;

create trigger workflow_definitions_immutability
  before update on public.workflow_definitions
  for each row execute function public.enforce_workflow_definitions_immutability();

alter table public.generation_jobs
  add column if not exists workspace_id uuid,
  add column if not exists workflow_version text,
  add column if not exists workflow_config_hash text,
  add column if not exists provider text,
  add column if not exists provider_model text,
  add column if not exists provider_job_reference text,
  add column if not exists input_asset_ids uuid[],
  add column if not exists output_asset_ids uuid[],
  add column if not exists inputs jsonb,
  add column if not exists worker_version text,
  add column if not exists usage_ledger_id uuid,
  add column if not exists error_category text,
  add column if not exists internal_error_ref text,
  add column if not exists queued_at timestamptz,
  add column if not exists started_at timestamptz,
  add column if not exists expires_at timestamptz;

update public.generation_jobs
set status = 'expired',
    error_code = 'job_expired',
    error_message = 'Job expired: stale queue entry predating worker dispatch.',
    completed_at = now(),
    updated_at = now()
where id in ('c3f77339-fe3a-4c7f-b175-8864c0dbf7e6','2f933030-6c9d-49e7-8d6e-6bfc775d831c')
  and status = 'queued';

insert into public.workflow_definitions (
  key, version, status, display_name, description, provider, provider_model,
  provider_workflow_reference, commercial_status, data_handling_profile,
  allowed_envs, production_enabled, enabled_for_studio, registry_visibility,
  rollout_percentage, input_schema, output_schema, allowed_dimensions,
  config_hash, worker_version, comfyui_ref, model_manifest_ref
) values (
  'flux_text_to_image', 'v1', 'active',
  'Flux Schnell text-to-image',
  'Baseline Flux Schnell text-to-image workflow served by the self-hosted Modal/ComfyUI worker. Staging/Lab only until the deployment manifest review completes.',
  'modal_comfyui', 'FLUX.1-schnell',
  'comfyui-generation-worker/ComfyUIWorker.generate_image',
  'pending_review', 'staging_default',
  '{staging}', false, false, 'internal', 100,
  '{"prompt":{"type":"string","required":true,"max_length":2000},"negative_prompt":{"type":"string","required":false,"max_length":1000},"width":{"type":"integer","required":true},"height":{"type":"integer","required":true},"seed":{"type":"integer","required":false,"minimum":0,"maximum":4294967295},"idempotency_key":{"type":"string","format":"uuid","required":true}}'::jsonb,
  '{"image":{"type":"image","content_type":"image/png"}}'::jsonb,
  '[{"width":512,"height":512},{"width":768,"height":768},{"width":1024,"height":1024},{"width":1024,"height":1280},{"width":1280,"height":1024}]'::jsonb,
  '97d95ca97cd861d49377445bc6c94acde122315e2f5e14c52dedf772594fe38e',
  'comfyui-worker:phase1:344b439',
  'https://github.com/brandverita/ComfyUI@344b43989e8c56b5bb4a66cf028c834192ab59dd',
  'worker-manifest:phase1:v1'
), (
  'flux_text_to_image', 'v1-commercial-candidate', 'draft',
  'Flux Schnell via Replicate (candidate)',
  'Staging evaluation candidate for a commercially hosted Flux Schnell provider. Pending legal/data-handling review; not dispatchable.',
  'replicate', 'black-forest-labs/flux-schnell',
  null, 'pending_review', 'unreviewed',
  '{staging}', false, false, 'internal', 0,
  '{}'::jsonb, '{}'::jsonb, '[]'::jsonb,
  null, null, null, null
), (
  'outpaint', 'v1', 'draft',
  'Outpaint (experimental)',
  'Lab-only outpaint research workflow. Its model/provider/licensing decision is independent of the Flux Schnell baseline. Research use only; never dispatchable from Studio or production.',
  'modal_comfyui', 'unselected',
  null, 'research_only', 'research_internal',
  '{staging}', false, false, 'internal', 0,
  '{}'::jsonb, '{}'::jsonb,
  '[{"width":1080,"height":1080},{"width":1200,"height":627},{"width":1600,"height":900},{"width":1080,"height":1920},{"width":1080,"height":1350}]'::jsonb,
  null, null, null, null
);