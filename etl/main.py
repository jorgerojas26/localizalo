import argparse
import hashlib
import uuid
import logging
from datetime import datetime, timezone

from etl import db
from etl.dedup import phonetic_hash
from etl.export_pfif import export_pfif
from etl.normalize import normalize_location
from etl.sources.loader import fetch as source_fetch
from etl.sources.loader import get_source, list_source_ids
from etl.stats import RunStats

log = logging.getLogger(__name__)


def person_record_id(ph: str, location: str | None) -> str:
    key = f"{ph}|{location or ''}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _build_note_text(record: dict, source_config: dict) -> str:
    parts = [
        f"Registro también reportado por {source_config['namespace']}.",
        f"ID original: {record.get('external_id', '')}.",
    ]
    if record.get("contacto"):
        parts.append(f"Contacto: {record['contacto']}")
    if record.get("photo_url"):
        parts.append(f"Foto: {record['photo_url']}")
    if record.get("localizado_nota"):
        parts.append(f"Nota: {record['localizado_nota']}")
    return " | ".join(parts)


def run(source_id: str) -> None:
    client = db.get_client()
    source_config = get_source(source_id)
    stats = RunStats(source_id=source_id)

    last_run = db.get_etl_state(client, source_id) or "1970-01-01T00:00:00Z"
    records = source_fetch(source_config, updated_after=last_run)

    stats.total_fetched = len(records)
    log.info("Fetched %d records from source %s (since %s)", stats.total_fetched, source_id, last_run)

    now = datetime.now(timezone.utc).isoformat()
    run_id = str(uuid.uuid4())

    for record in records:
        try:
            loc_norm = normalize_location(record.get("last_known_location"))
            ph = phonetic_hash(record["full_name"])
            pid = person_record_id(ph, loc_norm)

            existing = db.find_person_by_id(client, pid)

            if existing:
                db.update_person(
                    client,
                    pid,
                    {
                        "full_name": record["full_name"],
                        "age": record.get("age"),
                        "last_known_location": record.get("last_known_location"),
                        "description": record.get("description"),
                        "photo_url": record.get("photo_url"),
                        "status": record.get("status", "unknown"),
                        "updated_at": now,
                    },
                )
                stats.updated += 1
            else:
                match = None
                if loc_norm is not None:
                    match = db.find_person_by_phonetic_match(
                        client, record["full_name"], loc_norm
                    )
                if match:
                    note_text = _build_note_text(record, source_config)
                    db.add_note(
                        client,
                        {
                            "id": str(uuid.uuid4()),
                            "person_record_id": match["person_record_id"],
                            "note_text": note_text,
                            "note_record_id": hashlib.sha256(
                                f"{match['person_record_id']}|{note_text}|{record.get('source_date', '')}".encode()
                            ).hexdigest()[:16],
                            "author_name": record.get("author_name"),
                            "status": record.get("status"),
                            "source_date": record.get("source_date"),
                            "created_at": now,
                        },
                    )
                    stats.merged += 1
                    stats.notes_added += 1
                else:
                    db.create_person(
                        client,
                        {
                            "person_record_id": pid,
                            "full_name": record["full_name"],
                            "given_name": record.get("given_name"),
                            "family_name": record.get("family_name"),
                            "age": record.get("age"),
                            "last_known_location": record.get("last_known_location"),
                            "description": record.get("description"),
                            "photo_url": record.get("photo_url"),
                            "status": record.get("status", "unknown"),
                            "author_name": record.get("author_name"),
                            "phonetic_hash": ph,
                            "location_normalized": loc_norm,
                            "created_at": now,
                            "updated_at": now,
                        },
                    )
                    stats.created += 1

            db.upsert_source_record(
                client,
                {
                    "person_record_id": pid,
                    "source_id": source_id,
                    "external_id": record["external_id"],
                    "source_date": record.get("source_date"),
                    "contacto": record.get("contacto"),
                    "localizado_por": record.get("localizado_por"),
                    "localizado_contacto": record.get("localizado_contacto"),
                    "localizado_relacion": record.get("localizado_relacion"),
                    "localizado_nota": record.get("localizado_nota"),
                },
            )
            stats.source_records_upserted += 1
        except Exception:
            log.exception("Failed to process record external_id=%s", record.get("external_id"))
            stats.errors += 1

    db.update_etl_state_run(client, source_id, now, run_id)

    persons = db.get_all_persons(client)
    notes = db.get_all_notes(client)
    pfif_xml = export_pfif(persons, notes)
    stats.persons_exported = len(persons)
    stats.pfif_bytes = len(pfif_xml)
    log.info("Exported %d persons, %d notes, XML size %d bytes", stats.persons_exported, len(notes), stats.pfif_bytes)
    db.upload_pfif(client, pfif_xml)
    log.info("Upload completed for source %s", source_id)

    stats.log_summary()
    stats.exit_if_errors()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Run ETL for a source")
    parser.add_argument("--source", required=True, choices=list_source_ids())
    args = parser.parse_args()
    run(args.source)


if __name__ == "__main__":
    main()
