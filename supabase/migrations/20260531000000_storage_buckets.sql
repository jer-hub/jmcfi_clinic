-- Storage buckets for JMCFI Clinic (Django owns app schema via manage.py migrate)
-- Apply with: supabase db reset  OR  supabase migration up

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES
  (
    'clinic-private',
    'clinic-private',
    false,
    52428800,
    NULL
  ),
  (
    'clinic-public',
    'clinic-public',
    true,
    10485760,
    ARRAY['image/jpeg', 'image/png', 'image/gif', 'image/webp']::text[]
  )
ON CONFLICT (id) DO NOTHING;

-- Service role can manage all objects (Django uses S3 keys server-side)
CREATE POLICY "service_role_all_clinic_private"
ON storage.objects FOR ALL
TO service_role
USING (bucket_id = 'clinic-private')
WITH CHECK (bucket_id = 'clinic-private');

CREATE POLICY "service_role_all_clinic_public"
ON storage.objects FOR ALL
TO service_role
USING (bucket_id = 'clinic-public')
WITH CHECK (bucket_id = 'clinic-public');

-- Public read for health-tip images in clinic-public
CREATE POLICY "public_read_clinic_public"
ON storage.objects FOR SELECT
TO public
USING (bucket_id = 'clinic-public');
