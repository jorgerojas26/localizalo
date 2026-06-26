CREATE SCHEMA IF NOT EXISTS localize;

CREATE TABLE localize.sources (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    namespace   TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE localize.etl_state (
    source_id   TEXT PRIMARY KEY REFERENCES localize.sources(id),
    last_run    TIMESTAMPTZ
);

CREATE TABLE localize.persons (
    person_record_id     TEXT PRIMARY KEY,
    full_name            TEXT NOT NULL,
    given_name           TEXT,
    family_name          TEXT,
    age                  INTEGER,
    last_known_location  TEXT,
    description          TEXT,
    photo_url            TEXT,
    status               TEXT NOT NULL DEFAULT 'unknown',
    author_name          TEXT,
    phonetic_hash        TEXT,
    location_normalized  TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_persons_phonetic ON localize.persons(phonetic_hash);
CREATE INDEX idx_persons_location  ON localize.persons(location_normalized);

CREATE TABLE localize.source_records (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_record_id     TEXT NOT NULL REFERENCES localize.persons(person_record_id),
    source_id            TEXT NOT NULL REFERENCES localize.sources(id),
    external_id          TEXT NOT NULL,
    source_date          TIMESTAMPTZ,
    contacto             TEXT,
    localizado_por       TEXT,
    localizado_contacto  TEXT,
    localizado_relacion  TEXT,
    localizado_nota      TEXT,
    fetched_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(source_id, external_id)
);

CREATE INDEX idx_source_records_person ON localize.source_records(person_record_id);

CREATE TABLE localize.notes (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_record_id     TEXT NOT NULL REFERENCES localize.persons(person_record_id),
    note_text            TEXT,
    author_name          TEXT,
    status               TEXT,
    source_date          TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_notes_person ON localize.notes(person_record_id);

ALTER TABLE localize.sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE localize.etl_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE localize.persons ENABLE ROW LEVEL SECURITY;
ALTER TABLE localize.source_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE localize.notes ENABLE ROW LEVEL SECURITY;
