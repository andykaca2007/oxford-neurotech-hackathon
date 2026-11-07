"""Local web server for the load gauge page, the maths challenge and the debrief.

    .venv/bin/python unicorn/gauge_server.py            # http://localhost:8765
    .venv/bin/python unicorn/load_gauge.py --fake --web   # posts its state here every second

GET  /            the page (unicorn/web/index.html)
GET  /state       latest gauge state + challenge events
POST /state       the gauge pushes {t, state, load, alarm, channels, hist, ...}
POST /event       the page pushes {t, kind: "answer"|"error"|"challenge_start"|"challenge_end", ...}
POST /debrief     builds a session summary and asks Claude for a 3-line debrief
                  (model claude-opus-5-5; falls back to a plain template if no credentials)
No dependencies beyond the standard library, plus `anthropic` for the debrief.
"""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = {"t": 0, "state": "waiting for the gauge", "load": 0, "alarm": False, "baseline_done": False,
         "baseline_s": 30, "baseline_progress": 0, "hist": [], "channels": []}
EVENTS = []           # {"t", "kind", ...} from the page
LOADLOG = []          # (t, load) every second, kept for the debrief
LOCK = threading.Lock()


def summary():
    with LOCK:
        loads = list(LOADLOG)
        events = list(EVENTS)
    if not loads:
        return None
    ts = [t for t, _ in loads]
    ls = [l for _, l in loads]
    peak = max(ls)
    t_peak = ts[ls.index(peak)]
    above = sum(1 for l in ls if l >= 70)
    errors = [e for e in events if e.get("kind") == "error"]
    answers = [e for e in events if e.get("kind") in ("answer", "error")]
    def load_at(t):
        best = min(loads, key=lambda p: abs(p[0] - t))
        return best[1]
    err_loads = [load_at(e["t"]) for e in errors]
    high_err = sum(1 for l in err_loads if l >= 70)
    starts = [e["t"] for e in events if e.get("kind") == "challenge_start"]
    ends = [e["t"] for e in events if e.get("kind") == "challenge_end"]
    return dict(duration_s=round(ts[-1] - ts[0]), peak=round(peak), t_peak=round(t_peak),
                seconds_above_70=above, mean_load=round(sum(ls) / len(ls)),
                answers=len(answers), errors=len(errors), errors_during_high_load=high_err,
                challenge_start=round(starts[0]) if starts else None,
                challenge_end=round(ends[-1]) if ends else None,
                mean_load_before_challenge=round(sum(l for t, l in loads if starts and t < starts[0]) / max(1, sum(1 for t, l in loads if starts and t < starts[0]))) if starts else None,
                mean_load_during_challenge=round(sum(l for t, l in loads if starts and t >= starts[0] and (not ends or t <= ends[-1])) / max(1, sum(1 for t, l in loads if starts and t >= starts[0] and (not ends or t <= ends[-1])))) if starts else None)


def fallback_debrief(s):
    lines = [f"Load peaked at {s['peak']} at {s['t_peak'] // 60}:{s['t_peak'] % 60:02d}, and stayed above 70 for {s['seconds_above_70']} s of a {s['duration_s']} s session."]
    if s["challenge_start"] is not None:
        lines.append(f"During the challenge the mean load was {s['mean_load_during_challenge']} against {s['mean_load_before_challenge']} before it; {s['errors']} of {s['answers']} answers were wrong, {s['errors_during_high_load']} of them while load was above 70.")
    lines.append("Recommendation: a short break when the gauge holds above 70; re-check the baseline after rest.")
    return "\n".join(lines)


def claude_debrief(s):
    import anthropic
    client = anthropic.Anthropic()
    prompt = (
        "You are writing a three-line debrief for a supervisor after a mental-load monitoring session. "
        "The numbers below come from an 8-electrode EEG headset and a classifier that scores mental load 0 to 100 "
        "relative to the person's own 30-second baseline (model trained on public data; 70 percent held-out accuracy). "
        "Write exactly three short plain-English lines: 1) when load peaked and how long it stayed high, "
        "2) how the errors related to load, if a challenge ran, 3) one practical recommendation. "
        "No headings, no bullets, no medical claims, do not call anyone impaired or unfit. Session summary as JSON:\n"
        + json.dumps(s)
    )
    resp = client.messages.create(
        model="claude-opus-5-5",
        max_tokens=400,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}],
    )
    if resp.stop_reason == "refusal":
        return fallback_debrief(s)
    return "".join(b.text for b in resp.content if b.type == "text").strip()


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
                body = json.dumps(dict(STATE, events=EVENTS[-200:])).encode()
            self._send(200, body, "application/json")
        else:
            with open(os.path.join(HERE, "web", "index.html"), "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(n) or b"{}")
        if self.path.startswith("/state"):
            with LOCK:
                STATE.update(data)
                if data.get("baseline_done"):
                    LOADLOG.append((float(data.get("t", 0)), float(data.get("load", 0))))
            self._send(200, b"ok", "text/plain")
        elif self.path.startswith("/event"):
            with LOCK:
                data.setdefault("t", STATE.get("t", 0))
                EVENTS.append(data)
                if data.get("kind") == "reset":
                    EVENTS.clear()
                    LOADLOG.clear()
            self._send(200, b"ok", "text/plain")
        elif self.path.startswith("/debrief"):
            s = summary()
            if s is None:
                self._send(200, json.dumps({"text": "No session data yet.", "source": "none"}).encode(), "application/json")
                return
            try:
                text, source = claude_debrief(s), "claude-opus-5-5"
            except Exception as e:  # no credentials, offline, or an API error: never block the demo
                text, source = fallback_debrief(s), f"template ({type(e).__name__})"
            self._send(200, json.dumps({"text": text, "source": source, "summary": s}).encode(), "application/json")
        else:
            self._send(404, b"no", "text/plain")


def main(port=8765):
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"gauge page at http://localhost:{port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
