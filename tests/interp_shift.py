"""If one model electrode is bad, how much does rebuilding it from its neighbours move the live model? (8 Nov)

    .venv/bin/python tests/interp_shift.py           # about 3 minutes

Lab rest and task windows (eegmat, 12 people, all 8 layout-A electrodes, live chain with ASR and baseline from the
first 28 s). For each model electrode in turn, its signal is replaced by the mean of its layout-A neighbours (the
standard bad-channel fix), and the change in p (the model's task probability) is measured. Compare with
tests/noisy_channel_shift.py: one channel carrying his real noise moved p by a median 0.19.
"""
import glob
import os
import sys
import warnings

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "loadmonitor")); sys.path.insert(0, os.path.join(ROOT, "headset"))
os.chdir(ROOT)
warnings.filterwarnings("ignore")
import joblib  # noqa: E402
from scipy.signal import resample_poly  # noqa: E402

import model_search as ms  # noqa: E402
import readiness_model as rm  # noqa: E402
from montage import MONTAGE  # noqa: E402

FS = 250
m = joblib.load("models/readiness.joblib"); cfg, mask, CH = m["feat_cfg"], m["feature_mask"], m["channels"]
NEIGH = {"Fz": ["Cz", "C3", "C4"], "C3": ["Cz", "P3", "Fz"], "Cz": ["Fz", "C3", "C4", "Pz"],
         "Pz": ["Cz", "P3", "P4", "O1"], "O1": ["Pz", "P3"]}
clf = m["model"]


def p_of(x8, asr, base):
    f = np.nan_to_num(ms.feats(x8[[MONTAGE.index(c) for c in CH]], FS, True, cfg, asr), nan=0, posinf=0, neginf=0)[mask]
    return clf.predict_proba((f - base)[None, :])[0, 1]


res = {c: [] for c in CH}
for path in sorted(glob.glob("data/eegmat/Subject*_1.edf"))[:12]:
    rm.CH[:] = MONTAGE
    xr, fs = rm.load_edf(path); xt, _ = rm.load_edf(path.replace("_1.edf", "_2.edf"))
    rm.CH[:] = CH
    if fs == 500:
        xr = resample_poly(xr, 1, 2, axis=1); xt = resample_poly(xt, 1, 2, axis=1)
    n = 4 * FS
    sel = [MONTAGE.index(c) for c in CH]
    base_w = [xr[:, a * FS:a * FS + n] for a in range(0, 25, 2)]
    asr = ms.ASR(cfg["asr"]); asr.fit([ms.clean_window(w[sel], FS, cfg) for w in base_w])
    base = np.mean([np.nan_to_num(ms.feats(w[sel], FS, True, cfg, asr), posinf=0, neginf=0)[mask] for w in base_w], axis=0)
    wins = [xr[:, a * FS:a * FS + n] for a in range(30, 86, 8)] + [xt[:, a * FS:a * FS + n] for a in range(0, 56, 8)]
    for w in wins:
        p0 = p_of(w, asr, base)
        for c in CH:
            wi = w.copy()
            wi[MONTAGE.index(c)] = w[[MONTAGE.index(k) for k in NEIGH[c]]].mean(0)
            res[c].append(p_of(wi, asr, base) - p0)
allv = np.concatenate([np.array(v) for v in res.values()])
print(f"{len(allv)} window x electrode cases: rebuilt from neighbours, shift in p median |{np.median(np.abs(allv)):.3f}|, "
      f"over 0.10 in {np.mean(np.abs(allv) > 0.1):.0%}, over 0.20 in {np.mean(np.abs(allv) > 0.2):.0%}")
for c, v in res.items():
    v = np.array(v)
    print(f"  {c:3s} (from {'+'.join(NEIGH[c])}): median |shift| {np.median(np.abs(v)):.3f}, mean shift {np.mean(v):+.3f}, over 0.10 in {np.mean(np.abs(v) > 0.1):.0%}")
