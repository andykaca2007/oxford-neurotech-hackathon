"""Tiny local web server for the load gauge page.

    .venv/bin/python unicorn/gauge_server.py            # http://localhost:8765
    .venv/bin/python unicorn/load_gauge.py --fake --web   # posts its state here every second

GET /            the page (unicorn/web/index.html)
GET /state       latest state as JSON
POST /state      the gauge pushes {t, state, load, alarm, baseline_done, baseline_s, hist}
No dependencies beyond the standard library.
"""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = {"t": 0, "state": "waiting for the gauge", "load": 0, "alarm": False, "baseline_done": False,
         "baseline_s": 30, "baseline_progress": 0, "hist": []}
LOCK = threading.Lock()


class H(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/state"):
            with LOCK:
                body = json.dumps(STATE).encode()
            self._send(200, body, "application/json")
        else:
            with open(os.path.join(HERE, "web", "index.html"), "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(n) or b"{}")
        with LOCK:
            STATE.update(data)
        self._send(200, b"ok", "text/plain")


def main(port=8765):
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"gauge page at http://localhost:{port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
