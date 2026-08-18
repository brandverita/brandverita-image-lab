REVOKE ALL ON FUNCTION public.is_email_allowed(uuid) FROM anon, authenticated;
REVOKE ALL ON FUNCTION public.update_updated_at_column() FROM anon, authenticated, PUBLIC;
REVOKE ALL ON FUNCTION public.current_user_allowed() FROM anon;