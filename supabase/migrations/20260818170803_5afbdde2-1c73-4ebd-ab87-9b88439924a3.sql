INSERT INTO public.allowed_emails (email, note)
SELECT 'brandverita@gmail.com', 'primary test account'
WHERE NOT EXISTS (
  SELECT 1 FROM public.allowed_emails WHERE lower(email) = 'brandverita@gmail.com'
);