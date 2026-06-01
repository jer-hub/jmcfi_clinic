-- Mirrors core/sql/enable_supabase_rls.sql
-- Prefer: python manage.py migrate (core.0024_supabase_rls_deny_policies)

-- Lock down public tables for Supabase PostgREST (anon/authenticated).
-- Django connects as postgres (superuser) and is unaffected.
-- Safe to re-run after new Django migrations create tables.

CREATE SCHEMA IF NOT EXISTS jmcfi_private;

CREATE OR REPLACE FUNCTION jmcfi_private.lock_down_public_table(target regclass)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', target);
  EXECUTE format(
    'DROP POLICY IF EXISTS jmcfi_deny_postgrest_access ON %s',
    target
  );
  EXECUTE format(
    'CREATE POLICY jmcfi_deny_postgrest_access ON %s '
    'FOR ALL TO anon, authenticated '
    'USING (false) WITH CHECK (false)',
    target
  );
END;
$$;

REVOKE ALL ON FUNCTION jmcfi_private.lock_down_public_table(regclass) FROM PUBLIC;
REVOKE ALL ON FUNCTION jmcfi_private.lock_down_public_table(regclass) FROM anon, authenticated;

DO $$
DECLARE
  t record;
BEGIN
  FOR t IN
    SELECT schemaname, tablename
    FROM pg_tables
    WHERE schemaname = 'public'
  LOOP
    PERFORM jmcfi_private.lock_down_public_table(
      format('%I.%I', t.schemaname, t.tablename)::regclass
    );
  END LOOP;
END $$;

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL ROUTINES IN SCHEMA public FROM anon, authenticated;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  REVOKE ALL ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  REVOKE ALL ON SEQUENCES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  REVOKE ALL ON ROUTINES FROM anon, authenticated;

DROP EVENT TRIGGER IF EXISTS jmcfi_rls_on_public_table_create;
DROP FUNCTION IF EXISTS public.jmcfi_enable_rls_on_public_table();
DROP FUNCTION IF EXISTS jmcfi_private.enable_rls_on_public_table();

CREATE OR REPLACE FUNCTION jmcfi_private.enable_rls_on_public_table()
RETURNS event_trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  cmd record;
BEGIN
  FOR cmd IN
    SELECT *
    FROM pg_event_trigger_ddl_commands()
    WHERE command_tag IN ('CREATE TABLE', 'CREATE TABLE AS')
      AND schema_name = 'public'
  LOOP
    PERFORM jmcfi_private.lock_down_public_table(cmd.objid::regclass);
  END LOOP;
END;
$$;

REVOKE ALL ON FUNCTION jmcfi_private.enable_rls_on_public_table() FROM PUBLIC;
REVOKE ALL ON FUNCTION jmcfi_private.enable_rls_on_public_table() FROM anon, authenticated;

CREATE EVENT TRIGGER jmcfi_rls_on_public_table_create
  ON ddl_command_end
  WHEN TAG IN ('CREATE TABLE', 'CREATE TABLE AS')
  EXECUTE FUNCTION jmcfi_private.enable_rls_on_public_table();
