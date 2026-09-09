ALTER TABLE public.transformation_eval_runs
  ADD COLUMN IF NOT EXISTS variant_id text,
  ADD COLUMN IF NOT EXISTS provider_params jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS public.transformation_eval_scores (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  eval_run_id uuid REFERENCES public.transformation_eval_runs(id) ON DELETE SET NULL,
  job_id uuid REFERENCES public.generation_jobs(id) ON DELETE CASCADE,
  module text NOT NULL,
  reviewer_user_id uuid NOT NULL,
  overall integer NOT NULL,
  invented_content boolean NOT NULL DEFAULT false,
  brightness integer,
  notes text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT transformation_eval_scores_overall_chk CHECK (overall BETWEEN 1 AND 5),
  CONSTRAINT transformation_eval_scores_brightness_chk CHECK (brightness IS NULL OR brightness BETWEEN 1 AND 5),
  CONSTRAINT transformation_eval_scores_unique_reviewer UNIQUE (job_id, reviewer_user_id)
);

CREATE INDEX IF NOT EXISTS transformation_eval_scores_job_idx ON public.transformation_eval_scores (job_id);
CREATE INDEX IF NOT EXISTS transformation_eval_scores_module_idx ON public.transformation_eval_scores (module, created_at DESC);

GRANT SELECT, INSERT, UPDATE ON public.transformation_eval_scores TO authenticated;
GRANT ALL ON public.transformation_eval_scores TO service_role;

ALTER TABLE public.transformation_eval_scores ENABLE ROW LEVEL SECURITY;

CREATE POLICY "internal allow-list reads own scores"
  ON public.transformation_eval_scores FOR SELECT TO authenticated
  USING (reviewer_user_id = auth.uid() AND public.is_email_allowed(auth.uid()));

CREATE POLICY "internal allow-list writes own scores"
  ON public.transformation_eval_scores FOR INSERT TO authenticated
  WITH CHECK (reviewer_user_id = auth.uid() AND public.is_email_allowed(auth.uid()));

CREATE POLICY "internal allow-list updates own scores"
  ON public.transformation_eval_scores FOR UPDATE TO authenticated
  USING (reviewer_user_id = auth.uid() AND public.is_email_allowed(auth.uid()))
  WITH CHECK (reviewer_user_id = auth.uid() AND public.is_email_allowed(auth.uid()));