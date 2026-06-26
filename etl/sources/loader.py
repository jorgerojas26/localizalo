import functools
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from xml.etree.ElementTree import fromstring as xml_from_string
import time

import httpx
import yaml

log = logging.getLogger(__name__)

PAGE_LIMIT = 1000
_DEFAULT_SOURCES_FILE = Path(__file__).resolve().parent.parent.parent / "sources.yml"


def _get_sources_file() -> Path:
    """Return the sources file path, respecting SOURCES_FILE env var override."""
    return Path(os.environ.get("SOURCES_FILE", str(_DEFAULT_SOURCES_FILE)))
PFIF_NS = 'http://zesty.ca/pfif/1.5'

_URL_RE = re.compile(r'^https?://')


def _parse_pfif_person(el) -> dict:
    ns = f"{{{PFIF_NS}}}"
    def _text(tag):
        e = el.find(f"{ns}{tag}")
        if e is None:
            e = el.find(tag)
        if e is not None and e.text:
            return e.text.strip()
        return None

    record = {}
    record["external_id"] = _text("person_record_id")
    record["full_name"] = _text("full_name")
    record["given_name"] = _text("given_name")
    record["family_name"] = _text("family_name")

    age = _text("age")
    if age is not None:
        try:
            record["age"] = int(age)
        except (ValueError, TypeError):
            record["age"] = None
    else:
        record["age"] = None

    record["last_known_location"] = _text("last_known_location")
    record["description"] = _text("description")
    record["photo_url"] = _text("photo_url")
    record["status"] = _text("status")
    record["source_date"] = _text("source_date")
    record["author_name"] = _text("author_name")

    record["contacto"] = None
    record["localizado_por"] = None
    record["localizado_contacto"] = None
    record["localizado_relacion"] = None
    record["localizado_nota"] = None

    other = _text("other")
    if other:
        for part in other.split(" | "):
            if part.startswith("Contacto: "):
                record["contacto"] = part[10:]
            elif part.startswith("Localizado por: "):
                record["localizado_por"] = part[16:]
            elif part.startswith("Contacto localizador: "):
                record["localizado_contacto"] = part[22:]
            elif part.startswith("Relación: "):
                record["localizado_relacion"] = part[10:]
            elif part.startswith("Nota: "):
                record["localizado_nota"] = part[6:]

    for tag, key in (
        ("contacto", "contacto"),
        ("localizado_por", "localizado_por"),
        ("localizado_contacto", "localizado_contacto"),
        ("localizado_relacion", "localizado_relacion"),
        ("localizado_nota", "localizado_nota"),
    ):
        e = el.find(f"{ns}{tag}")
        if e is None:
            e = el.find(tag)
        if e is not None and e.text:
            record[key] = e.text.strip()

    return record


def sanitize_record(record: dict) -> dict | None:
    r = dict(record)

    if not r.get("full_name") or not isinstance(r["full_name"], str) or not r["full_name"].strip():
        return None
    if not r.get("external_id") or not isinstance(r["external_id"], str) or not r["external_id"].strip():
        return None

    sd = r.get("source_date")
    if sd is not None and isinstance(sd, int):
        r["source_date"] = datetime.fromtimestamp(sd / 1000, tz=timezone.utc).isoformat()
    if sd is not None and isinstance(sd, str):
        try:
            datetime.fromisoformat(sd)
        except (ValueError, TypeError):
            r["source_date"] = None

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
            # Age 0 is treated as valid (newborn); consider treating as unknown after data review.
            if not (0 <= age <= 150):
                r["age"] = None
            else:
                r["age"] = age
        except (ValueError, TypeError):
            r["age"] = None
    return r


_REQUIRED_SOURCE_KEYS = {"id", "name", "namespace", "base_url"}


@functools.lru_cache(maxsize=1)
def load_sources() -> list[dict]:
    with open(_get_sources_file()) as f:
        sources = yaml.safe_load(f)["sources"]
    for s in sources:
        missing = _REQUIRED_SOURCE_KEYS - s.keys()
        if missing:
            raise ValueError(
                f"Source '{s.get('id', 'unknown')}' missing required keys: {missing}"
            )
    return sources


def get_source(source_id: str) -> dict:
    for s in load_sources():
        if s["id"] == source_id:
            return s
    raise ValueError(f"Unknown source: {source_id}")


def list_source_ids() -> list[str]:
    return [s["id"] for s in load_sources()]


def fetch(source_config: dict, updated_after: str):
    """Generator: yields sanitized records one at a time for memory-efficient streaming."""
    offset = 0
    total = 0
    url = source_config["base_url"].rstrip("/") + "/pfif"
    max_retries = 3

    log.info("Fetching from %s with updated_after=%s", url, updated_after)

    rate_limit_ms = source_config.get("rate_limit_ms", 100)

    with httpx.Client(timeout=30.0) as client:
        while True:
            data = None
            for attempt in range(max_retries):
                try:
                    resp = client.get(
                        url,
                        params={
                            "updated_after": updated_after,
                            "offset": offset,
                            "limit": PAGE_LIMIT,
                        },
                        headers={"accept": "application/json, application/xml"},
                    )
                    resp.raise_for_status()
                    ctype = resp.headers.get("content-type", "").lower()
                    if "xml" in ctype:
                        root = xml_from_string(resp.text)
                        ns = f"{{{PFIF_NS}}}"
                        persons = root.findall(f".//{ns}person")
                        if not persons:
                            persons = root.findall(".//person")
                        raw_records = [_parse_pfif_person(p) for p in persons]
                    else:
                        raw_records = resp.json()
                    data = [sanitize_record(r) for r in raw_records]
                    data = [r for r in data if r is not None]
                    log.info("Fetched offset %d: %d records", offset, len(data))
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        log.error("All retries exhausted for offset %d: %s. %d records yielded before failure.",
                                  offset, e, total)
                        raise RuntimeError(
                            f"Fetch failed for {source_config['id']} at offset {offset}: {e}"
                        ) from e
                    log.warning("Retry %d for offset %d: %s", attempt + 1, offset, e)
                    time.sleep(2 ** attempt)

            if not data:
                break
            for record in data:
                total += 1
                yield record
            time.sleep(rate_limit_ms / 1000.0)

            if len(data) < PAGE_LIMIT:
                break
            offset += PAGE_LIMIT

    log.info("Fetch complete: %d total records", total)
