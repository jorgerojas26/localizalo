-- Grant schema usage and table permissions for PostgREST to access the localize schema.
-- Without these grants, even the service_role key gets "permission denied for schema localize" (HTTP 403).

GRANT USAGE ON SCHEMA localize TO anon, authenticated, service_role;

-- Service role and authenticated (used by ETL via service_role key) need full DML
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA localize TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA localize TO service_role;

-- Anon gets read-only (SELECT) — write access is via SECURITY DEFINER RPC functions only
GRANT SELECT ON ALL TABLES IN SCHEMA localize TO anon;

-- Ensure future tables in localize get the same grants
ALTER DEFAULT PRIVILEGES IN SCHEMA localize
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA localize
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA localize
    GRANT SELECT ON TABLES TO anon;
