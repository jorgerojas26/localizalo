-- Add source_id and external_id columns to notes table for note_record_id
-- composition (new formula: sha256(person|source|external)[:16]).
-- Backfill legacy rows from source_records via person_record_id + source_date join.
-- Update atomic_merge_note to INSERT with the new columns and ON CONFLICT DO UPDATE.

ALTER TABLE localize.notes ADD COLUMN IF NOT EXISTS source_id TEXT;
ALTER TABLE localize.notes ADD COLUMN IF NOT EXISTS external_id TEXT;

-- Best-effort backfill for legacy rows where source_id/external_id can be matched
UPDATE localize.notes n
SET source_id = sr.source_id,
    external_id = sr.external_id
FROM localize.source_records sr
WHERE sr.person_record_id = n.person_record_id
  AND sr.source_date IS NOT DISTINCT FROM n.source_date
  AND n.source_id IS NULL;

CREATE OR REPLACE FUNCTION localize.atomic_merge_note(
    _person_record_id TEXT,
    _note_record_id TEXT,
    _note_text TEXT,
    _author_name TEXT,
    _status TEXT,
    _source_date TIMESTAMPTZ,
    _created_at TIMESTAMPTZ,
    _source_id TEXT,
    _external_id TEXT,
    _contacto TEXT,
    _localizado_por TEXT,
    _localizado_contacto TEXT,
    _localizado_relacion TEXT,
    _localizado_nota TEXT
) RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    INSERT INTO localize.source_records (
        person_record_id, source_id, external_id, source_date,
        contacto, localizado_por, localizado_contacto,
        localizado_relacion, localizado_nota
    ) VALUES (
        _person_record_id, _source_id, _external_id, _source_date,
        _contacto, _localizado_por, _localizado_contacto,
        _localizado_relacion, _localizado_nota
    )
    ON CONFLICT (source_id, external_id) DO UPDATE SET
        person_record_id = EXCLUDED.person_record_id,
        source_date = COALESCE(EXCLUDED.source_date, source_records.source_date),
        contacto = COALESCE(EXCLUDED.contacto, source_records.contacto),
        localizado_por = COALESCE(EXCLUDED.localizado_por, source_records.localizado_por),
        localizado_contacto = COALESCE(EXCLUDED.localizado_contacto, source_records.localizado_contacto),
        localizado_relacion = COALESCE(EXCLUDED.localizado_relacion, source_records.localizado_relacion),
        localizado_nota = COALESCE(EXCLUDED.localizado_nota, source_records.localizado_nota);

    INSERT INTO localize.notes (
        person_record_id, note_text, author_name, status, source_date, created_at,
        note_record_id, source_id, external_id
    ) VALUES (
        _person_record_id, _note_text, _author_name, _status, _source_date, _created_at,
        _note_record_id, _source_id, _external_id
    )
    ON CONFLICT (note_record_id) DO UPDATE SET
        source_id = COALESCE(EXCLUDED.source_id, notes.source_id),
        external_id = COALESCE(EXCLUDED.external_id, notes.external_id);
END;
$$;

REVOKE EXECUTE ON FUNCTION localize.atomic_merge_note(
    TEXT, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ, TIMESTAMPTZ,
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT
) FROM PUBLIC;

REVOKE EXECUTE ON FUNCTION localize.atomic_merge_note(
    TEXT, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ, TIMESTAMPTZ,
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT
) FROM authenticated;

GRANT EXECUTE ON FUNCTION localize.atomic_merge_note(
    TEXT, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ, TIMESTAMPTZ,
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT
) TO service_role;
