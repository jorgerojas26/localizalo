import logging
from pathlib import Path
import time

import httpx
import yaml

log = logging.getLogger(__name__)

PAGE_LIMIT = 1000
_SOURCES_FILE = Path(__file__).resolve().parent.parent.parent / "sources.yml"


def load_sources() -> list[dict]:
    with open(_SOURCES_FILE) as f:
        return yaml.safe_load(f)["sources"]


def get_source(source_id: str) -> dict:
    for s in load_sources():
        if s["id"] == source_id:
            return s
    raise ValueError(f"Unknown source: {source_id}")


def list_source_ids() -> list[str]:
    return [s["id"] for s in load_sources()]


def fetch(source_config: dict, updated_after: str) -> list[dict]:
    client = httpx.Client(timeout=30.0)
    records = []
    page = 1
    url = source_config["base_url"].rstrip("/") + "/pfif"
    max_retries = 3

    log.info("Fetching from %s with updated_after=%s", url, updated_after)

    while True:
        data = None
        for attempt in range(max_retries):
            try:
                resp = client.get(
                    url,
                    params={
                        "updated_after": updated_after,
                        "page": page,
                        "limit": PAGE_LIMIT,
                    },
                    headers={"accept": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
                log.info("Fetched page %d: %d records", page, len(data))
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    log.error("All retries exhausted for page %d: %s", page, e)
                    return records
                log.warning("Retry %d for page %d: %s", attempt + 1, page, e)
                time.sleep(2 ** attempt)

        if not data:
            break
        records.extend(data)
        time.sleep(0.1)

        if len(data) < PAGE_LIMIT:
            break
        page += 1

    log.info("Fetch complete: %d total records", len(records))
    return records
