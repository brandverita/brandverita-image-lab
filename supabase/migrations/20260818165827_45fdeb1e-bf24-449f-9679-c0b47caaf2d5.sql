REVOKE ALL ON FUNCTION public.current_user_allowed() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.current_user_allowed() TO authenticated;