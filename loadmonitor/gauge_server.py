"""Local web server for the load gauge page, the maths challenge and the debrief.

    .venv/bin/python loadmonitor/gauge_server.py            # http://localhost:8765
    .venv/bin/python loadmonitor/load_gauge.py --fake --web   # posts its state here every second

GET  /            the page (loadmonitor/web/index.html)
GET  /state       latest gauge state + challenge events
POST /state       the gauge pushes {t, state, load, alarm, channels, hist, ...}
POST /event       the page pushes {t, kind: "answer"|"error"|"challenge_start"|"challenge_end", ...}
POST /debrief     builds a session summary and asks Claude for a 3-line debrief
                  (debrief claude-opus-5-5, live coach claude-sonnet-5-5; falls back to a plain template if no credentials)
No dependencies beyond the standard library, plus `anthropic` for the debrief.
"""
import json
import time
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = {"t": 0, "state": "waiting for the gauge", "load": 0, "alarm": False, "baseline_done": False,
         "baseline_s": 30, "baseline_progress": 0, "hist": [], "channels": [], "condition": "none"}
EVENTS = []           # {"t", "kind", ...} from the page
LOADLOG = []          # (t, load) every second, kept for the debrief
LOCK = threading.Lock()


def summary():
    with LOCK:
        loads = list(LOADLOG)
        events = list(EVENTS)
        thr = float(STATE.get("alarm_at") or 70)
        ac = (STATE.get("alpha_check") or {}).get("result")
        cal = (STATE.get("calibration") or {}).get("result")
        personal = bool(STATE.get("personal"))
    if not loads:
        return None
    ts = [r[0] for r in loads]
    ls = [r[1] for r in loads]
    cleans = [r[2] for r in loads]
    fats = [r[3] for r in loads]
    conds = [r[4] for r in loads]
    peak = max(ls)
    t_peak = ts[ls.index(peak)]
    above = sum(1 for l in ls if l >= thr)
    errors = [e for e in events if e.get("kind") == "error"]
    answers = [e for e in events if e.get("kind") in ("answer", "error")]
    def load_at(t):
        best = min(loads, key=lambda p: abs(p[0] - t))
        return best[1]
    per_cond = {}
    for c in sorted(set(conds)):
        sel = [l for l, cc in zip(ls, conds) if cc == c]
        per_cond[c] = dict(seconds=len(sel), mean_load=round(sum(sel) / len(sel)))
    last = [(t, l, c) for t, l, c in zip(ts, ls, cleans) if t >= ts[-1] - 60]
    recent_err = [e for e in events if e.get("kind") == "error" and e.get("t", 0) >= ts[-1] - 60]
    recent_ans = [e for e in events if e.get("kind") in ("answer", "error") and e.get("t", 0) >= ts[-1] - 60]
    quality = dict(mean_clean_channels=round(sum(cleans) / len(cleans), 1), share_seconds_3plus_clean=round(sum(1 for c in cleans if c >= 3) / len(cleans), 2))
    err_loads = [load_at(e["t"]) for e in errors]
    high_err = sum(1 for l in err_loads if l >= thr)
    starts = [e["t"] for e in events if e.get("kind") == "challenge_start"]
    ends = [e["t"] for e in events if e.get("kind") == "challenge_end"]
    # what the EEG has been shown to contain: only a passed Alpha check is evidence of brain signal; the clean count
    # is amplitude only and is high on recordings that fail the alpha check (CRITIQUE serverpage-2)
    evidence = dict(alpha_check=ac, brain_signal_shown=bool(ac and ac.get("ok")), calibration=cal, personal_model_on=personal)
    return dict(evidence=evidence, alarm_threshold=thr, replay=STATE.get("replay") or False, duration_s=round(ts[-1] - ts[0]), peak=round(peak), t_peak=round(t_peak),
                signal_quality=quality, fatigue_start=(round(fats[0]) if fats[0] == fats[0] else None), fatigue_now=(round(fats[-1]) if fats[-1] == fats[-1] else None), load_by_condition=per_cond,   # fatigue None = not shown yet or no baseline
                last_60s=dict(mean_load=round(sum(l for _, l, _ in last) / max(1, len(last))), max_load=round(max([l for _, l, _ in last] or [0])),
                              mean_clean=round(sum(c for _, _, c in last) / max(1, len(last)), 1), answers=len(recent_ans), errors=len(recent_err), condition=conds[-1]),
                seconds_above_alarm=above, mean_load=round(sum(ls) / len(ls)),
                answers=len(answers), errors=len(errors), errors_during_high_load=high_err,
                challenge_start=round(starts[0]) if starts else None,
                challenge_end=round(ends[-1]) if ends else None,
                mean_load_before_challenge=round(sum(l for t, l in zip(ts, ls) if starts and t < starts[0]) / max(1, sum(1 for t in ts if starts and t < starts[0]))) if starts else None,
                mean_load_during_challenge=round(sum(l for t, l in zip(ts, ls) if starts and t >= starts[0] and (not ends or t <= ends[-1])) / max(1, sum(1 for t in ts if starts and t >= starts[0] and (not ends or t <= ends[-1])))) if starts else None)


