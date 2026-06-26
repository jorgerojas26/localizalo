import argparse
import hashlib
import os
import uuid
import logging
import sys
from datetime import datetime, timezone

try:
    import sentry_sdk
except ImportError:
    sentry_sdk = None  # type: ignore[assignment]

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
    if record.get("photo_url"):
        parts.append(f"Foto: {record['photo_url']}")
    if record.get("localizado_nota"):
        parts.append(f"Nota: {record['localizado_nota']}")
    return " | ".join(parts)


def run(source_id: str) -> None:
    """Run ETL pipeline for a single source.

    Idempotency guarantees:
    - person_record_id is deterministic (sha256(phonetic_hash|normalized_location)[:16])
    - atomic_upsert_person uses ON CONFLICT DO UPDATE on person_record_id
    - source_records use ON CONFLICT (source_id, external_id)
    - notes use ON CONFLICT (note_record_id) where note_record_id is deterministic
    - etl_state is only updated after successful export+upload
    Safe to re-run or run concurrently across different sources.
    """
    client = db.get_client()
    source_config = get_source(source_id)
    stats = RunStats(source_id=source_id)

    _default_after = os.environ.get("ETL_DEFAULT_UPDATED_AFTER", "1970-01-01T00:00:00Z")
    last_run = db.get_etl_state(client, source_id) or _default_after
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
                db.atomic_upsert_person(
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
                stats.updated += 1
                stats.source_records_upserted += 1
            else:
                match = db.find_person_by_phonetic_match(
                    client, record["full_name"], loc_norm
                )
                # Merge is atomic via RPC — note + source_record inserted in single transaction.
                # ON CONFLICT (note_record_id) DO NOTHING handles cross-source races safely.
                if match:
                    note_text = _build_note_text(record, source_config)
                    db.atomic_merge_note(
                        client,
                        {
                            "person_record_id": match["person_record_id"],
                            "note_record_id": db.compute_note_record_id(
                                match["person_record_id"], note_text, record.get("source_date", "")
                            ),
                            "note_text": note_text,
                            "author_name": record.get("author_name"),
                            "status": record.get("status"),
                            "source_date": record.get("source_date"),
                            "created_at": now,
                        },
                        {
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
                    stats.merged += 1
                    stats.notes_added += 1
                    stats.source_records_upserted += 1
                else:
                    db.atomic_upsert_person(
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
                    stats.created += 1
                    stats.source_records_upserted += 1
        except Exception:
            log.exception("Failed to process record external_id=%s", record.get("external_id"))
            if sentry_sdk:
                sentry_sdk.capture_exception()
            stats.errors += 1

    if stats.created + stats.updated + stats.merged + stats.notes_added == 0:
        log.info("No changes detected. Skipping export and upload.")
        db.update_etl_state_run(client, source_id, now, run_id)
        stats.run_id = run_id
        stats.log_summary()
        return

    pfif_xml = export_pfif(
        db.get_all_persons_paged(client),
        db.get_all_notes_paged(client),
    )
    stats.persons_exported = db.count_persons(client)
    stats.pfif_bytes = len(pfif_xml)
    log.info("Exported %d persons, %d notes, XML size %d bytes", stats.persons_exported, db.count_notes(client), stats.pfif_bytes)

    try:
        db.upload_pfif(client, pfif_xml, run_id)
        log.info("Upload completed for source %s (run %s)", source_id, run_id)
    except Exception:
        log.exception("PFIF upload failed for source %s. etl_state NOT updated.", source_id)
        stats.errors += 1
        stats.run_id = run_id
        stats.log_summary()
        sys.exit(1)

    if stats.errors == 0:
        db.update_etl_state_run(client, source_id, now, run_id)
    else:
        log.warning(
            "%d error(s) during run — etl_state watermark NOT advanced; "
            "next run will refetch this window (idempotent).",
            stats.errors,
        )
    stats.run_id = run_id
    stats.log_summary()
    stats.exit_if_errors()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    sentry_dsn = os.environ.get("SENTRY_DSN")
    if sentry_dsn:
        sentry_sdk.init(
            dsn=sentry_dsn,
            traces_sample_rate=0.0,
            environment=os.environ.get("ENVIRONMENT", "production"),
        )

    parser = argparse.ArgumentParser(description="Run ETL for a source")
    parser.add_argument("--source", required=True, choices=list_source_ids())
    args = parser.parse_args()
    run(args.source)


if __name__ == "__main__":
    main()
