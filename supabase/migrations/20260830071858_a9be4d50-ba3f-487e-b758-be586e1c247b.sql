-- 1.1 Registry columns
alter table public.workflow_definitions
  add column if not exists requires_source_asset boolean not null default false,
  add column if not exists allowed_output_presets jsonb not null default '[]'::jsonb,
  add column if not exists input_envelope jsonb not null default '{}'::jsonb,
  add column if not exists artifact_pins jsonb not null default '[]'::jsonb,
  add column if not exists candidate_id text,
  add column if not exists candidate_notes text;

create unique index if not exists workflow_definitions_candidate_id_key
  on public.workflow_definitions (candidate_id) where candidate_id is not null;

-- Extended immutability: freeze new config fields once the row is live
create or replace function public.enforce_workflow_definitions_immutability()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if OLD.status in ('active', 'deprecated', 'disabled') then
    if NEW.key is distinct from OLD.key
      or NEW.version is distinct from OLD.version
      or NEW.provider is distinct from OLD.provider
      or NEW.provider_model is distinct from OLD.provider_model
      or NEW.provider_workflow_reference is distinct from OLD.provider_workflow_reference
      or NEW.input_schema is distinct from OLD.input_schema
      or NEW.output_schema is distinct from OLD.output_schema
      or NEW.allowed_dimensions is distinct from OLD.allowed_dimensions
      or NEW.config_hash is distinct from OLD.config_hash
      or NEW.worker_version is distinct from OLD.worker_version
      or NEW.comfyui_ref is distinct from OLD.comfyui_ref
      or NEW.model_manifest_ref is distinct from OLD.model_manifest_ref
      or NEW.requires_source_asset is distinct from OLD.requires_source_asset
      or NEW.allowed_output_presets is distinct from OLD.allowed_output_presets
      or NEW.input_envelope is distinct from OLD.input_envelope
      or NEW.artifact_pins is distinct from OLD.artifact_pins
      or NEW.candidate_id is distinct from OLD.candidate_id
    then
      raise exception 'workflow_definitions row % is immutable in status %', OLD.id, OLD.status
        using errcode = 'check_violation';
    end if;
  end if;
  return NEW;
end;
$$;

-- 1.2 Job link columns
alter table public.generation_jobs
  add column if not exists source_asset_id uuid references public.generation_assets(id),
  add column if not exists output_asset_id uuid references public.generation_assets(id),
  add column if not exists output_preset text,
  add column if not exists request_params jsonb not null default '{}'::jsonb;

create index if not exists generation_jobs_source_asset_idx
  on public.generation_jobs (source_asset_id);
create index if not exists generation_jobs_output_asset_idx
  on public.generation_jobs (output_asset_id);

-- 1.3 Evaluation runs (staging only)
create table if not exists public.transformation_eval_runs (
  id uuid primary key default gen_random_uuid(),
  module text not null,
  job_id uuid references public.generation_jobs(id) on delete set null,
  candidate_id text,
  workflow_key text not null,
  workflow_version text not null,
  config_hash text,
  provider text not null,
  provider_model text,
  provider_call_id text,
  worker_version text,
  operator_user_id uuid not null,
  source_asset_id uuid references public.generation_assets(id) on delete set null,
  output_asset_id uuid references public.generation_assets(id) on delete set null,
  output_preset text,
  request_params jsonb not null default '{}'::jsonb,
  queued_at timestamptz,
  dispatched_at timestamptz,
  first_byte_at timestamptz,
  completed_at timestamptz,
  provider_latency_ms integer,
  total_latency_ms integer,
  cold_start boolean,
  gpu_seconds numeric,
  estimated_cost numeric,
  actual_provider_cost numeric,
  cost_currency text default 'USD',
  status text not null default 'pending',
  error_code text,
  error_message text,
  output_width integer,
  output_height integer,
  output_bytes bigint,
  output_sha256 text,
  source_region_verified boolean,
  reviewer_scores jsonb not null default '[]'::jsonb,
  rubric_mean numeric,
  blinded boolean not null default true,
  license_ref text,
  commercial_status text,
  data_retention_finding text,
  training_on_input boolean,
  legal_status text not null default 'pending',
  legal_reviewed_by text,
  legal_reviewed_at timestamptz,
  notes text,
  created_at timestamptz not null default now(),
  constraint transformation_eval_runs_module_chk check (module in ('outpaint','product_scene')),
  constraint transformation_eval_runs_status_chk
    check (status in ('pending','dispatched','running','completed','failed','canceled')),
  constraint transformation_eval_runs_legal_chk
    check (legal_status in ('pending','cleared_staging','blocked','needs_counsel'))
);

create index if not exists transformation_eval_runs_module_created_idx
  on public.transformation_eval_runs (module, created_at desc);
create index if not exists transformation_eval_runs_candidate_created_idx
  on public.transformation_eval_runs (candidate_id, created_at desc);
create index if not exists transformation_eval_runs_job_idx
  on public.transformation_eval_runs (job_id);

grant select on public.transformation_eval_runs to authenticated;
grant all on public.transformation_eval_runs to service_role;

alter table public.transformation_eval_runs enable row level security;

drop policy if exists "internal allow-list reads own eval runs" on public.transformation_eval_runs;
create policy "internal allow-list reads own eval runs"
  on public.transformation_eval_runs for select to authenticated
  using (operator_user_id = auth.uid() and public.is_email_allowed(auth.uid()));