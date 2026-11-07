"""Reference distribution for the fatigue index: the resting (theta + alpha) / beta ratio of the 36 eegmat subjects.

    .venv/bin/python loadmonitor/fatigue_ref.py     # writes loadmonitor/fatigue_ref.json

Per subject: rest recording, 0 to 60 s, 4 s windows, per channel log10((theta + alpha) / beta) from a Welch PSD
(same bands and same channel set as the live gauge), median over channels, mean over windows. The live gauge
places the wearer's baseline ratio in this distribution (percentile) as the fatigue starting point, then drifts.
"""
import glob
import json
import os
import re
import sys

import numpy as np
from scipy.signal import welch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import readiness_model  # noqa: E402

CH = ["Fz", "C3", "Cz", "C4", "Pz", "P3", "P4", "O1"]


def ratio(x, fs):
    f, p = welch(x - x.mean(1, keepdims=True), fs=fs, nperseg=int(fs * 2), axis=1)
    th = p[:, (f >= 4) & (f < 8)].mean(1); al = p[:, (f >= 8) & (f < 13)].mean(1); be = p[:, (f >= 13) & (f < 30)].mean(1)
    return float(np.median(np.log10((th + al) / (be + 1e-12) + 1e-12)))


def main():
    readiness_model.CH[:] = CH
    vals = {}
    for path in sorted(glob.glob("data/eegmat/Subject*_1.edf")):
        sid = re.search(r"Subject(\d+)_1", path).group(1)
        x, fs = readiness_model.load_edf(path)
        n = int(4 * fs)
        r = [ratio(x[:, i:i + n], fs) for i in range(0, min(int(60 * fs), x.shape[1]) - n + 1, n // 2)]
        vals[sid] = float(np.mean(r))
    arr = np.array(list(vals.values()))
    out = dict(channels=CH, bands=dict(theta=[4, 8], alpha=[8, 13], beta=[13, 30]), n=len(arr),
               values=sorted(float(v) for v in arr), mean=float(arr.mean()), sd=float(arr.std()))
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fatigue_ref.json"), "w") as f:
        json.dump(out, f, indent=1)
    print(f"{len(arr)} subjects: rest ratio log10 mean {arr.mean():.3f} sd {arr.std():.3f}, "
          f"min {arr.min():.3f} max {arr.max():.3f}; wrote loadmonitor/fatigue_ref.json")


if __name__ == "__main__":
    main()
