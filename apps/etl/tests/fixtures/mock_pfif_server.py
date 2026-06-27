"""
Mock PFIF 1.5 HTTP server for ETL testing.

Each instance simulates one Source. Start on a free port, feed it records,
and it returns PFIF XML with pagination and updated_after filtering.

Usage in tests:
    server = MockPfifServer(records=CRUZ_ROJA_RECORDS)
    server.start()
    # ... run ETL against server.url ...
    server.stop()
"""

import json
import socket
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from xml.etree.ElementTree import Element, SubElement, tostring


PFIF_NS = "http://zesty.ca/pfif/1.5"


def _find_free_port() -> int:
    """Return an available port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def records_to_pfif_xml(records: list[dict]) -> str:
    """Convert a list of record dicts to PFIF 1.5 XML."""
    root = Element(f"{{{PFIF_NS}}}pfif")

    for r in records:
        person = SubElement(root, f"{{{PFIF_NS}}}person")

        for tag, key in (
            ("person_record_id", "person_record_id"),
            ("entry_date", "entry_date"),
            ("author_name", "author_name"),
            ("full_name", "full_name"),
            ("given_name", "given_name"),
            ("family_name", "family_name"),
            ("age", "age"),
            ("last_known_location", "last_known_location"),
            ("description", "description"),
            ("photo_url", "photo_url"),
            ("status", "status"),
            ("source_date", "source_date"),
            ("contacto", "contacto"),
            ("localizado_por", "localizado_por"),
            ("localizado_contacto", "localizado_contacto"),
            ("localizado_relacion", "localizado_relacion"),
            ("localizado_nota", "localizado_nota"),
        ):
            val = r.get(key)
            if val is not None:
                el = SubElement(person, f"{{{PFIF_NS}}}{tag}")
                el.text = str(val)

        other = r.get("other")
        if other:
            el = SubElement(person, f"{{{PFIF_NS}}}other")
            el.text = other

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + tostring(root, encoding="unicode")
    )


class _PfifHandler(BaseHTTPRequestHandler):
    """HTTP handler that serves PFIF XML with pagination."""

    server_records: list[dict]

    def log_message(self, format, *args):
        pass  # silence request logs

    def _send_xml(self, body: str, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Content-Length", str(len(body.encode())))
        self.end_headers()
        self.wfile.write(body.encode())

    def _send_json(self, data: list, status: int = 200):
        body = json.dumps(data, ensure_ascii=False)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body.encode())))
        self.end_headers()
        self.wfile.write(body.encode())

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(self.path)
        if parsed.path != "/pfif":
            self._send_xml("<error>Not Found</error>", 404)
            return

        params = parse_qs(parsed.query)
        updated_after = params.get("updated_after", [None])[0]
        offset = int(params.get("offset", [0])[0])
        limit = int(params.get("limit", [1000])[0])
        accept = self.headers.get("Accept", "application/xml")

        # Filter by updated_after (compare source_date ISO strings)
        records = self.server_records
        if updated_after:
            records = [
                r for r in records
                if r.get("source_date", "") > updated_after
            ]

        # Apply pagination
        page = records[offset : offset + limit]

        # Support both XML and JSON responses
        if "json" in accept.lower() and "xml" not in accept.lower():
            self._send_json(page)
        else:
            self._send_xml(records_to_pfif_xml(page))


class MockPfifServer:
    """A mock PFIF 1.5 HTTP server for testing the ETL pipeline.

    Usage:
        server = MockPfifServer(records=CRUZ_ROJA_RECORDS)
        server.start()
        print(server.url)  # http://127.0.0.1:PORT
        # ... run ETL ...
        server.stop()
    """

    def __init__(self, records: list[dict]):
        self._records = records
        self._httpd: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._port: int = 0

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._port}"

    @property
    def port(self) -> int:
        return self._port

    @property
    def base_url(self) -> str:
        return self.url

    def start(self):
        """Start the server in a background thread."""
        self._port = _find_free_port()
        handler = type("Handler", (_PfifHandler,), {"server_records": self._records})
        self._httpd = HTTPServer(("127.0.0.1", self._port), handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        # Give the server a moment to bind
        time.sleep(0.05)

    def stop(self):
        """Stop the server."""
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread:
            self._thread.join(timeout=2)
