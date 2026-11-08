"""How often does Calibrate switch the personal model on by chance, and how often for a real effect?

    .venv/bin/python tests/calib_null.py            # about 5 minutes

Uses loadmonitor/calibration.leave_one_pair_out, the function the gauge runs, and the live model's cleaning chain and
feature mask. Three measurements:
  1. his recordings, where he never alternated rest and task (null): NON-OVERLAPPING 160 s runs after a 30 s baseline,
     8 blocks of 20 s, first 5 s of each block skipped, windows with a dead model channel skipped (the gauge holds them)
  2. lab rest only (null): each eegmat subject's rest file cut into 6 fake blocks of 20 s from 30 s
  3. lab rest vs arithmetic (positive control): 3 pairs, rest blocks from the rest file, task blocks from the task file
     (two separate recordings of one session, so this is an optimistic sensitivity)
Prints the share at or above the bar with an exact binomial 95 percent bound, counting independent runs only.
"""
import glob
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "loadmonitor"))
sys.path.insert(0, os.path.join(ROOT, "headset"))
os.chdir(ROOT)

import warnings  # noqa: E402
warnings.filterwarnings("ignore")
import joblib  # noqa: E402
import model_search as ms  # noqa: E402
import readiness_model as rm  # noqa: E402
from calibration import binomial_upper, leave_one_pair_out  # noqa: E402
from montage import MONTAGE  # noqa: E402

BAR = 0.80
m = joblib.load("models/readiness.joblib")
cfg, mask, CH = m["feat_cfg"], m["feature_mask"], m["channels"]
rm.CH[:] = CH


def featurise(x, fs, starts_s, base_s=(0, 28)):
    """Features for 4 s windows starting at starts_s (seconds), relative to the mean of the baseline windows, with ASR
    fitted on the baseline, as the gauge does. Returns {start: vector or None if a channel is dead}."""
    n = int(4 * fs)

    def dead(w):
        return np.any((w.std(1) < 1e-6) | np.any(np.abs(np.abs(w) - 200000) < 1, axis=1))
    bw = [x[:, int(a * fs):int(a * fs) + n] for a in range(base_s[0], base_s[1] - 3)]
    bw = [w for w in bw if w.shape[1] == n and not dead(w)]
    if len(bw) < 10:
        return None
    asr = ms.ASR(cfg["asr"]); asr.fit([ms.clean_window(w, fs, cfg) for w in bw])
    base = np.mean([np.nan_to_num(ms.feats(w, fs, True, cfg, asr), posinf=0, neginf=0)[mask] for w in bw], axis=0)
    out = {}
    for a in starts_s:
        w = x[:, int(a * fs):int(a * fs) + n]
        out[a] = None if (w.shape[1] < n or dead(w)) else np.nan_to_num(ms.feats(w, fs, True, cfg, asr), posinf=0, neginf=0)[mask] - base
    return out


def blocks_from(F, t0, n_blocks, block_s=20, skip_s=5):
    return {b: [F[a] for a in range(t0 + b * block_s + skip_s, t0 + (b + 1) * block_s) if F.get(a) is not None] for b in range(n_blocks)}


def report(name, aucs):
    a = np.array([v for v in aucs if v == v])
    k = int(np.sum(a >= BAR))
    print(f"{name}: {len(a)} independent runs, median AUC {np.median(a):.2f}, at or above {BAR}: {k} "
          f"({k / len(a):.0%}), exact 95% upper bound {binomial_upper(k, len(a)):.0%}", flush=True)
    print("     share at or above other bars: " + ", ".join(f"{b}: {np.mean(a >= b):.0%}" for b in (0.75, 0.80, 0.85, 0.90, 0.95)), flush=True)


# 1. his recordings: non-overlapping 160 s runs after a 30 s baseline
idx = [MONTAGE.index(c) for c in CH]
null_his = []
for path in sorted(glob.glob("recordings/paing_2026110[78]_*raw*.csv")):
    rows = []
    for line in open(path):
        if line.startswith("#"):
            continue
        try:
            rows.append([float(v) for v in line.split(",")[1:9]])
        except ValueError:
            continue
    x = np.array(rows).T[idx]
    dur = x.shape[1] // 250
    runs = (dur - 30 - 4) // 160
    if runs < 1:
        continue
    F = featurise(x, 250, range(30, 30 + runs * 160), base_s=(0, 30))
    if F is None:
        continue
    for r in range(runs):
        null_his.append(leave_one_pair_out(blocks_from(F, 30 + r * 160, 8), 8)["auc"])
report("1. his recordings, no real alternation (null)", null_his)

# 2 and 3. lab
null_lab, pos_lab = [], []
for path in sorted(glob.glob("data/eegmat/Subject*_1.edf")):
    xr, fs = rm.load_edf(path)
    xt, _ = rm.load_edf(path.replace("_1.edf", "_2.edf"))
    if xr.shape[1] < 160 * fs or xt.shape[1] < 60 * fs:
        continue
    Fr = featurise(xr, fs, range(30, 152))
    if Fr is None:
        continue
    null_lab.append(leave_one_pair_out(blocks_from(Fr, 30, 6), 6)["auc"])
    # positive control: rest blocks k from 30 + 20k, task blocks k from 20k (task file, same baseline and ASR as rest)
    n = int(4 * fs)
    asr = ms.ASR(cfg["asr"]); asr.fit([ms.clean_window(xr[:, int(a * fs):int(a * fs) + n], fs, cfg) for a in range(0, 25)])
    base = np.mean([np.nan_to_num(ms.feats(xr[:, int(a * fs):int(a * fs) + n], fs, True, cfg, asr), posinf=0, neginf=0)[mask] for a in range(0, 25)], axis=0)
    f = lambda x, a: np.nan_to_num(ms.feats(x[:, int(a * fs):int(a * fs) + n], fs, True, cfg, asr), posinf=0, neginf=0)[mask] - base
    B = {}
    for k in range(3):
        B[2 * k] = [f(xr, 30 + 20 * k + o) for o in range(5, 17)]
        B[2 * k + 1] = [f(xt, 20 * k + o) for o in range(5, min(17, int(xt.shape[1] / fs) - 20 * k - 4))]
    pos_lab.append(leave_one_pair_out(B, 6)["auc"])
report("2. lab rest only, fake 20 s blocks (null)", null_lab)
report("3. lab rest vs arithmetic, interleaved (positive control, optimistic)", pos_lab)
