ALTER TABLE public.generation_jobs
  ADD COLUMN IF NOT EXISTS prompt text,
  ADD COLUMN IF NOT EXISTS negative_prompt text,
  ADD COLUMN IF NOT EXISTS progress integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS error_code text;

CREATE UNIQUE INDEX IF NOT EXISTS generation_jobs_user_idempotency_key
  ON public.generation_jobs (user_id, idempotency_key)
  WHERE idempotency_key IS NOT NULL;