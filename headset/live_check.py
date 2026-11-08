"""Live electrode check while run_all.sh is running: reads the newest raw recording every 2 s.

    .venv/bin/python headset/live_check.py          # in a second Terminal tab; Ctrl-C to stop
    .venv/bin/python headset/live_check.py --4ch    # when run_all uses the 4-electrode model (no C3)

Per electrode, over the last 2 s:
  OPEN      every sample at +/-200 mV: the amplifier is not connected to that electrode (press the amplifier in)
  SATURATED within 4 mV of the 200 mV limit without touching it: pinned at the rail, not EEG; press in, wait 10 s
            (a DC offset alone is normal on this amplifier: quiet channels in his recordings sit at a median 80 mV)
  FLAT      no signal at all
  number    1 to 40 Hz noise in uV after a 50 Hz notch: under 40 good, 40 to 100 fair, over 100 too noisy
"""
import glob
import os
import sys
import time

import numpy as np
from scipy.signal import butter, iirnotch, sosfiltfilt, tf2sos

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "headset"))
from montage import MONTAGE  # noqa: E402

FS = 250
BB = butter(4, [1, 40], btype="band", fs=FS, output="sos")
NO = tf2sos(*iirnotch(50.0, 30.0, fs=FS))
MODEL = {"Fz", "C3", "Cz", "Pz", "O1"} if "--4ch" not in sys.argv else {"Fz", "Cz", "Pz", "O1"}


def tail_rows(path, n):
    with open(path, "rb") as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - n * 160))
        lines = f.read().decode(errors="ignore").splitlines()[1:]
    rows = []
    for line in lines[-n:]:
        try:
            rows.append([float(v) for v in line.split(",")[1:9]])
        except (ValueError, IndexError):
            continue
    return np.array(rows).T if rows else None


def newest():
    files = glob.glob(os.path.join(ROOT, "recordings", "*_raw*.csv"))
    return max(files, key=os.path.getmtime) if files else None


def main():
    path = None
    while True:
        p = newest()
        if p is None or time.time() - os.path.getmtime(p) > 3:
            # nothing has written a recording in the last 3 s: run_all.sh is stopped, or its bridge died
            print(time.strftime("%H:%M:%S") + "  NOT RECORDING: start ./run_all.sh in the other tab (this check follows it automatically)", flush=True)
            time.sleep(2); continue
        if p != path:
            path = p
            print(f"watching {os.path.basename(path)}  (model electrodes marked *; all of them must be under 100 for a load number)", flush=True)
        x = tail_rows(path, 2 * FS)
        if x is None or x.shape[1] < FS:
            print("waiting for data ..."); time.sleep(2); continue
        out = []
        for i, c in enumerate(MONTAGE):
            w = x[i]
            name = c + ("*" if c in MODEL else " ")
            if np.mean(np.abs(np.abs(w) - 200000) < 1) > 0.5:
                out.append(f"{name} OPEN")
            elif np.median(np.abs(w)) > 196000:
                out.append(f"{name} SATURATED")       # pinned just under the 200 mV limit
            elif w.std() < 1e-6:
                out.append(f"{name} FLAT")
            else:
                v = sosfiltfilt(BB, sosfiltfilt(NO, w - w.mean()))[FS // 4:-FS // 4].std()
                tag = "ok" if v < 40 else "fair" if v < 100 else "NOISY"
                out.append(f"{name} {v:5.0f} {tag}")
        ready = all(("OPEN" not in s and "FLAT" not in s and "NOISY" not in s and "SATURATED" not in s) for s in out if s[:3].rstrip("* ") in MODEL)
        print(time.strftime("%H:%M:%S") + "  " + " | ".join(out) + ("   <- READY" if ready else ""), flush=True)
        time.sleep(2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
