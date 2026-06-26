ALTER TABLE localize.notes ADD COLUMN IF NOT EXISTS note_record_id TEXT;
CREATE INDEX IF NOT EXISTS idx_notes_record_id ON localize.notes(note_record_id);
