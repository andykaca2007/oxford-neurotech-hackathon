"""Rebaseline through the shared reset (CRITIQUE gauge-8): the page's Rebaseline and the pygame B key both set
cond["redo"], and the one reset block must leave a clean second baseline.

Runs the lab replay (rest 0 to 90 s, arithmetic 90 to 150 s, rest after) against its own page server on a free port,
posts a page-style rebaseline event once the first baseline has been scoring for a while (still inside the rest
phase), then checks on the gauge's CSV that the second baseline scores rest near 0 and arithmetic well above it,
exactly as the first did. Speed 40, about 30 s wall time.

    .venv/bin/python tests/test_rebaseline.py
"""
import glob
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import free_port  # noqa: E402
os.environ["OXN_QUIET"] = "1"      # the gauge never speaks from a test

PY = os.path.join(ROOT, ".venv", "bin", "python")
SPEED = 40
REBASE_AT = 55.0            # replay seconds: inside the first rest phase, 25 s before arithmetic starts


def rows(log):
    out = []
    if not os.path.exists(log):
        return out
    for line in open(log).read().splitlines()[1:]:
        p = line.split(",")
        try:
            out.append((float(p[0]), float(p[1]), p[4]))
        except (ValueError, IndexError):
            pass
    return out


def main():
    raw = sorted(glob.glob(os.path.join(ROOT, "demo", "lab_eegmat_s*_raw.csv")))
    if not raw:
        print("SKIP: no lab demo file (run loadmonitor/lab_demo.py)")
        return 0
    port = free_port.claim()
    log = f"/tmp/rebase{port}.csv"
    if os.path.exists(log):
        os.remove(log)
    srv = subprocess.Popen([PY, os.path.join(ROOT, "loadmonitor", "gauge_server.py"), str(port)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(1.2)
        cmd = [PY, os.path.join(ROOT, "loadmonitor", "load_gauge.py"), "--replay", raw[-1], "--speed", str(SPEED),
               "--web", "--web-port", str(port), "--no-ui", "--log", log, "--model",
               os.path.join(ROOT, "models", "readiness_demo.joblib"), "--show-noisy", "--fatigue-show-s", "0"]
        posted = {"t": None}

        def poster():
            # the page posts {"kind": "rebaseline"}; the gauge sees the server's counter change and sets cond["redo"]
            while posted["t"] is None:
                r = rows(log)
                if r and r[-1][0] >= REBASE_AT:
                    req = urllib.request.Request(f"http://127.0.0.1:{port}/event", data=json.dumps({"kind": "rebaseline"}).encode(),
                                                 headers={"Content-Type": "application/json"})
                    urllib.request.urlopen(req, timeout=2).read()
                    posted["t"] = r[-1][0]
                    return
                time.sleep(0.05)

        th = threading.Thread(target=poster, daemon=True)
        th.start()
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=ROOT)
        out = r.stdout + r.stderr
    finally:
        srv.terminate(); srv.wait()
        free_port.release(port)

    ok = True
    if "Traceback" in out:
        print(out[-2000:]); print("FAIL: gauge crashed"); return 1
    if posted["t"] is None:
        print("FAIL: the rebaseline was never posted (gauge finished first?)"); return 1
    n_req = out.count("REBASELINE requested")
    n_done = out.count("# baseline done")
    rr = rows(log)
    t_req = posted["t"]
    # after the request, no scored row until a full new baseline has passed, then rest near 0 and arithmetic well above
    after = [x for x in rr if x[0] > t_req + 1]
    first_after = after[0][0] if after else None
    rest2 = [l for t, l, c in after if t < 90]
    task2 = [l for t, l, c in after if 120 <= t < 150]
    before_rest = [l for t, l, c in rr if t < t_req]
    med = lambda v: sorted(v)[len(v) // 2] if v else float("nan")
    print(f"rebaseline posted at t {t_req:.0f}: requests seen {n_req}, baselines done {n_done}, first scored row after {first_after}")
    print(f"rest before: {len(before_rest)} rows median {med(before_rest):.1f};  rest after new baseline: {len(rest2)} rows median {med(rest2):.1f};  "
          f"arithmetic 120 to 150 s: {len(task2)} rows median {med(task2):.1f}")
    for cond, msg in ((n_req == 1, "exactly one REBASELINE request"), (n_done == 2, "two baselines completed"),
                      (first_after is not None and first_after >= t_req + 20, "no scored row for at least 20 s after the request"),
                      (rest2 and med(rest2) < 10, "second-baseline rest median under 10"),
                      (task2 and med(task2) > 30, "arithmetic median over 30 after the second baseline")):
        print(("PASS " if cond else "FAIL ") + msg); ok &= bool(cond)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
