-- Server-side trigram-based fuzzy match for phonetic deduplication.
-- Replaces the slow Python pagination loop in find_person_by_phonetic_match.

CREATE OR REPLACE FUNCTION localize.trigram_match_persons(
    _name TEXT,
    _location TEXT DEFAULT NULL,
    _limit INTEGER DEFAULT 50
) RETURNS SETOF localize.persons
LANGUAGE plpgsql STABLE
AS $$
BEGIN
    IF _location IS NOT NULL THEN
        RETURN QUERY
        SELECT p.*
        FROM localize.persons p
        WHERE p.location_normalized = _location
          AND (p.full_name % _name OR similarity(p.full_name, _name) > 0.3)
        ORDER BY similarity(p.full_name, _name) DESC
        LIMIT _limit;
    ELSE
        RETURN QUERY
        SELECT p.*
        FROM localize.persons p
        WHERE p.full_name % _name OR similarity(p.full_name, _name) > 0.3
        ORDER BY similarity(p.full_name, _name) DESC
        LIMIT _limit;
    END IF;
END;
$$;

REVOKE ALL ON FUNCTION localize.trigram_match_persons(TEXT, TEXT, INTEGER) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION localize.trigram_match_persons(TEXT, TEXT, INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION localize.trigram_match_persons(TEXT, TEXT, INTEGER) TO service_role;
