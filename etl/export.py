"""Consolidator module: cross-source reconciliation and authoritative PFIF export.

Called once after all per-source ingest jobs complete.
"""

import argparse
import logging
import os
import sys
import uuid

try:
    import sentry_sdk
except ImportError:
    sentry_sdk = None

from etl import db
from etl.export_pfif import export_pfif

log = logging.getLogger(__name__)


def reconcile(client) -> int:
    """Run reconcile_duplicate_persons RPC repeatedly until no more pairs.

    Returns total number of merge pairs processed.
    """
    total = 0
    while True:
        result = client.rpc("localize.reconcile_duplicate_persons", {"_limit": 5000}).execute()
        pairs = result.data or []
        if not pairs:
            break
        total += len(pairs)
        log.info("Reconciled %d duplicate pair(s) this batch", len(pairs))
    log.info("Reconciliation complete: %d total pair(s) merged", total)
    return total


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    sentry_dsn = os.environ.get("SENTRY_DSN")
    if sentry_dsn and sentry_sdk:
        sentry_sdk.init(
            dsn=sentry_dsn,
            traces_sample_rate=0.0,
            environment=os.environ.get("ENVIRONMENT", "production"),
        )

    parser = argparse.ArgumentParser(description="Consolidate and export PFIF")
    parser.parse_args()

    try:
        client = db.get_client()

        reconcile(client)

        pfif_xml = export_pfif(
            db.get_all_persons_paged(client),
            db.get_all_notes_paged(client),
        )

        run_id = str(uuid.uuid4())
        db.upload_pfif(client, pfif_xml, run_id)

        person_count = db.count_persons(client)
        note_count = db.count_notes(client)
        log.info(
            "Consolidator PFIF uploaded: run_id=%s, persons=%d, notes=%d, size=%d bytes",
            run_id, person_count, note_count, len(pfif_xml),
        )
    except Exception:
        log.exception("Consolidator run failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
