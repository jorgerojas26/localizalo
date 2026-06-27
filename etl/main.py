import argparse
import hashlib
import os
import uuid
import logging
import sys
from datetime import datetime, timedelta, timezone

try:
    import sentry_sdk
except ImportError:
    sentry_sdk = None  # type: ignore[assignment]

from etl import db
from etl.dedup import phonetic_hash, is_match, is_full_match
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


def _compute_watermark(max_dt: datetime | None, last_run: str) -> str:
    """Compute watermark = max_dt - 1s, or last_run if max_dt is None."""
    if max_dt is None:
        return last_run
    watermark_dt = max_dt - timedelta(seconds=1)
    return watermark_dt.isoformat()


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
        "status": record.get("status", "unknown"),
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


def run(source_id: str) -> None:
    """Run ETL pipeline for a single source.

    Idempotency guarantees:
    - person_record_id is deterministic (sha256(phonetic_hash|normalized_location)[:16])
    - atomic_upsert_person uses ON CONFLICT DO UPDATE on person_record_id
    - source_records use ON CONFLICT (source_id, external_id)
    - notes use ON CONFLICT (note_record_id) where note_record_id is deterministic
    - etl_state watermark is computed from max(source_date) across fetched records,
      NOT from wall-clock time, to avoid TOCTOU data loss.
    Safe to re-run or run concurrently across different sources.
    """
    client = db.get_client()
    source_config = get_source(source_id)
    db.ensure_source_exists(client, source_id, source_config["name"], source_config["namespace"])
    stats = RunStats(source_id=source_id)

    _default_after = os.environ.get("ETL_DEFAULT_UPDATED_AFTER", "1970-01-01T00:00:00Z")
    last_run = db.get_etl_state(client, source_id) or _default_after

    now = datetime.now(timezone.utc).isoformat()
    run_id = str(uuid.uuid4())

    max_source_dt: datetime | None = None
    fetch_failed = False

    try:
        records_iter = source_fetch(source_config, updated_after=last_run)
        for record in records_iter:
            stats.total_fetched += 1

            sd = record.get("source_date")
            if sd is not None:
                try:
                    dt = datetime.fromisoformat(sd)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if max_source_dt is None or dt > max_source_dt:
                        max_source_dt = dt
                except (ValueError, TypeError):
                    pass

            try:
                loc_norm = normalize_location(record.get("last_known_location"))
                ph = phonetic_hash(record["full_name"])
                pid = person_record_id(ph, loc_norm)

                existing = db.find_person_by_id(client, pid)

                if existing:
                    same_source = db.source_record_exists(
                        client, pid, source_id, record["external_id"]
                    )
                    # NOTE: existing.get("contacto") is always None here — the persons
                    # table has no contacto column (it lives in source_records).
                    # So the contacto check in is_full_match never fires; only
                    # name and age can discriminate a pid collision.
                    if not is_full_match(
                        record["full_name"], existing["full_name"],
                        record.get("age"), existing.get("age"),
                        record.get("contacto"), existing.get("contacto"),
                    ):
                        # Bug #2: false-positive pid collision — different Person with
                        # same phonetic_hash + location. Disambiguate via suffix.
                        discriminator = hashlib.sha256(
                            f"{source_id}|{record['external_id']}".encode()
                        ).hexdigest()[:8]
                        pid = f"{pid}-{discriminator}"
                        existing = None  # fall through to else branch
                    elif same_source:
                        # Same source re-reporting: refresh via upsert (no note).
                        db.atomic_upsert_person(
                            client,
                            _build_person(record, pid, ph, loc_norm, now),
                            _build_source_record(record, pid, source_id),
                        )
                        stats.updated += 1
                        stats.source_records_upserted += 1
                    else:
                        # Cross-source match on same pid: merge secondary as historical note.
                        note_text = _build_note_text(record, source_config)
                        db.atomic_merge_note(
                            client,
                            {
                                "person_record_id": pid,
                                "note_record_id": db.compute_note_record_id(
                                    pid, source_id, record["external_id"]
                                ),
                                "note_text": note_text,
                                "author_name": record.get("author_name"),
                                "status": record.get("status"),
                                "source_date": record.get("source_date"),
                                "created_at": now,
                            },
                            _build_source_record(record, pid, source_id),
                        )
                        stats.merged += 1
                        stats.notes_added += 1
                        stats.source_records_upserted += 1

                if not existing:
                    match = db.find_person_by_phonetic_match(
                        client, record["full_name"], loc_norm
                    )
                    if match:
                        note_text = _build_note_text(record, source_config)
                        db.atomic_merge_note(
                            client,
                            {
                                "person_record_id": match["person_record_id"],
                                "note_record_id": db.compute_note_record_id(
                                    match["person_record_id"], source_id, record["external_id"]
                                ),
                                "note_text": note_text,
                                "author_name": record.get("author_name"),
                                "status": record.get("status"),
                                "source_date": record.get("source_date"),
                                "created_at": now,
                            },
                            _build_source_record(record, match["person_record_id"], source_id),
                        )
                        stats.merged += 1
                        stats.notes_added += 1
                        stats.source_records_upserted += 1
                    else:
                        db.atomic_upsert_person(
                            client,
                            _build_person(record, pid, ph, loc_norm, now),
                            _build_source_record(record, pid, source_id),
                        )
                        stats.created += 1
                        stats.source_records_upserted += 1
            except Exception:
                log.exception("Failed to process record external_id=%s", record.get("external_id"))
                if sentry_sdk:
                    sentry_sdk.capture_exception()
                stats.errors += 1

    except Exception as e:
        log.warning("Fetch aborted partway: %s. Watermark NOT advanced.", e)
        fetch_failed = True

    if fetch_failed:
        stats.errors += 1
        stats.log_summary()
        return

    log.info("Fetched %d records from source %s (since %s)", stats.total_fetched, source_id, last_run)

    watermark = _compute_watermark(max_source_dt, last_run)

    # Bug #10: per-source PFIF export/upload removed; consolidator owns publishing.
    if stats.created + stats.updated + stats.merged + stats.notes_added == 0 and stats.errors == 0:
        log.info("No changes detected. Advancing watermark.")
        db.update_etl_state_watermark(client, source_id, watermark, run_id)
        stats.run_id = run_id
        stats.log_summary()
        return

    stats.persons_exported = db.count_persons(client)
    log.info("Processed records for source %s. Persons in DB: %d", source_id, stats.persons_exported)

    if stats.errors == 0:
        db.update_etl_state_watermark(client, source_id, watermark, run_id)
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
