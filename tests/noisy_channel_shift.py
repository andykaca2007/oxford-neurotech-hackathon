"""How much does ONE noisy model channel move the live model's output? (CRITIQUE dsp-adv1, dsp-adv2, 8 Nov)

    .venv/bin/python tests/noisy_channel_shift.py        # about 3 minutes

Clean lab rest windows (eegmat, rest file 30 to 90 s, 12 people) are scored by the live model with the live chain
(ASR fitted on the person's first 28 s, baseline features subtracted), then scored again with ONE model channel
replaced by lab EEG plus a real noise segment from Paing's recordings: a 4 s stretch where that channel is live (no
rail sample) and over 100 uV RMS in 4 to 30 Hz before the reference and burst mask. Reports the shift in p (the
model's task probability) and how the current quality gate (RMS after the full chain, under 100 uV = clean) and a
pre-mask gate (4 to 30 Hz RMS before reference and mask, under 100 uV) classify the noisy channel.
The live model was trained on these 36 people, so the clean p values are in-sample; the shifts are the point.
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


def pre_rms(w):
    return sosfiltfilt(BP, sosfiltfilt(NO, w - w.mean(1, keepdims=True), axis=1), axis=1)[:, FS // 2:-FS // 2].std(1)


# noise bank: per model channel, 4 s segments from his recordings, live, pre-mask RMS over 100 uV
bank = {c: [] for c in CH}
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
    for e in range(4 * FS, x.shape[1], 4 * FS):
        w = x[:, e - 4 * FS:e]
        r = pre_rms(w)
        for j, c in enumerate(CH):
            if not np.any(np.abs(np.abs(w[j]) - 200000) < 1) and w[j].std() > 1e-6 and r[j] > 100:
                bank[c].append(w[j] - w[j].mean())
print("noise segments per channel:", {c: len(v) for c, v in bank.items()}, flush=True)
rng = np.random.default_rng(0)
clf = m["model"]


def p_of(feats):
    return clf.predict_proba(np.nan_to_num(feats, nan=0, posinf=0, neginf=0)[None, :])[0, 1]


res = []
for path in sorted(glob.glob("data/eegmat/Subject*_1.edf"))[:12]:
    xr, fs = rm.load_edf(path)
    xr = resample_poly(xr, 1, 2, axis=1) if fs == 500 else xr
    n = 4 * FS
    base_w = [xr[:, a * FS:a * FS + n] for a in range(0, 25, 2)]
    asr = ms.ASR(cfg["asr"]); asr.fit([ms.clean_window(w, FS, cfg) for w in base_w])
    base = np.mean([np.nan_to_num(ms.feats(w, FS, True, cfg, asr), posinf=0, neginf=0)[mask] for w in base_w], axis=0)
    for a in range(30, 86, 4):
        w = xr[:, a * FS:a * FS + n]
        p0 = p_of(ms.feats(w, FS, True, cfg, asr)[mask] - base)
        j = int(rng.integers(len(CH))); c = CH[j]
        if not bank[c]:
            continue
        wn = w.copy(); wn[j] = wn[j] + bank[c][int(rng.integers(len(bank[c])))]
        p1 = p_of(ms.feats(wn, FS, True, cfg, asr)[mask] - base)
        post = asr(ms.clean_window(wn, FS, cfg)).std(1)[j]
        res.append((p1 - p0, post < 100 and post > 0.5, pre_rms(wn)[j] < 100))
d = np.array([r[0] for r in res]); post_clean = np.array([r[1] for r in res]); pre_clean = np.array([r[2] for r in res])
print(f"{len(d)} lab windows, one model channel given real noise from his recordings")
print(f"  shift in p: median {np.median(d):+.3f}, median |shift| {np.median(np.abs(d)):.3f}, |shift| over 0.10 in {np.mean(np.abs(d) > 0.1):.0%}, over 0.20 in {np.mean(np.abs(d) > 0.2):.0%}")
print(f"  current gate (after the chain) calls the noisy channel clean in {post_clean.mean():.0%}; pre-mask gate in {pre_clean.mean():.0%}")
if post_clean.any():
    print(f"  among windows the current gate calls clean: median |shift| {np.median(np.abs(d[post_clean])):.3f}, over 0.10 in {np.mean(np.abs(d[post_clean]) > 0.1):.0%}")
print("  for scale: the live mapping is load = 40 x (p - rest mean) / rest sd, rest sd floor 0.10, so a 0.10 shift is up to 40 load points")
