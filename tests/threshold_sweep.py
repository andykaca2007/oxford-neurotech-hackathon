"""Choose the per-channel noise limit (--quality-uv) from evidence (8 Nov).

    .venv/bin/python tests/threshold_sweep.py           # about 4 minutes

1. Error curve: clean lab rest and task windows (eegmat, 12 people, live chain with ASR and baseline) get ONE model
   channel plus a real 4 s segment from Paing's recordings, binned by that segment's 4 to 30 Hz RMS before the
   reference and burst mask (notched, as the gauge measures it). The shift in p (task probability) is measured per bin.
   Reference row: the same channel plus clean lab EEG from another person (what adding ordinary brain-level signal does).
2. Availability: for each candidate limit, the share of Paing's recorded seconds (4 s windows, one per second) in
   which all 5 model channels are connected and under the limit before the mask (the binding half of the gate).
A 0.10 shift in p can be 40 load points (load = 40 x (p - rest) / rest sd, sd floor 0.10).
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
from scipy.signal import butter, iirnotch, resample_poly, sosfiltfilt, tf2sos  # noqa: E402

import model_search as ms  # noqa: E402
import readiness_model as rm  # noqa: E402
from montage import MONTAGE  # noqa: E402

FS = 250
m = joblib.load("models/readiness.joblib"); cfg, mask, CH = m["feat_cfg"], m["feature_mask"], m["channels"]
rm.CH[:] = CH
idx = [MONTAGE.index(c) for c in CH]
BP = butter(4, [4, 30], btype="band", fs=FS, output="sos"); NO = tf2sos(*iirnotch(50.0, 30.0, fs=FS))
EDGES = [0, 20, 40, 60, 80, 100, 150, 200, 300, 1e9]
LIMITS = [40, 60, 80, 100, 150, 200, 300]
clf = m["model"]


def pre_rms(w):
    return sosfiltfilt(BP, sosfiltfilt(NO, w - w.mean(-1, keepdims=True), axis=-1), axis=-1)[..., FS // 2:-FS // 2].std(-1)


# his recordings: noise bank by level, and per-second availability
bank = {c: [[] for _ in EDGES[:-1]] for c in CH}
win_rms = []
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
    for e in range(4 * FS, x.shape[1], FS):
        w = x[:, e - 4 * FS:e]
        live = ~np.any(np.abs(np.abs(w) - 200000) < 1, axis=1) & (w.std(1) > 1e-6)
        r = pre_rms(w)
        win_rms.append(np.where(live, r, np.inf))
        if (e // FS) % 4 == 0:                        # bank: non-overlapping 4 s segments
            for j, c in enumerate(CH):
                if live[j]:
                    b = int(np.searchsorted(EDGES, r[j], side="right")) - 1
                    bank[c][b].append(w[j] - w[j].mean())
win_rms = np.array(win_rms)


def p_of(w, asr, base):
    f = np.nan_to_num(ms.feats(w, FS, True, cfg, asr), nan=0, posinf=0, neginf=0)[mask]
    return clf.predict_proba((f - base)[None, :])[0, 1]


rng = np.random.default_rng(0)
labs = []
for path in sorted(glob.glob("data/eegmat/Subject*_1.edf"))[:12]:
    xr, fs = rm.load_edf(path); xt, _ = rm.load_edf(path.replace("_1.edf", "_2.edf"))
    if fs == 500:
        xr = resample_poly(xr, 1, 2, axis=1); xt = resample_poly(xt, 1, 2, axis=1)
    labs.append((xr, xt))
shift = {b: [] for b in range(len(EDGES) - 1)}; ref = []
n = 4 * FS
for k, (xr, xt) in enumerate(labs):
    base_w = [xr[:, a * FS:a * FS + n] for a in range(0, 25, 2)]
    asr = ms.ASR(cfg["asr"]); asr.fit([ms.clean_window(w, FS, cfg) for w in base_w])
    base = np.mean([np.nan_to_num(ms.feats(w, FS, True, cfg, asr), posinf=0, neginf=0)[mask] for w in base_w], axis=0)
    other = labs[(k + 1) % len(labs)][0]
    for w in [xr[:, a * FS:a * FS + n] for a in range(30, 86, 8)] + [xt[:, a * FS:a * FS + n] for a in range(0, 56, 8)]:
        p0 = p_of(w, asr, base)
        j = int(rng.integers(len(CH))); c = CH[j]
        wr = w.copy(); s0 = int(rng.integers(30, 150)) * FS
        wr[j] = wr[j] + other[j, s0:s0 + n] - other[j, s0:s0 + n].mean()
        ref.append(p_of(wr, asr, base) - p0)
        for b in shift:
            if bank[c][b]:
                wn = w.copy(); wn[j] = wn[j] + bank[c][b][int(rng.integers(len(bank[c][b])))]
                shift[b].append(p_of(wn, asr, base) - p0)

print("1. shift in p from ONE model channel carrying a real segment of his signal, by its level (before the mask)")
print(f"   reference, clean lab EEG of another person added: median |shift| {np.median(np.abs(ref)):.3f}, over 0.10 in {np.mean(np.abs(np.array(ref)) > 0.1):.0%} (n {len(ref)})")
for b, v in shift.items():
    v = np.abs(np.array(v))
    if len(v):
        hi = "" if EDGES[b + 1] > 1e8 else f"{EDGES[b + 1]:.0f}"
        print(f"   {EDGES[b]:>4.0f} to {hi:>4s} uV: median |shift| {np.median(v):.3f}, over 0.10 in {np.mean(v > 0.1):3.0%}  (n {len(v)})")
print("2. share of his recorded seconds with all 5 model channels connected and under the limit (before the mask)")
for L in LIMITS:
    print(f"   limit {L:4d} uV: {np.mean(np.all(win_rms < L, axis=1)):5.1%} of {len(win_rms)} seconds")
