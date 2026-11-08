"""Replay every recording through the live gauge and report crashes, NaNs and load per condition.

    .venv/bin/python tests/replay_all.py [--speed 40] [--min-s 60] [--extra "--calib-s 0"]

Runs its own page server on a free port from 8799 upward (tests/free_port.py; never 8765), replays each recordings/paing_2026110[78]_*raw*.csv longer
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import free_port  # noqa: E402
os.environ["OXN_QUIET"] = "1"      # the gauge never speaks from a test

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, ".venv", "bin", "python")


def n_samples(path):
    with open(path) as f:
        return sum(1 for line in f if not line.startswith("#")) - 1


def check_log(log):
    """Per-session checks on a gauge CSV: crash-free finite rows, plus broken-but-finite scored rows (CRITIQUE
    fatigue-adv2): all features 0, the same feature vector for 60 s, fatigue pinned at 0 or 100 for 30 s."""
    rows, bad, by, al = 0, 0, {}, {}
    scored, zeroed, pinned, same, longest, prev = 0, 0, 0, 0, 0, None
    if os.path.exists(log):
        for line in open(log).read().splitlines()[1:]:
            p = line.split(",")
            rows += 1
            try:
                load, fat = float(p[1]), float(p[2])
            except ValueError:
                bad += 1
                continue
            if not math.isfinite(load):          # fatigue may be nan by design (no fatigue baseline)
                bad += 1
                continue
            by.setdefault(p[4], []).append(load)
            al.setdefault(p[4], []).append(int(p[3]) if p[3].isdigit() else 0)
            # broken-but-finite checks on SCORED rows (held rows carry NaN features), CRITIQUE fatigue-adv2:
            # all features exactly 0 (the chain zeroed every channel), the same feature vector for 60 s
            # (frozen input), fatigue pinned at 0 or 100
            if p[6] != "nan":
                scored += 1
                fv = p[6:]
                zeroed += all(float(v) == 0.0 for v in fv)
                same = same + 1 if fv == prev else 0
                longest = max(longest, same)
                prev = fv
                pinned += fat in (0.0, 100.0)
    broken = (zeroed > 0) + (longest >= 60) + (pinned >= 30)
    bad += broken
    return dict(rows=rows, bad=bad, by=by, al=al, scored=scored, zeroed=zeroed, pinned=pinned, longest=longest, broken=broken)


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
    PORT = free_port.claim()
    print(f"# test port {PORT}", flush=True)
    try:
        files = sorted(glob.glob("recordings/paing_2026110[78]_*raw*.csv"))
        for path in files:
            dur = n_samples(path) / 250
            if dur < a.min_s:
                continue
            if srv:
                srv.terminate(); srv.wait()
            # a fresh page server per recording, so no condition or event carries over from the previous one
            srv = subprocess.Popen([PY, "loadmonitor/gauge_server.py", str(PORT)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.2)
            log = f"/tmp/replay{PORT}_{os.path.basename(path)[:21]}.csv"
            if os.path.exists(log):
                os.remove(log)
            cmd = [PY, "loadmonitor/load_gauge.py", "--replay", path, "--speed", str(a.speed), "--web", "--web-port", str(PORT),
                   "--no-ui", "--log", log] + shlex.split(a.extra)
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            out = r.stdout + r.stderr
            crash = "Traceback" in out
            c = check_log(log)
            rows, bad, by, al, scored, zeroed, pinned, longest, broken = (c[k] for k in ("rows", "bad", "by", "al", "scored", "zeroed", "pinned", "longest", "broken"))
            # a recording whose model channels are never all connected for 30 s gets no baseline and no scored rows:
            # that is the correct behaviour (holding), not a failure, as long as the gauge said so
            no_baseline = rows == 0 and not crash and "BASELINE paused" in out
            ok = (not crash) and (rows > 0 or no_baseline) and bad == 0
            fails += 0 if ok else 1
            conds = "  ".join(f"{k} {len(v)}s mean {sum(v) / len(v):.0f} alarm {sum(al[k])}s" for k, v in sorted(by.items()))
            reason = (" (no clean 30 s baseline: held, never scored)" if no_baseline else
                      " (held throughout: no second had all model channels clean)" if ok and scored == 0 else "" if ok else
                      (" CRASH" if crash else "") + (" NO ROWS" if rows == 0 else "") + (f" {bad - broken} BAD ROWS" if bad - broken else "")
                      + (f" {zeroed} ZEROED ROWS" if zeroed else "") + (f" FROZEN {longest + 1} s" if longest >= 60 else "")
                      + (f" FATIGUE PINNED {pinned} s" if pinned >= 30 else ""))
            print(f"{'ok  ' if ok else 'FAIL'} {os.path.basename(path)[:21]} {dur:5.0f} s  rows {rows:4d}  scored {scored:4d}  {conds}{reason}", flush=True)
            if crash:
                print("     " + out[out.index("Traceback"):].strip().splitlines()[-1])
    finally:
        if srv:
            srv.terminate()
        free_port.release(PORT)
    print(f"{fails} failed")
    sys.exit(fails)


if __name__ == "__main__":
    main()