UNVERIFIED = "Unverified: the Alpha check has not passed, so these load numbers are not shown to come from brain signal."


def fallback_live(s):
    l = s.get("last_60s", {})
    if not s.get("evidence", {}).get("brain_signal_shown"):
        q = "EEG not yet shown to contain brain signal (run the Alpha check); trust the answers more than the EEG"
    else:
        q = "signal clean" if l.get("mean_clean", 0) >= 3 else "signal noisy, trust the answers more than the EEG"
    pace = f"{l.get('answers', 0)} answers, {l.get('errors', 0)} wrong" if l.get("answers") else "no challenge running"
    return f"Last minute: load mean {l.get('mean_load', 0)}, peak {l.get('max_load', 0)}; {pace}; {q}."


def fallback_debrief(s):
    thr = int(s.get("alarm_threshold", 70))
    lines = [] if s.get("evidence", {}).get("brain_signal_shown") else [UNVERIFIED]
    if s.get("replay"):
        lines.insert(0, f"This is a REPLAY of a recorded session ({s['replay']}), not a live person.")
    lines.append(f"Load peaked at {s['peak']} at {s['t_peak'] // 60}:{s['t_peak'] % 60:02d}, and stayed at or above {thr} for {s['seconds_above_alarm']} s of a {s['duration_s']} s session.")
    if s["challenge_start"] is not None:
        lines.append(f"During the challenge the mean load was {s['mean_load_during_challenge']} against {s['mean_load_before_challenge']} before it; {s['errors']} of {s['answers']} answers were wrong, {s['errors_during_high_load']} of them while load was at or above {thr}.")
    lines.append(f"Recommendation: a short break when the gauge holds above {thr}; re-check the baseline after rest.")
    return "\n".join(lines)


CONTEXT = (
    "The numbers come from a dry EEG headset; the model uses 5 of its 8 electrodes (Fz C3 Cz Pz O1). 'load' is a classifier score 0 to 100 of how far the person's "
    "brain activity sits above their own 30-second resting baseline (model trained on public rest-versus-arithmetic data, "
    "cross-validated AUC 0.76 on lab EEG; on lab data rest reads 0 and arithmetic a median of 31; it has not yet been shown "
    "to separate task from rest on this dry cap). If 'replay' names a file, this is a RECORDED session replayed, not a "
    "live person: say so in the first words. 'fatigue' is a published "
    "(theta+alpha)/beta ratio, 50 = the person's own start, moving only slowly; it is not a trained model. "
    "'evidence.brain_signal_shown' is true only if the eyes-closed Alpha check passed; if it is false or missing, say first "
    "that the EEG has not been shown to contain brain signal and the load numbers are unverified. "
    "'signal_quality' counts electrodes whose cleaned signal is under 100 microvolts; that is amplitude only, not proof of "
    "EEG (it is high on recordings that fail the Alpha check). With fewer than 3 clean channels the "
    "EEG numbers are unreliable and the challenge answers and errors are the better evidence. Never make medical claims, never "
    "call anyone impaired or unfit, and say plainly when the signal was too noisy to conclude anything."
)


