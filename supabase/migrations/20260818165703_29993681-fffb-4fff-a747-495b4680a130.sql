CREATE TABLE public.allowed_emails (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text NOT NULL UNIQUE,
  note text,
  created_at timestamptz NOT NULL DEFAULT now()
);

GRANT ALL ON public.allowed_emails TO service_role;

ALTER TABLE public.allowed_emails ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION public.is_email_allowed(_user_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM auth.users u
    JOIN public.allowed_emails a ON lower(a.email) = lower(u.email)
    WHERE u.id = _user_id
  )
$$;

CREATE OR REPLACE FUNCTION public.current_user_allowed()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT public.is_email_allowed(auth.uid())
$$;

REVOKE ALL ON FUNCTION public.is_email_allowed(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.current_user_allowed() TO authenticated;

DROP POLICY IF EXISTS "Users can view their own generation jobs" ON public.generation_jobs;
CREATE POLICY "Approved users can view their own generation jobs"
ON public.generation_jobs FOR SELECT TO authenticated
USING (auth.uid() = user_id AND public.is_email_allowed(auth.uid()));

DROP POLICY IF EXISTS "Users can view their own usage" ON public.generation_usage;
CREATE POLICY "Approved users can view their own usage"
ON public.generation_usage FOR SELECT TO authenticated
USING (auth.uid() = user_id AND public.is_email_allowed(auth.uid()));