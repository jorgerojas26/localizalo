-- Public server-side search RPC for the web landing page.
-- Exposes a fuzzy, ranked search over localize.persons without granting direct table read to anon.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE OR REPLACE FUNCTION localize.search_persons(
    search_query TEXT,
    result_limit INTEGER DEFAULT 50
)
RETURNS SETOF localize.persons
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = localize, public, pg_temp
AS $$
DECLARE
    q TEXT;
BEGIN
    q := trim(coalesce(search_query, ''));

    IF q = '' THEN
        RETURN QUERY
        SELECT *
        FROM localize.persons
        ORDER BY updated_at DESC
        LIMIT result_limit;
        RETURN;
    END IF;

    RETURN QUERY
    SELECT *
    FROM localize.persons p
    WHERE
        p.full_name ILIKE '%' || q || '%'
        OR p.given_name ILIKE '%' || q || '%'
        OR p.family_name ILIKE '%' || q || '%'
        OR p.last_known_location ILIKE '%' || q || '%'
        OR p.full_name % q
        OR similarity(p.full_name, q) > 0.25
    ORDER BY
        GREATEST(
            similarity(coalesce(p.full_name, ''), q),
            similarity(coalesce(p.given_name, '') || ' ' || coalesce(p.family_name, ''), q),
            similarity(coalesce(p.last_known_location, ''), q)
        ) DESC,
        p.updated_at DESC
    LIMIT result_limit;
END;
$$;

REVOKE ALL ON FUNCTION localize.search_persons(TEXT, INTEGER) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION localize.search_persons(TEXT, INTEGER) TO anon;
GRANT EXECUTE ON FUNCTION localize.search_persons(TEXT, INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION localize.search_persons(TEXT, INTEGER) TO service_role;
