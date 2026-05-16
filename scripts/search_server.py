#!/usr/bin/env python3
"""Small HTTP server for local/static-page topic search.

POST /api/search-topic with {"keyword": "..."} to run a real server-side web
search and receive a topic-tab JSON object. GET requests serve files from docs/
so local testing matches GitHub Pages closely.
"""
from __future__ import annotations

import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from search_topic import SearchError, search_topic

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
DEFAULT_PORT = 8765


class SearchHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DOCS_DIR), **kwargs)

    def end_headers(self) -> None:
        origin = os.environ.get("ANNE_ALLOWED_ORIGIN", "*")
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_POST(self) -> None:
        if self.path != "/api/search-topic":
            self.send_error(404, "Not found")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json({"error": "invalid content length"}, status=400)
            return

        try:
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body or "{}")
            keyword = str(payload.get("keyword", "")).strip()
            max_results = int(payload.get("max_results", 8))
            if not keyword:
                self.send_json({"error": "keyword is required"}, status=400)
                return
            self.send_json(search_topic(keyword, max_results=max(1, min(max_results, 12))))
        except json.JSONDecodeError:
            self.send_json({"error": "invalid JSON"}, status=400)
        except (SearchError, OSError) as exc:
            self.send_json({"error": str(exc)}, status=502)
        except Exception as exc:  # Keep the browser response usable.
            self.send_json({"error": f"unexpected server error: {exc}"}, status=500)

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    port = int(os.environ.get("PORT", DEFAULT_PORT))
    server = ThreadingHTTPServer(("0.0.0.0", port), SearchHandler)
    print(f"[search-server] serving {DOCS_DIR} and /api/search-topic on :{port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
