-- generation_assets ---------------------------------------------------------
create table public.generation_assets (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null,
  workspace_id uuid,
  sha256 text,
  bucket text not null,
  storage_path text not null,
  content_type text,
  file_size bigint,
  width integer,
  height integer,
  kind text not null default 'input',
  status text not null default 'pending_upload',
  source_asset_id uuid references public.generation_assets(id) on delete set null,
  job_id uuid references public.generation_jobs(id) on delete set null,
  workflow_key text,
  workflow_version text,
  provenance jsonb not null default '{}'::jsonb,
  idempotency_key text,
  created_at timestamptz not null default now(),
  finalized_at timestamptz,
  deleted_at timestamptz,
  expires_at timestamptz,
  constraint generation_assets_bucket_path_key unique (bucket, storage_path),
  constraint generation_assets_kind_chk check (kind in ('input','output')),
  constraint generation_assets_status_chk check (status in ('pending_upload','ready','rejected','deleted','expired')),
  constraint generation_assets_ready_chk check (
    status <> 'ready' or (sha256 is not null and content_type is not null
      and file_size is not null and width is not null and height is not null
      and finalized_at is not null)),
  constraint generation_assets_dims_chk check (
    (width is null or (width between 1 and 4096)) and
    (height is null or (height between 1 and 4096)) and
    (width is null or height is null or width::bigint * height::bigint <= 16777216)),
  constraint generation_assets_size_chk check (file_size is null or file_size <= 10485760)
);

create unique index generation_assets_idem_key
  on public.generation_assets (owner_id, idempotency_key)
  where idempotency_key is not null;
create index generation_assets_owner_recent
  on public.generation_assets (owner_id, status, created_at desc);
create index generation_assets_sha256_idx on public.generation_assets (sha256);
create index generation_assets_job_idx on public.generation_assets (job_id);

create or replace function public.validate_generation_asset_expiry()
returns trigger language plpgsql set search_path = public as $$
begin
  if new.expires_at is not null and new.expires_at <= new.created_at then
    raise exception 'generation_assets: expires_at must be after created_at';
  end if;
  if new.finalized_at is not null and new.finalized_at < new.created_at then
    raise exception 'generation_assets: finalized_at cannot precede created_at';
  end if;
  if new.status = 'ready' and new.expires_at is null then
    raise exception 'generation_assets: ready assets require expires_at';
  end if;
  return new;
end $$;

create trigger generation_assets_expiry_validate
  before insert or update on public.generation_assets
  for each row execute function public.validate_generation_asset_expiry();

-- usage_ledger --------------------------------------------------------------
create table public.usage_ledger (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  workspace_id uuid,
  job_id uuid references public.generation_jobs(id) on delete set null,
  workflow_key text not null,
  workflow_version text not null,
  provider text not null,
  estimated_credits numeric,
  estimated_provider_cost numeric,
  actual_provider_cost numeric,
  gpu_seconds numeric,
  status text not null default 'reserved',
  created_at timestamptz not null default now(),
  settled_at timestamptz,
  constraint usage_ledger_status_chk check (status in ('reserved','settled','void'))
);
create index usage_ledger_user_recent on public.usage_ledger (user_id, created_at desc);
create index usage_ledger_job_idx on public.usage_ledger (job_id);

alter table public.generation_jobs
  add constraint generation_jobs_usage_ledger_fk
  foreign key (usage_ledger_id) references public.usage_ledger(id) on delete set null;

-- grants + RLS --------------------------------------------------------------
grant select on public.generation_assets to authenticated;
grant all on public.generation_assets to service_role;
grant select on public.usage_ledger to authenticated;
grant all on public.usage_ledger to service_role;

alter table public.generation_assets enable row level security;
alter table public.usage_ledger enable row level security;

create policy "Approved users read own assets" on public.generation_assets
  for select to authenticated
  using (owner_id = auth.uid() and is_email_allowed(auth.uid()) and deleted_at is null);

create policy "Approved users read own usage ledger" on public.usage_ledger
  for select to authenticated
  using (user_id = auth.uid() and is_email_allowed(auth.uid()));