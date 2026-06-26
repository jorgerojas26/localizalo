-- Add pg_trgm extension and trigram indexes for fuzzy name matching
-- during phonetic deduplication of person records.
-- Enables SQL-side similarity() queries to replace the slow Python
-- per-row is_match() loop in find_person_by_phonetic_match.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Default trigram similarity threshold; runtime queries may override
-- with SET pg_trgm.similarity_threshold = <value>.
SET pg_trgm.similarity_threshold = 0.3;

-- GIN trigram indexes on person text columns for fuzzy matching
CREATE INDEX IF NOT EXISTS idx_persons_full_name_trgm
    ON localize.persons USING gin (full_name extensions.gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_persons_phonetic_hash_trgm
    ON localize.persons USING gin (phonetic_hash extensions.gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_persons_location_trgm
    ON localize.persons USING gin (last_known_location extensions.gin_trgm_ops);

-- Composite btree index for the fast-path exact-match query
CREATE INDEX IF NOT EXISTS idx_persons_loc_phonetic
    ON localize.persons(location_normalized, phonetic_hash);
