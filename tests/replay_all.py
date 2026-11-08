"""Replay every recording through the live gauge and report crashes, NaNs and load per condition.

    .venv/bin/python tests/replay_all.py [--speed 40] [--min-s 60] [--extra "--calib-s 0"]

Runs its own page server on port 8799 (never 8765), replays each recordings/paing_2026110[78]_*raw*.csv longer
than --min-s seconds with its markers, and prints one line per recording. Exit code = number of failures
(crash, NaN or inf in the gauge log, or no rows written).
"""
import argparse
import glob
import math
import os
import shlex
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, ".venv", "bin", "python")


def n_samples(path):
    with open(path) as f:
        return sum(1 for line in f if not line.startswith("#")) - 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--speed", type=float, default=40)
    ap.add_argument("--min-s", type=float, default=60)
    # same gauge settings as run_all.sh, so the replays test what is actually launched
    ap.add_argument("--extra", default="--alarm 50 --hold 20 --smooth 12")
    a = ap.parse_args()
    os.chdir(ROOT)
    fails = 0
    srv = None
    try:
        files = sorted(glob.glob("recordings/paing_2026110[78]_*raw*.csv"))
        for path in files:
            dur = n_samples(path) / 250
            if dur < a.min_s:
                continue
            if srv:
                srv.terminate(); srv.wait()
            # a fresh page server per recording, so no condition or event carries over from the previous one
            srv = subprocess.Popen([PY, "loadmonitor/gauge_server.py", "8799"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.2)
            log = f"/tmp/replay_{os.path.basename(path)[:21]}.csv"
            if os.path.exists(log):
                os.remove(log)
            cmd = [PY, "loadmonitor/load_gauge.py", "--replay", path, "--speed", str(a.speed), "--web", "--web-port", "8799",
                   "--no-ui", "--log", log] + shlex.split(a.extra)
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            out = r.stdout + r.stderr
            crash = "Traceback" in out
            rows, bad, by, al = 0, 0, {}, {}
            if os.path.exists(log):
                for line in open(log).read().splitlines()[1:]:
                    p = line.split(",")
                    rows += 1
                    try:
                        load, fat = float(p[1]), float(p[2])
                    except ValueError:
                        bad += 1
                        continue
                    if not (math.isfinite(load) and math.isfinite(fat)):
                        bad += 1
                        continue
                    by.setdefault(p[4], []).append(load)
                    al.setdefault(p[4], []).append(int(p[3]) if p[3].isdigit() else 0)
            ok = (not crash) and rows > 0 and bad == 0
            fails += 0 if ok else 1
            conds = "  ".join(f"{k} {len(v)}s mean {sum(v) / len(v):.0f} alarm {sum(al[k])}s" for k, v in sorted(by.items()))
            reason = "" if ok else (" CRASH" if crash else "") + (" NO ROWS" if rows == 0 else "") + (f" {bad} BAD ROWS" if bad else "")
            print(f"{'ok  ' if ok else 'FAIL'} {os.path.basename(path)[:21]} {dur:5.0f} s  rows {rows:4d}  {conds}{reason}", flush=True)
            if crash:
                print("     " + out[out.index("Traceback"):].strip().splitlines()[-1])
    finally:
        if srv:
            srv.terminate()
    print(f"{fails} failed")
    sys.exit(fails)


if __name__ == "__main__":
    main()
