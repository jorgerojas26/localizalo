"""
Bulk PFIF 1.5 XML file importer.

Parses a local PFIF XML file, runs the full dedup pipeline in memory,
then bulk-inserts new persons via a single PostgreSQL RPC call per batch.

Usage:
    python -m etl.import_file_bulk /path/to/records.xml

Environment variables required:
    SUPABASE_URL, SUPABASE_SERVICE_KEY
"""

import argparse
import hashlib
import logging
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from xml.etree.ElementTree import parse as xml_parse

from etl import db
from etl.dedup import phonetic_hash, is_match, is_full_match
from etl.normalize import normalize_location
from etl.sources.loader import PFIF_NS, _parse_pfif_person, sanitize_record

log = logging.getLogger(__name__)

SOURCE_ID = "pfif-file-import"


def person_record_id(ph: str, location: str | None) -> str:
    key = f"{ph}|{location or ''}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def parse_pfif_file(filepath: str) -> list[dict]:
    path = filepath if isinstance(filepath, str) else str(filepath)
    import os as _os
    if not _os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

    log.info("Parsing %s ...", path)
    tree = xml_parse(path)
    root = tree.getroot()

    ns = f"{{{PFIF_NS}}}"
    persons = root.findall(f".//{ns}person")
    if not persons:
        persons = root.findall(".//{*}person")

    log.info("Found %d <person> elements", len(persons))

    records = []
    skipped = 0
    no_date = 0
    for p in persons:
        raw = _parse_pfif_person(p)
        clean = sanitize_record(raw)
        if clean:
            if not clean.get("source_date"):
                clean["source_date"] = "1970-01-01T00:00:01Z"
                no_date += 1
            records.append(clean)
        else:
            skipped += 1

    if skipped:
        log.warning("Skipped %d records (missing full_name or external_id)", skipped)
    if no_date:
        log.warning("Assigned default source_date to %d records", no_date)

    log.info("Parsed %d valid records", len(records))
    return records


def _build_person(record: dict, pid: str, ph: str, loc_norm: str | None, now: str) -> dict:
    return {
        "person_record_id": pid,
        "full_name": record["full_name"],
        "given_name": record.get("given_name"),
        "family_name": record.get("family_name"),
        "age": record.get("age"),
        "last_known_location": record.get("last_known_location"),
        "description": record.get("description"),
        "photo_url": record.get("photo_url"),
        "status": record.get("status") or "unknown",
        "author_name": record.get("author_name"),
        "phonetic_hash": ph,
        "location_normalized": loc_norm,
        "created_at": now,
        "updated_at": now,
    }


def _build_source_record(record: dict, pid: str, source_id: str) -> dict:
    return {
        "person_record_id": pid,
        "source_id": source_id,
        "external_id": record["external_id"],
        "source_date": record.get("source_date"),
        "contacto": record.get("contacto"),
        "localizado_por": record.get("localizado_por"),
        "localizado_contacto": record.get("localizado_contacto"),
        "localizado_relacion": record.get("localizado_relacion"),
        "localizado_nota": record.get("localizado_nota"),
    }


def _build_note_text(record: dict, namespace: str) -> str:
    parts = [
        f"Registro tambien reportado por {namespace}.",
        f"ID original: {record.get('external_id', '')}.",
    ]
    if record.get("photo_url"):
        parts.append(f"Foto: {record['photo_url']}")
    if record.get("localizado_nota"):
        parts.append(f"Nota: {record['localizado_nota']}")
    return " | ".join(parts)


def _load_existing_persons(client) -> tuple[dict[str, dict], dict]:
    """Fetch all existing persons as:
    1. dict keyed by person_record_id (for exact pid lookup)
    2. dict keyed by (phonetic_hash, location_normalized) -> list of persons
       (for in-memory phonetic matching — avoids N individual RPC calls)
    """
    by_pid = {}
    by_ph_loc: dict[tuple, list] = {}
    for page in db.get_all_persons_paged(client):
        for p in page:
            pid = p["person_record_id"]
            by_pid[pid] = p
            key = (p.get("phonetic_hash"), p.get("location_normalized"))
            if key not in by_ph_loc:
                by_ph_loc[key] = []
            by_ph_loc[key].append(p)
    log.info("Loaded %d existing persons from DB", len(by_pid))
    return by_pid, by_ph_loc


