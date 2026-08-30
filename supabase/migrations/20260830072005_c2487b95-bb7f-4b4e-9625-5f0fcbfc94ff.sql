create or replace function public.enforce_workflow_definitions_immutability()
returns trigger
language plpgsql
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

revoke execute on function public.enforce_workflow_definitions_immutability() from anon, authenticated, public;