"""Local data-health dashboard across every fiscal year (FY2008-FY2025), read-only on data.

    .venv/bin/python -m viewer.server            # then open http://127.0.0.1:8765/

Python standard library HTTP server + DuckDB. Binds to 127.0.0.1 only, makes no outbound network calls,
and serves the page from viewer/static/ (no CDN). Every route is read-only except one: POST
/api/h/decisions, which writes config/decisions.csv (decisions about the data, never the data). That
route accepts only JSON from this page's own origin.

Needs Stage 1 (python -m src.stage1 build) and Stage 2 (python -m src.stage2 all). The FY2025-only
Layer B viewer engine (viewer/data.py) is kept but no longer served.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import time
from datetime import date, datetime
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import health, rows_all
from .health import HealthDB
from .rows_all import RowsDB

HOST = "127.0.0.1"
DEFAULT_PORT = 8765
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/static/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/static/app.css": ("app.css", "text/css; charset=utf-8"),
}
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; object-src 'none'; "
                               "base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}
MAX_BODY = 64 * 1024


def to_json(obj) -> bytes:
    def default(o):
        if isinstance(o, Decimal):
            return str(o)
        if isinstance(o, (date, datetime)):
            return o.isoformat()
        raise TypeError(f"not JSON serializable: {type(o)}")
    return json.dumps(obj, default=default).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "fy-dashboard"
    health: HealthDB = None
    rows: RowsDB = None
    allowed_hosts: set[str] = set()
    allowed_origins: set[str] = set()
    quiet = False

    def log_message(self, fmt, *args):
        if not self.quiet:
            sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % args))

    def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in {**SECURITY_HEADERS, **(extra or {})}.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, status: int = 200):
        self._send(status, to_json(obj), "application/json; charset=utf-8")

    def _error(self, status: int, message: str):
        self._json({"error": message}, status)

    do_PUT = do_DELETE = do_PATCH = lambda self: self._error(405, "method not allowed")  # noqa: E731

    def do_POST(self):          # noqa: N802 - the one write: the decision log
        if self.headers.get("Host", "") not in self.allowed_hosts:
            return self._error(403, "forbidden host")
        if self.headers.get("Origin") not in self.allowed_origins:
            return self._error(403, "forbidden origin")
        if urlsplit(self.path).path != "/api/h/decisions":
            return self._error(404, "not found")
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return self._error(415, "JSON only")
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_BODY:
            return self._error(413, "body missing or too large")
        try:
            body = json.loads(self.rfile.read(n))
            return self._json(self.health.save_decision(body))
        except (json.JSONDecodeError, health.BadRequest) as e:
            return self._error(400, str(e))

    def do_GET(self):           # noqa: N802
        if self.headers.get("Host", "") not in self.allowed_hosts:
            return self._error(403, "forbidden host")
        url = urlsplit(self.path)
        p = {k: v[-1] for k, v in parse_qs(url.query, keep_blank_values=True).items()}
        H, R = self.health, self.rows
        try:
            if url.path in STATIC_FILES:
                name, ctype = STATIC_FILES[url.path]
                return self._send(200, (STATIC_DIR / name).read_bytes(), ctype)
            if url.path.startswith("/api/h/"):
                g = H.parse_global(p.get("g"))
                route = url.path[len("/api/h/"):]
                if route == "meta":
                    return self._json(H.meta())
                if route == "overview":
                    return self._json(H.overview(g))
                if route == "completeness":
                    return self._json(H.completeness(g))
                if route == "columns":
                    return self._json(H.columns(g, p.get("metric", "blank")))
                if route == "column":
                    fy = p.get("fy")
                    return self._json(H.column_detail(p.get("name", ""), int(fy) if fy and fy.isdigit() else None))
                if route == "flags":
                    return self._json(H.flags(g))
                if route == "decisions":
                    return self._json({"decisions": H.decisions()})
                if route == "glossary":
                    return self._json(H.glossary(p.get("q", ""), p.get("category", "")))
                return self._error(404, "not found")
            if url.path == "/api/meta":
                return self._json(R.meta())
            if url.path in ("/api/rows", "/api/totals", "/api/groupby", "/api/export.csv"):
                st = R.parse_state(p, H.parse_global(p.get("g")))
                if url.path == "/api/rows":
                    return self._json(R.rows(st))
                if url.path == "/api/totals":
                    return self._json(R.totals(st))
                if url.path == "/api/groupby":
                    return self._json(R.groupby(st))
                return self._export(st)
            if url.path == "/api/values":
                return self._json(R.values(p.get("column", "")))
            if url.path == "/api/row":
                return self._json(R.row_detail(p.get("y"), p.get("m"), p.get("r")))
            return self._error(404, "not found")
        except (health.BadRequest, rows_all.BadRequest) as e:
            return self._error(400, str(e))
        except Exception as e:  # noqa: BLE001 - report, don't crash the server
            return self._error(500, f"{type(e).__name__}: {e}")

    def _export(self, st):
        R = self.rows
        matching = R.totals(st)["rows"]
        exported = min(matching, rows_all.EXPORT_CAP)
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="contracts_view_{exported}_of_{matching}_rows.csv"')
        self.send_header("X-Export-Rows", str(exported))
        self.send_header("X-Export-Matching-Rows", str(matching))
        self.send_header("X-Export-Truncated", "true" if matching > rows_all.EXPORT_CAP else "false")
        self.send_header("Cache-Control", "no-store")
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        for i, row in enumerate(R.export_rows(st)):
            w.writerow(["" if v is None else v.isoformat() if isinstance(v, (date, datetime)) else str(v) for v in row])
            if i % 5000 == 0:
                self.wfile.write(buf.getvalue().encode("utf-8"))
                buf.seek(0)
                buf.truncate()
        self.wfile.write(buf.getvalue().encode("utf-8"))


def make_server(port: int = DEFAULT_PORT, quiet: bool = False) -> tuple[ThreadingHTTPServer, HealthDB, RowsDB]:
    hdb = HealthDB()
    rdb = RowsDB(hdb.flag_ids)
    server = ThreadingHTTPServer((HOST, port), Handler)
    real = server.server_address[1]
    Handler.health, Handler.rows, Handler.quiet = hdb, rdb, quiet
    Handler.allowed_hosts = {f"127.0.0.1:{real}", f"localhost:{real}"}
    Handler.allowed_origins = {f"http://127.0.0.1:{real}", f"http://localhost:{real}"}
    return server, hdb, rdb


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--quiet", action="store_true")
    a = p.parse_args(argv)
    t0 = time.time()
    server, hdb, rdb = make_server(a.port, quiet=a.quiet)
    print(f"Dashboard: {len(rdb.years)} fiscal years present ({min(rdb.years)}-{max(rdb.years)}), "
          f"pending: {', '.join('FY' + str(y) for y in hdb.pending) or 'none'}. Ready in {time.time() - t0:.1f}s.")
    print(f"Open http://{HOST}:{server.server_address[1]}/  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
