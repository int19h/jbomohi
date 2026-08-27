#!/usr/bin/env python3
"""Serve the read-only exchange web client on localhost."""

from __future__ import annotations

import argparse
import copy
import json
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from exchange import Registry, build_snapshot, now_utc, stamp


STATIC = Path(__file__).resolve().parent / "web"
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


class SnapshotCache:
    """Serialize reads and retain the last view across transient filesystem races."""

    def __init__(self, root: Path):
        self.registry = Registry(root)
        self._lock = threading.Lock()
        self._last: dict | None = None

    def read(self) -> dict:
        with self._lock:
            try:
                snapshot = build_snapshot(self.registry)
                snapshot["stale"] = False
                self._last = snapshot
                return snapshot
            except (OSError, UnicodeError, ValueError) as exc:
                error = f"Snapshot read was interrupted: {type(exc).__name__}: {exc}"
                if self._last is not None:
                    snapshot = copy.deepcopy(self._last)
                    snapshot["healthy"] = False
                    snapshot["stale"] = True
                    snapshot["errors"] = [error, *snapshot.get("errors", [])]
                    return snapshot
                return {
                    "protocol": self.registry.protocol,
                    "generated_at": stamp(now_utc())[1],
                    "healthy": False,
                    "stale": True,
                    "errors": [error],
                    "stats": {"threads": 0, "messages": 0, "sessions": 0,
                              "active_sessions": 0, "drafts": 0,
                              "acknowledgements": 0, "pending": 0},
                    "models": [], "sessions": [], "threads": [], "messages": [],
                }


def make_handler(cache: SnapshotCache):
    class Handler(BaseHTTPRequestHandler):
        server_version = "JbomohiExchangeReader/1"

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            path = urlsplit(self.path).path
            if path == "/api/snapshot":
                payload = json.dumps(cache.read(), ensure_ascii=False,
                                     separators=(",", ":")).encode()
                self._send(HTTPStatus.OK, "application/json; charset=utf-8", payload,
                           cache_control="no-store")
                return
            asset = ASSETS.get(path)
            if asset is None:
                self._send(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", b"Not found\n")
                return
            filename, content_type = asset
            try:
                payload = (STATIC / filename).read_bytes()
            except OSError:
                self._send(HTTPStatus.INTERNAL_SERVER_ERROR, "text/plain; charset=utf-8",
                           b"Web client asset unavailable\n")
                return
            self._send(HTTPStatus.OK, content_type, payload, cache_control="no-cache")

        def _send(self, status: HTTPStatus, content_type: str, payload: bytes,
                  *, cache_control: str = "no-store") -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", cache_control)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; img-src 'self' data:; "
                             "style-src 'self'; script-src 'self'; connect-src 'self'; "
                             "base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, fmt: str, *args) -> None:
            if getattr(self.server, "quiet", False):
                return
            super().log_message(fmt, *args)

    return Handler


def make_server(root: Path, host: str, port: int, *, quiet: bool = False) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), make_handler(SnapshotCache(root)))
    server.daemon_threads = True
    server.quiet = quiet
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2],
                        help="repository root (default: derived from this file)")
    parser.add_argument("--host", default="127.0.0.1",
                        help="listen address (default: localhost only)")
    parser.add_argument("--port", type=int, default=8765, help="listen port (default: 8765)")
    parser.add_argument("--open", action="store_true", help="open the reader in the default browser")
    a = parser.parse_args(argv)
    server = make_server(a.root.resolve(), a.host, a.port)
    host, port = server.server_address[:2]
    visible_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    url = f"http://{visible_host}:{port}/"
    print(f"Exchange reader: {url}", flush=True)
    if a.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nReader stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
