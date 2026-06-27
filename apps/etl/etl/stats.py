import json
import logging
import sys
from dataclasses import dataclass, asdict

log = logging.getLogger(__name__)


@dataclass
class RunStats:
    source_id: str
    run_id: str | None = None
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
        if self.errors == 0:
            return
        error_rate = self.errors / max(self.total_fetched, 1)
        if error_rate > 0.1:
            log.error(
                "ETL run had %d error(s) out of %d records (%.1f%%). Exiting with code 1.",
                self.errors, self.total_fetched, error_rate * 100,
            )
            sys.exit(1)
        else:
            log.warning(
                "ETL run had %d error(s) out of %d records (%.1f%%). Continuing.",
                self.errors, self.total_fetched, error_rate * 100,
            )
