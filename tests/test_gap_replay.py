"""A Bluetooth outage must not splice the replay (CRITIQUE ops-7).

The raw CSV the bridge writes has no rows for an outage, while the gauge's clock (LSL time) runs on, so the markers
it wrote land late by the gap and 4 s windows straddle the splice. The live gauge now writes a gap= marker when its
clock jumps, and the replay inserts that gap into its clock.

Test: the lab replay with raw seconds 100 to 120 removed (an outage inside the arithmetic phase), a markers file with
mental at 90, gap=20.0 at 120 and rest at 170 (all in gauge time, offset 0). Expected: the replay prints the gap, no
scored row exists with 100 < t < 124 (gap plus a fresh 4 s window), the condition is mental up to t 170 and rest from
t 170 on (plus the usual 1 to 2 s marker latency), which is the 150th raw second. Without the gap row the rest marker would land 20 raw seconds late.
Speed 40, about 30 s.

    .venv/bin/python tests/test_gap_replay.py
"""
import glob
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import free_port  # noqa: E402
os.environ["OXN_QUIET"] = "1"
PY = os.path.join(ROOT, ".venv", "bin", "python")
CUT_FROM, CUT_TO = 100.0, 120.0


def run(with_gap):
    src = sorted(glob.glob(os.path.join(ROOT, "demo", "lab_eegmat_s*_raw.csv")))[-1]
    tag = f"{os.getpid()}_{'gap' if with_gap else 'nogap'}"
    cut, mk, log = f"/tmp/oxn_gap_{tag}.csv", f"/tmp/oxn_gap_{tag}_markers.csv", f"/tmp/oxn_gap_{tag}_gauge.csv"
    with open(src) as f, open(cut, "w") as g:
        for line in f:
            if line.startswith("#") or line.startswith("t,"):
                g.write(line); continue
            t = float(line.split(",", 1)[0])
            if not (CUT_FROM <= t < CUT_TO):
                g.write(line)
    with open(mk, "w") as g:
        g.write("t,condition\n# raw_offset_s=0.000\n90.0,mental\n")
        if with_gap:
            g.write(f"{CUT_TO:.1f},gap={CUT_TO - CUT_FROM:.1f}\n")
        g.write("170.0,rest\n")
    # replay markers are applied through the page server's reply, so the test runs its own server on a free port
    port = free_port.claim()
    srv = subprocess.Popen([PY, os.path.join(ROOT, "loadmonitor", "gauge_server.py"), str(port)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.2)
    cmd = [PY, os.path.join(ROOT, "loadmonitor", "load_gauge.py"), "--replay", cut, "--replay-markers", mk, "--speed", "40", "--no-ui",
           "--web", "--web-port", str(port), "--log", log, "--model", os.path.join(ROOT, "models", "readiness_demo.joblib"), "--show-noisy", "--fatigue-show-s", "0",
           "--alarm", "50", "--hold", "20", "--smooth", "12"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=ROOT)
    finally:
        srv.terminate(); srv.wait(); free_port.release(port)
    out = r.stdout + r.stderr
    rows = []
    for line in open(log).read().splitlines()[1:]:
        p = line.split(",")
        try:
            rows.append((float(p[0]), p[4]))
        except (ValueError, IndexError):
            pass
    for pth in (cut, mk, log):
        try:
            os.remove(pth)
        except OSError:
            pass
    return out, rows


def main():
    if not glob.glob(os.path.join(ROOT, "demo", "lab_eegmat_s*_raw.csv")):
        print("SKIP: no lab demo file (run loadmonitor/lab_demo.py)"); return 0
    out, rows = run(True)
    if "Traceback" in out:
        print(out[-2000:]); print("FAIL: gauge crashed"); return 1
    inside = [t for t, c in rows if CUT_FROM < t < CUT_TO + 4]
    first_rest = min((t for t, c in rows if c == "rest"), default=None)
    last_mental = max((t for t, c in rows if c == "mental"), default=None)
    print(f"with gap marker: rows {len(rows)}, GAP lines {out.count('# GAP')}, rows inside the outage {len(inside)}, "
          f"last mental t {last_mental}, first rest t {first_rest}")
    out0, rows0 = run(False)
    first_rest0 = min((t for t, c in rows0 if c == "rest"), default=None)
    print(f"without it (old behaviour): rows {len(rows0)}, GAP lines {out0.count('# GAP')}, first rest t {first_rest0} "
          f"(the raw file's 150th second is replayed at t 150, so rest there is {first_rest0 - 150 if first_rest0 else 'n/a'} s late)")
    ok = True
    for cond, msg in ((out.count("# GAP") == 1, "exactly one GAP line printed"),
                      (len(inside) == 0, "no scored row inside the outage or the fresh window after it"),
                      (first_rest is not None and 170.0 <= first_rest <= 172.5, "rest begins at t 170 to 172.5 in the gap-corrected clock (raw second 150, plus the 1 to 2 s marker latency on the 1 s grid)"),
                      (last_mental is not None and first_rest is not None and last_mental < first_rest, "mental ends where rest begins"),
                      (first_rest0 is not None and first_rest0 >= 169, "without the gap marker the rest marker lands about 20 s late (the bug)")):
        print(("PASS " if cond else "FAIL ") + msg); ok &= bool(cond)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