def claude_debrief(s, mode="full"):
    """Returns (text, source); source names the model that actually wrote the text, or the template."""
    import anthropic
    client = anthropic.Anthropic()
    if mode == "live":
        # the live line gets the evidence and replay flag too, not only the last minute (else it cannot say "unverified")
        live = dict(last_60s=s.get("last_60s", {}), evidence=s.get("evidence", {}), replay=s.get("replay", False))
        prompt = (CONTEXT + " You are a live coach. In ONE short plain sentence (under 25 words), say what the last 60 seconds "
                  "show, combining load, the person's answer pace and errors, and the signal evidence. JSON:\n" + json.dumps(live))
    else:
        prompt = (CONTEXT + " Write exactly three short plain-English lines for the person and their team: 1) when load peaked, how long it "
                  "stayed high and how it differed between the marked conditions, 2) how answers and errors related to load if a challenge ran, "
                  "3) one next step for the session (for example rebaseline, fix contact, repeat the Alpha check), no health or work advice. "
                  "State the confidence from 'evidence' first, then signal_quality. No headings, no bullets. Session summary as JSON:\n"
                  + json.dumps(s))
    model = "claude-sonnet-5-5" if mode == "live" else "claude-opus-5-5"      # the once-a-minute coach line is cheap; the debrief gets Opus
    resp = client.messages.create(
        model=model,
        max_tokens=120 if mode == "live" else 400,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}],
    )
    if resp.stop_reason == "refusal":
        return (fallback_live(s) if mode == "live" else fallback_debrief(s)), "template (model refused)"
    return "".join(b.text for b in resp.content if b.type == "text").strip(), model


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
                # age of the last gauge update: the page blanks the number and shows NO DATA when it is stale
                age = (time.time() - STATE["_rx"]) if STATE.get("_rx") else None
                body = json.dumps(dict({k: v for k, v in STATE.items() if k != "_rx"}, age_s=age, events=EVENTS[-200:])).encode()
            self._send(200, body, "application/json")
        else:
            with open(os.path.join(HERE, "web", "index.html"), "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(n) or b"{}")
        if self.path.startswith("/state"):
            with LOCK:
                cond = STATE.get("condition", "none")
                data.pop("condition", None)          # the page owns the condition, not the gauge
                data.pop("rebaseline", None)
                STATE.update(data)
                STATE["_rx"] = time.time()
                if data.get("baseline_done"):
                    LOADLOG.append((float(data.get("t", 0)), float(data.get("load", 0)), int(data.get("clean", 0)), (float(data["fatigue"]) if data.get("fatigue") is not None else float("nan")), STATE.get("condition", "none")))
            self._send(200, json.dumps({"condition": cond, "rebaseline": STATE.get("rebaseline", 0), "alpha_check": STATE.get("alpha_check_n", 0), "calibrate": STATE.get("calibrate_n", 0)}).encode(), "application/json")
        elif self.path.startswith("/event"):
            with LOCK:
                data.setdefault("t", STATE.get("t", 0))
                EVENTS.append(data)
                if data.get("kind") == "condition":
                    STATE["condition"] = str(data.get("value", "none"))
                if data.get("kind") == "reset":
                    EVENTS.clear()
                    LOADLOG.clear()
                if data.get("kind") == "rebaseline":
                    STATE["rebaseline"] = STATE.get("rebaseline", 0) + 1
                if data.get("kind") == "alpha_check":
                    STATE["alpha_check_n"] = STATE.get("alpha_check_n", 0) + 1
                if data.get("kind") == "calibrate":
                    STATE["calibrate_n"] = STATE.get("calibrate_n", 0) + 1
            self._send(200, b"ok", "text/plain")
        elif self.path.startswith("/debrief"):
            s = summary()
            if s is None:
                self._send(200, json.dumps({"text": "No session data yet.", "source": "none"}).encode(), "application/json")
                return
            mode = data.get("mode", "full")
            try:
                text, source = claude_debrief(s, mode)
            except Exception as e:  # no credentials, offline, or an API error: never block the demo
                text, source = (fallback_live(s) if mode == "live" else fallback_debrief(s)), f"template ({type(e).__name__})"
            self._send(200, json.dumps({"text": text, "source": source, "summary": s}).encode(), "application/json")
        else:
            self._send(404, b"no", "text/plain")


def main(port=8765):
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"gauge page at http://localhost:{port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    import sys
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8765)
