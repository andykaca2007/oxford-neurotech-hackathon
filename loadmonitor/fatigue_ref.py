"""Reference distribution for the fatigue index: the resting (theta + alpha) / beta ratio of the 36 eegmat subjects.

    .venv/bin/python loadmonitor/fatigue_ref.py     # writes loadmonitor/fatigue_ref.json

Per subject: rest recording, 0 to 60 s, 4 s windows through the live cleaning chain (clean_window + ASR), per channel
log10((theta + alpha) / beta) from Hilbert band envelopes (median over time), median over the 8 channels listed in CH,
mean over windows. The live gauge computes the same ratio over its 5 model channels only, so the two are not on the
same channel set; the gauge prints the wearer's percentile in this distribution for information and does not use it
(the fatigue start is a fixed 50 and the drift is scored against the wearer's own baseline spread; CRITIQUE fatigue-2,
fatigue-7).
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


def ratio(x, fs, cfg=None, asr=None):
    """log10((theta + alpha) / beta) from Hilbert band envelopes (median over time), median over channels,
    on the same cleaned window as the live gauge (model_search.clean_window + ASR) when cfg is given."""
    from scipy.signal import butter, sosfiltfilt, hilbert
    if cfg:
        from model_search import clean_window
        x = clean_window(x, fs, cfg)
        if asr is not None:
            x = asr(x)
    x = x - x.mean(1, keepdims=True)
    env = []
    for lo, hi in ((4, 8), (8, 13), (13, 30)):
        xb = sosfiltfilt(butter(4, [lo, hi], btype="band", fs=fs, output="sos"), x, axis=1)
        env.append(np.median(np.abs(hilbert(xb, axis=1))[:, int(fs) // 2:-int(fs) // 2], axis=1))
    return float(np.median(np.log10((env[0] ** 2 + env[1] ** 2) / (env[2] ** 2 + 1e-12) + 1e-12)))


def main():
    readiness_model.CH[:] = CH
    vals = {}
    for path in sorted(glob.glob("data/eegmat/Subject*_1.edf")):
        sid = re.search(r"Subject(\d+)_1", path).group(1)
        x, fs = readiness_model.load_edf(path)
        n = int(4 * fs)
        from model_search import ROBUST_CFG, ASR, clean_window
        cfg = ROBUST_CFG
        asr = ASR(cfg["asr"]); asr.fit([clean_window(x[:, i:i + n], fs, cfg) for i in range(0, int(28 * fs) - n + 1, n // 2)])
        r = [ratio(x[:, i:i + n], fs, cfg, asr) for i in range(0, min(int(60 * fs), x.shape[1]) - n + 1, n // 2)]
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
