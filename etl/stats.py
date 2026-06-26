import json
import logging
import sys
from dataclasses import dataclass, asdict

log = logging.getLogger(__name__)


@dataclass
class RunStats:
    source_id: str
    total_fetched: int = 0
    created: int = 0
    updated: int = 0
    merged: int = 0
    notes_added: int = 0
    source_records_upserted: int = 0
    errors: int = 0
    persons_exported: int = 0
    pfif_bytes: int = 0

    def log_summary(self) -> None:
        d = asdict(self)
        log.info("ETL run summary: %s", json.dumps(d))
        for key, val in d.items():
            if key == "source_id":
                continue
            level = logging.WARNING if key == "errors" and val > 0 else logging.INFO
            log.log(level, "  %s: %s", key, val)

    def exit_if_errors(self) -> None:
        if self.errors > 0:
            log.error(
                "ETL run had %d error(s). Check logs for details. Exiting with code 1.",
                self.errors,
            )
            sys.exit(1)