def _phonetic_match_in_memory(name: str, ph: str, loc_norm: str | None,
                                by_ph_loc: dict) -> dict | None:
    """Check if an incoming record matches any existing person via in-memory
    phonetic index. Same logic as db.find_person_by_phonetic_match but no RPC."""
    key = (ph, loc_norm)
    for candidate in by_ph_loc.get(key, []):
        if is_match(name, candidate["full_name"]):
            return candidate
    return None


def _compute_watermark(max_dt: datetime | None, last_run: str) -> str:
    if max_dt is None:
        return last_run
    return (max_dt - timedelta(seconds=1)).isoformat()


def run_bulk(filepath: str, batch_size: int = 1000):
    client = db.get_client()

    # Ensure source exists
    db.ensure_source_exists(
        client, SOURCE_ID, "Import from PFIF file (bulk)", "pfif-file-import.local"
    )

    last_run = db.get_etl_state(client, SOURCE_ID) or os.environ.get(
        "ETL_DEFAULT_UPDATED_AFTER", "1970-01-01T00:00:00Z"
    )
    now = datetime.now(timezone.utc).isoformat()
    run_id = str(uuid.uuid4())

    # 1. Parse file
    records = parse_pfif_file(filepath)
    if not records:
        log.error("No valid records found.")
        return

    # 2. Normalize + hash in memory
    log.info("Normalizing and hashing %d records...", len(records))
    enriched = []
    max_source_dt: datetime | None = None
    for rec in records:
        loc_norm = normalize_location(rec.get("last_known_location"))
        ph = phonetic_hash(rec["full_name"])
        pid = person_record_id(ph, loc_norm)
        enriched.append((rec, pid, ph, loc_norm))

        sd = rec.get("source_date")
        if sd is not None:
            try:
                dt = datetime.fromisoformat(sd)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if max_source_dt is None or dt > max_source_dt:
                    max_source_dt = dt
            except (ValueError, TypeError):
                pass

    # 3. Fetch existing persons for dedup
    existing_by_pid, existing_by_ph_loc = _load_existing_persons(client)

    # 4. Classify records: create, merge (cross-source), skip (same source)
    to_create: list[dict] = []  # {person: ..., source_record: ...}
    stats = {"created": 0, "merged": 0, "updated": 0, "errors": 0, "total": 0}

    namespace = "pfif-file-import.local"

    for rec, pid, ph, loc_norm in enriched:
        stats["total"] += 1
        existing_person = existing_by_pid.get(pid)

        if existing_person:
            same_source = db.source_record_exists(
                client, pid, SOURCE_ID, rec["external_id"]
            )
            if not is_full_match(
                rec["full_name"], existing_person["full_name"],
                rec.get("age"), existing_person.get("age"),
                rec.get("contacto"), existing_person.get("contacto"),
            ):
                # PID collision — different person, add discriminator
                discriminator = hashlib.sha256(
                    f"{SOURCE_ID}|{rec['external_id']}".encode()
                ).hexdigest()[:8]
                pid = f"{pid}-{discriminator}"
                existing_person = None
            elif same_source:
                # Same source refresh — use individual RPC
                try:
                    db.atomic_upsert_person(
                        client,
                        _build_person(rec, pid, ph, loc_norm, now),
                        _build_source_record(rec, pid, SOURCE_ID),
                    )
                    stats["updated"] += 1
                except Exception:
                    log.exception("Failed to refresh record %s", rec.get("external_id"))
                    stats["errors"] += 1
                continue
            else:
                # Cross-source match — merge as note
                try:
                    note_text = _build_note_text(rec, namespace)
                    db.atomic_merge_note(
                        client,
                        {
                            "person_record_id": pid,
                            "note_record_id": db.compute_note_record_id(
                                pid, SOURCE_ID, rec["external_id"]
                            ),
                            "note_text": note_text,
                            "author_name": rec.get("author_name"),
                            "status": rec.get("status"),
                            "source_date": rec.get("source_date"),
                            "created_at": now,
                        },
                        _build_source_record(rec, pid, SOURCE_ID),
                    )
                    stats["merged"] += 1
                except Exception:
                    log.exception("Failed to merge record %s", rec.get("external_id"))
                    stats["errors"] += 1
                continue

        if not existing_person:
            # In-memory phonetic match (fast — no RPC per record)
            match = _phonetic_match_in_memory(
                rec["full_name"], ph, loc_norm, existing_by_ph_loc
            )
            if match:
                try:
                    note_text = _build_note_text(rec, namespace)
                    db.atomic_merge_note(
                        client,
                        {
                            "person_record_id": match["person_record_id"],
                            "note_record_id": db.compute_note_record_id(
                                match["person_record_id"], SOURCE_ID, rec["external_id"]
                            ),
                            "note_text": note_text,
                            "author_name": rec.get("author_name"),
                            "status": rec.get("status"),
                            "source_date": rec.get("source_date"),
                            "created_at": now,
                        },
                        _build_source_record(rec, match["person_record_id"], SOURCE_ID),
                    )
                    stats["merged"] += 1
                except Exception:
                    log.exception("Failed to merge-phonetic record %s", rec.get("external_id"))
                    stats["errors"] += 1
                continue

            # No match — add to bulk create batch
            to_create.append({
                "person": _build_person(rec, pid, ph, loc_norm, now),
                "source_record": _build_source_record(rec, pid, SOURCE_ID),
            })

    log.info(
        "Classification complete: %d to create, %d to merge, %d to refresh, %d errors",
        len(to_create), stats["merged"], stats["updated"], stats["errors"],
    )

    # 5. De-duplicate within to_create (same pid = same phonetic+location = same person).
    # Keep first occurrence, log the rest as intra-file duplicates.
    seen_pids: set[str] = set()
    deduped_create: list[dict] = []
    intra_dup = 0
    for entry in to_create:
        pid = entry["person"]["person_record_id"]
        if pid in seen_pids:
            intra_dup += 1
        else:
            seen_pids.add(pid)
            deduped_create.append(entry)
    if intra_dup:
        log.warning("Skipped %d intra-file duplicates (same person_record_id)", intra_dup)

    # 6. Bulk insert
    total_create = len(deduped_create)
    for i in range(0, total_create, batch_size):
        chunk = deduped_create[i : i + batch_size]
        log.info("Bulk-upserting chunk %d/%d (%d records)...",
                 i // batch_size + 1, (total_create + batch_size - 1) // batch_size, len(chunk))
        try:
            result = client.schema("localize").rpc(
                "atomic_bulk_upsert_persons",
                {"_records": chunk},
            ).execute()
            stats["created"] += len(chunk)
        except Exception:
            log.exception("Bulk upsert failed for chunk at offset %d", i)
            stats["errors"] += len(chunk)

    # 6. Update watermark
    watermark = _compute_watermark(max_source_dt, last_run)
    if stats["errors"] == 0:
        db.update_etl_state_watermark(client, SOURCE_ID, watermark, run_id)
    else:
        log.warning("%d errors — watermark NOT advanced", stats["errors"])

    log.info(
        "Import summary: total=%d created=%d merged=%d updated=%d errors=%d run_id=%s",
        stats["total"], stats["created"], stats["merged"], stats["updated"], stats["errors"], run_id,
    )


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    sentry_dsn = os.environ.get("SENTRY_DSN")
    if sentry_dsn:
        try:
            import sentry_sdk
            sentry_sdk.init(
                dsn=sentry_dsn,
                traces_sample_rate=0.0,
                environment=os.environ.get("ENVIRONMENT", "production"),
            )
        except ImportError:
            pass

    parser = argparse.ArgumentParser(
        description="Bulk-import a PFIF 1.5 XML file into the ETL pipeline"
    )
    parser.add_argument("file", help="Path to the PFIF 1.5 XML file")
    parser.add_argument(
        "--batch-size", type=int, default=1000,
        help="Records per bulk RPC call (default: 1000)"
    )
    args = parser.parse_args()

    run_bulk(args.file, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
