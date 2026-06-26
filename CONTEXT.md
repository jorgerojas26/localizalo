# Localizalo.org

ETL pipeline that consolidates missing persons reports from multiple sources after the 2026 Venezuela earthquake, deduplicates via phonetic matching, and exports to PFIF 1.5.

## Language

**Person**:
A missing person record in the canonical database.
_Avoid_: Desaparecido, victim, entry

**Source**:
An external API from which raw records are fetched (e.g. desaparecidos-terremoto-api.theempire.tech).
_Avoid_: Data source, provider, origin

**Source PFIF Contract**:
Each Source exposes `GET /pfif?updated_after=<ISO>&limit=<int>`. The preferred wire format is PFIF 1.5 XML (client sends `Accept: application/xml`); JSON array format is also accepted for legacy sources (Content-Type negotiated). The ETL never scrapes HTML or calls proprietary JSON endpoints.

**Source Record**:
A single raw PFIF `<person>` element as received from a Source. Stored in `source_records` with its raw XML; the Source's `person_record_id` becomes `source_records.external_id`.

**Canonical Schema**:
The unified internal schema (Supabase `persons` table) into which all Source Records are transformed, deduplicated, and merged before PFIF re-export.

**person_record_id**:
Deterministic identifier derived as `sha256(phonetic_hash + "|" + normalized_location)[:16]`. The ETL generates this, ignoring the Source's native ID. Guarantees the same person+location always maps to the same ID across sources.

**Phonetic Match**:
Two Person records are considered the same if Double Metaphone phonetic closeness >= PHONETIC_THRESHOLD (0.8) and (Levenshtein ratio on stripped names >= NAME_SIMILARITY_THRESHOLD (0.9) or Spanish-phonetic-key Levenshtein ratio >= NAME_SIMILARITY_THRESHOLD (0.9)), and their normalized locations match. The algorithm merges them under one person_record_id and adds the second source's data as a historical note.

**Reconciliation**:
Background RPC `reconcile_duplicate_persons` merges cross-source duplicate Persons created by parallel ingest races (distinct person_record_id from typos changing the phonetic_hash). Runs once per consolidator cycle, processes disjoint pairs per batch to avoid transitivity errors, and authors an audit note on the survivor.

**PFIF**:
Person Finder Interchange Format v1.5 — the XML export format for missing person data interoperability.
