import logging
import re
from pathlib import Path
import time

import httpx
import yaml

log = logging.getLogger(__name__)

PAGE_LIMIT = 1000
_SOURCES_FILE = Path(__file__).resolve().parent.parent.parent / "sources.yml"

_URL_RE = re.compile(r'^https?://')


def sanitize_record(record: dict) -> dict:
    r = dict(record)
    if r.get("photo_url") and not _URL_RE.match(str(r["photo_url"])):
        r["photo_url"] = None
    for field in ("full_name", "given_name", "family_name", "description",
                  "contacto", "localizado_por", "localizado_contacto",
                  "localizado_relacion", "localizado_nota"):
        if r.get(field) and isinstance(r[field], str):
            r[field] = r[field].strip()[:5000]
    if r.get("age") is not None:
        try:
            age = int(r["age"])
            if not (0 <= age <= 150):
                r["age"] = None
            else:
                r["age"] = age
        except (ValueError, TypeError):
            r["age"] = None
    return r


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

    rate_limit_ms = source_config.get("rate_limit_ms", 100)

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
                data = [sanitize_record(r) for r in resp.json()]
                log.info("Fetched page %d: %d records", page, len(data))
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    log.error("All retries exhausted for page %d: %s. %d records fetched before failure.",
                              page, e, len(records))
                    raise RuntimeError(
                        f"Fetch failed for {source_config['id']} at page {page}: {e}"
                    ) from e
                log.warning("Retry %d for page %d: %s", attempt + 1, page, e)
                time.sleep(2 ** attempt)

        if not data:
            break
        records.extend(data)
        time.sleep(rate_limit_ms / 1000.0)

        if len(data) < PAGE_LIMIT:
            break
        page += 1

    log.info("Fetch complete: %d total records", len(records))
    return records
