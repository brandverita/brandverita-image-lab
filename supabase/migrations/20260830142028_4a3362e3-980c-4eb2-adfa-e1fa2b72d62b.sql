UPDATE public.workflow_definitions
SET allowed_output_presets = '["1200x627","1600x900"]'::jsonb,
    provider = 'modal_research_2b',
    provider_model = 'sd-v1-5-inpainting',
    provider_workflow_reference = 'outpaint-v1-preserve-source-1',
    worker_version = 'research-2b-outpaint-1',
    comfyui_ref = '3d0003c24c1aec9f0c021dbc70ffb7cd8cf0685c',
    candidate_id = 'outpaint-a-sd15inpaint-2b',
    candidate_notes = 'WP1 Module A research candidate. Worker app comfyui-research-worker-2b (isolated from V5/V6). Staging only, research_only, flags default false.',
    artifact_pins = '[
      {"role":"comfyui","source":"https://github.com/comfyanonymous/ComfyUI","commit":"3d0003c24c1aec9f0c021dbc70ffb7cd8cf0685c","tag":"v0.3.69","license":"GPL-3.0"},
      {"role":"checkpoint","source":"https://huggingface.co/benjamin-paine/stable-diffusion-v1-5-inpainting","commit":"705090e310335d0cf1586d032130fa9f09a6fa00","filename":"sd-v1-5-inpainting.safetensors","sha256":"ef97ac1fe87ed0406433ad8710ff1da6e07e873de9a1a107b828844336d015ec","size_bytes":4265216468,"license":"CreativeML OpenRAIL-M"},
      {"role":"base_image","source":"docker.io/nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04","digest":"sha256:622e78a1d02c0f90ed900e3985d6c975d8e2dc9ee5e61643aed587dcf9129f42","license":"NVIDIA Deep Learning Container License"},
      {"role":"runtime","python":"3.12","torch":"2.6.0+cu124","cuda":"12.4","custom_nodes":[]}
    ]'::jsonb
WHERE key = 'outpaint' AND version = 'v1';