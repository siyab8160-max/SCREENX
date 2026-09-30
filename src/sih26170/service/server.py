"""HTTP Server for SIH26170 Engineering Workstation.

Complies strictly with post-Phase-5 engineering integration specifications:
- Pure Python standard library implementation: Zero external web framework dependencies.
- Serves static workstation assets (index.html, app.js, styles.css) from static directory.
- Routes API requests directly through the locked ServiceRouter.
- Preserves all temporal contracts and ground-truth quarantine barriers.
"""

from __future__ import annotations

import argparse
import json
import os
import mimetypes
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import socketserver
from typing import Optional
from urllib.parse import urlparse

from sih26170.service.router import ServiceRouter

STATIC_DIR = Path(__file__).resolve().parent / "static"


class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """Multi-threaded HTTP server for concurrent asset loading."""
    daemon_threads = True


class WorkstationRequestHandler(SimpleHTTPRequestHandler):
    """Handles static assets and API requests for SIH26170 Engineering Workstation."""

    router: ServiceRouter = ServiceRouter()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path in ("/health", "/model_lineage", "/lots") or path.startswith("/lots/") or path.startswith("/components/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            return
        super().do_HEAD()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # Check if this is an API endpoint handled by ServiceRouter
        is_api = (
            path in ("/health", "/model_lineage", "/lots")
            or path.startswith("/lots/")
            or path.startswith("/components/")
        )

        if is_api:
            status_code, body = self.router.dispatch("GET", self.path)
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.end_headers()
            self.wfile.write(json.dumps(body, indent=2).encode("utf-8"))
            return

        # Serve index.html for root path
        if path == "" or path == "/index.html":
            target = STATIC_DIR / "index.html"
            if target.exists():
                self._serve_static_file(target, "text/html; charset=utf-8")
                return

        # Serve static assets from STATIC_DIR
        rel_path = parsed.path.lstrip("/")
        target_file = (STATIC_DIR / rel_path).resolve()
        if target_file.is_relative_to(STATIC_DIR) and target_file.is_file():
            mime_type, _ = mimetypes.guess_type(str(target_file))
            if not mime_type:
                mime_type = "application/octet-stream"
            if mime_type.startswith("text/") or mime_type in ("application/javascript", "application/json"):
                mime_type += "; charset=utf-8"
            self._serve_static_file(target_file, mime_type)
            return

        # Fallback 404
        self.send_response(404)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({"error": f"Resource '{self.path}' not found."}).encode("utf-8"))

    def _serve_static_file(self, file_path: Path, mime_type: str) -> None:
        content = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args) -> None:
        # Standard silent logging to avoid test pollution
        pass


def create_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    router: Optional[ServiceRouter] = None,
) -> ThreadingHTTPServer:
    """Create a configured ThreadingHTTPServer instance."""
    if router is not None:
        WorkstationRequestHandler.router = router
    return ThreadingHTTPServer((host, port), WorkstationRequestHandler)


def main() -> None:
    default_host = os.environ.get("HOST", "0.0.0.0")
    default_port = int(os.environ.get("PORT", "8000"))
    parser = argparse.ArgumentParser(description="SIH26170 Engineering Workstation HTTP Server")
    parser.add_argument("--host", default=default_host, help=f"Binding host (default: {default_host})")
    parser.add_argument("--port", type=int, default=default_port, help=f"Port (default: {default_port})")
    args = parser.parse_args()

    server = create_server(host=args.host, port=args.port)
    print(f"SIH26170 Engineering Workstation active at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down workstation server.")
        server.shutdown()


if __name__ == "__main__":
    main()
