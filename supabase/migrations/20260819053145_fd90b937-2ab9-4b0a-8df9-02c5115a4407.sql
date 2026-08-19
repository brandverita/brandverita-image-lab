GRANT SELECT ON public.generation_jobs TO authenticated;
GRANT SELECT ON public.generation_usage TO authenticated;
GRANT SELECT ON public.allowed_emails TO authenticated;
GRANT ALL ON public.generation_jobs TO service_role;
GRANT ALL ON public.generation_usage TO service_role;
GRANT ALL ON public.allowed_emails TO service_role;