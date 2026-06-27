"""
One-shot PFIF 1.5 XML file importer.

Parses a local PFIF XML file with 60k+ person records, starts a local
mock HTTP server with pagination, registers it as a temporary source,
and feeds it through the existing ETL pipeline.

Usage:
    python -m etl.import_file /path/to/records.xml

Environment variables required:
    SUPABASE_URL, SUPABASE_SERVICE_KEY
"""

import argparse
import logging
import sys
import tempfile
import threading
import time
from http.server import HTTPServer
from pathlib import Path
from xml.etree.ElementTree import parse as xml_parse

import yaml

from etl.sources.loader import PFIF_NS, _parse_pfif_person, sanitize_record
from tests.fixtures.mock_pfif_server import _PfifHandler, records_to_pfif_xml

log = logging.getLogger(__name__)

SOURCE_ID = "pfif-file-import"


def _make_handler_class(records):
    """Create a handler class that serves PFIF records WITHOUT updated_after
    filtering. File imports are one-shot — all records are static."""
    from urllib.parse import urlparse, parse_qs

    class Handler(_PfifHandler):
        server_records = records

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path != "/pfif":
                self.send_response(404)
                self.end_headers()
                return
            params = parse_qs(parsed.query)
            offset = int(params.get("offset", [0])[0])
            limit = int(params.get("limit", [1000])[0])
            accept = self.headers.get("Accept", "application/xml")
            page = self.server_records[offset : offset + limit]
            # _parse_pfif_person maps person_record_id -> external_id.
            # records_to_pfif_xml expects the key person_record_id.
            # Remap so the round-trip preserves the id.
            remapped = []
            for r in page:
                rr = dict(r)
                if "external_id" in rr and "person_record_id" not in rr:
                    rr["person_record_id"] = rr.pop("external_id")
                remapped.append(rr)
            if "json" in accept.lower() and "xml" not in accept.lower():
                self._send_json(remapped)
            else:
                self._send_xml(records_to_pfif_xml(remapped))

    return Handler


def _find_free_port():
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _setup_temp_sources(base_url: str) -> Path:
    """Write a temporary sources.yml with the file-import source and the
    existing production sources appended."""
    import copy
    from etl.sources.loader import load_sources, _get_sources_file

    existing = load_sources()
    sources = copy.deepcopy(existing)

    sources.insert(0, {
        "id": SOURCE_ID,
        "name": "Import from PFIF file",
        "namespace": "pfif-file-import.local",
        "base_url": base_url,
        "rate_limit_ms": 0,
    })

    tf = tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False, prefix="sources_")
    yaml.safe_dump({"sources": sources}, tf)
    tf.close()
    return Path(tf.name)


def parse_pfif_file(filepath: str) -> list[dict]:
    """Parse a PFIF 1.5 XML file and return sanitized records.

    Assigns a default source_date to records that lack one so they pass
    the mock server's updated_after filter.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

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


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Import a PFIF 1.5 XML file into the ETL pipeline"
    )
    parser.add_argument("file", help="Path to the PFIF 1.5 XML file")
    args = parser.parse_args()

    # 1. Parse the XML file
    records = parse_pfif_file(args.file)
    if not records:
        log.error("No valid records found. Aborting.")
        sys.exit(1)

    # 2. Start local mock HTTP server
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    handler = _make_handler_class(records)
    httpd = HTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)
    log.info("Mock server running at %s", base_url)

    # 3. Set up temporary sources.yml (must happen BEFORE importing etl.main)
    sources_path = _setup_temp_sources(base_url)
    import os
    os.environ["SOURCES_FILE"] = str(sources_path)

    # Clear the lru_cache so load_sources() reads our temp file
    from etl.sources.loader import load_sources
    load_sources.cache_clear()

    # Lazy import — etl.main evaluates list_source_ids() at import time
    from etl.main import run as etl_run

    try:
        # 4. Run the ETL pipeline
        log.info("Starting ETL import for source '%s' ...", SOURCE_ID)
        etl_run(SOURCE_ID)
        log.info("Import complete.")
    finally:
        # 5. Cleanup
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)
        sources_path.unlink(missing_ok=True)
        if "SOURCES_FILE" in os.environ:
            del os.environ["SOURCES_FILE"]


if __name__ == "__main__":
    main()
