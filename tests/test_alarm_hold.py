"""The alarm must not survive a held stretch (CRITIQUE serverpage-6).

Takes the lab replay (rest 0 to 90 s, arithmetic 90 to 150 s, rest after; the alarm fires at about t 138 on the demo
model), flattens the model channel C3 from 150 to 175 s so the gauge enters CHANNEL LOST, and checks the gauge's CSV:
the alarm was on before the hold, every held row (features nan) carries alarm 0, and no scored row after the hold
has the alarm on (rest after 150 s, and a refire would need --hold fresh scored seconds above the line anyway).
Before the fix the held rows carried alarm 1 and the page stayed red while saying "Held". Speed 40, about 30 s.

    .venv/bin/python tests/test_alarm_hold.py
"""
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
os.environ["OXN_QUIET"] = "1"
PY = os.path.join(ROOT, ".venv", "bin", "python")
HOLD_FROM, HOLD_TO = 150.0, 175.0


def main():
    raw = sorted(glob.glob(os.path.join(ROOT, "demo", "lab_eegmat_s*_raw.csv")))
    if not raw:
        print("SKIP: no lab demo file (run loadmonitor/lab_demo.py)")
        return 0
    src = raw[-1]
    cut = f"/tmp/oxn_alarm_hold_{os.getpid()}.csv"
    log = cut.replace(".csv", "_gauge.csv")
    with open(src) as f, open(cut, "w") as g:
        for line in f:
            if line.startswith("#") or line.startswith("t,"):
                g.write(line); continue
            p = line.rstrip("\n").split(",")
            t = float(p[0])
            if HOLD_FROM <= t < HOLD_TO:
                p[2] = "0.0"          # C3 (column index 2 after t) perfectly flat: the dead-channel rule marks it lost
            g.write(",".join(p) + "\n")
    cmd = [PY, os.path.join(ROOT, "loadmonitor", "load_gauge.py"), "--replay", cut, "--speed", "40", "--no-ui", "--log", log,
           "--model", os.path.join(ROOT, "models", "readiness_demo.joblib"), "--show-noisy", "--fatigue-show-s", "0",
           "--alarm", "50", "--hold", "20", "--smooth", "12"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=ROOT)
    out = r.stdout + r.stderr
    for pth in (cut,):
        try:
            os.remove(pth)
        except OSError:
            pass
    if "Traceback" in out:
        print(out[-2000:]); print("FAIL: gauge crashed"); return 1
    rows = []
    for line in open(log).read().splitlines()[1:]:
        p = line.split(",")
        try:
            rows.append((float(p[0]), float(p[1]), int(p[3]), p[6] == "nan"))   # t, load, alarm, held (features nan)
        except (ValueError, IndexError):
            pass
    before = [a for t, l, a, h in rows if t < HOLD_FROM]
    held = [(t, a) for t, l, a, h in rows if HOLD_FROM <= t < HOLD_TO + 5 and h]
    after = [(t, a) for t, l, a, h in rows if t >= HOLD_TO and not h]
    print(f"rows {len(rows)}; alarm seconds before the hold {sum(before)}; held rows {len(held)} (alarm on in {sum(a for _, a in held)}); "
          f"scored rows after {len(after)} (alarm on in {sum(a for _, a in after)}); CHANNEL LOST lines {out.count('CHANNEL LOST')}")
    ok = True
    for cond, msg in ((sum(before) >= 10, "alarm fired before the hold (at least 10 alarm seconds)"),
                      (len(held) >= 15, "the flattened C3 produced a held stretch of at least 15 rows"),
                      (held and sum(a for _, a in held) == 0, "no held row carries the alarm"),
                      (after and sum(a for _, a in after) == 0, "no scored row after the hold carries the alarm")):
        print(("PASS " if cond else "FAIL ") + msg); ok &= bool(cond)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
