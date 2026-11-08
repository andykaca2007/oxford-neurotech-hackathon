"""Alpha check: false-pass rate (null) and sensitivity (real lab alpha injected), with the gauge's own rule.

    .venv/bin/python tests/alpha_check_eval.py            # about 2 minutes

For each of his recordings and every 10 s start position, the check is replayed as the gauge runs it: 4 s windows each
second, heights from load_gauge.alpha_height, eyes-open phase = windows ending at 4 to 19 s, eyes-closed = 26 to 41 (each window starts 2 s or more after the spoken prompt) s,
the noise gate on the quietest channel's 8 to 13 Hz RMS in the open phase, the +3/+3 rule on the best channel.
  null: his data as recorded (he never closed his eyes on cue)
  injected: real lab rest EEG (eegmat, eye state not stated; resampled to 250 Hz, same channel names) added to his
            closed phase only, at full amplitude
for two channel sets: the four posterior channels (Pz O1 P3 P4) and Pz O1 only. Positions overlap (10 s step); the
non-overlapping 40 s count is printed too.
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
from scipy.signal import resample_poly, sosfiltfilt  # noqa: E402
import load_gauge as lg  # noqa: E402
import readiness_model as rm  # noqa: E402
from montage import MONTAGE  # noqa: E402

FS = 250
SETS = {"Pz O1 P3 P4 (best of 4)": ["Pz", "O1", "P3", "P4"], "Pz O1 (best of 2)": ["Pz", "O1"]}

# lab alpha donors: rest files, posterior channels, 250 Hz
rm.CH[:] = ["Pz", "O1", "P3", "P4"]
donors = []
for path in sorted(glob.glob("data/eegmat/Subject*_1.edf")):
    x, fs = rm.load_edf(path)
    donors.append(dict(zip(rm.CH, resample_poly(x[:, int(30 * fs):int(90 * fs)], 1, 2, axis=1))))


def dead(w):
    return (w.std(1) < 1e-6) | np.any(np.abs(np.abs(w) - 200000) < 1, axis=1)


def flank_cut(w, db=6.0):
    """The adversary's attack: lower power below 7 Hz and above 15 Hz by db (amplitude 10^(-db/20)), no alpha added."""
    F = np.fft.rfft(w, axis=1); f = np.fft.rfftfreq(w.shape[1], 1 / FS)
    g = np.where((f < 7) | (f > 15), 10 ** (-db / 20), 1.0)
    return np.fft.irfft(F * g, n=w.shape[1], axis=1)


def check(x, t0, chans, inject=None, attack=False):
    """Returns (new verdict, old verdict), each 'pass', 'fail', 'noisy', or None when no channel is usable."""
    slots = [MONTAGE.index(c) for c in chans]
    o, c, noise = [], [], []
    for s in range(4, 42):
        e = (t0 + s) * FS
        w = x[slots, e - 4 * FS:e].copy()
        if w.shape[1] < 4 * FS:
            return None, None
        if s >= 26:
            if inject is not None:
                for j, ch in enumerate(chans):
                    w[j] = w[j] + inject[ch][(s - 4) * FS:s * FS]
            if attack:
                w = flank_cut(w - w.mean(1, keepdims=True))
        d = dead(w)
        live = [j for j in range(len(chans)) if not d[j]]
        if not live:
            continue
        h, b = lg.alpha_height(w[live], bands=True)
        rec = {chans[j]: (h[jj], b[jj]) for jj, j in enumerate(live)}
        if 4 <= s < 20:
            o.append(rec)
            xa = w[live] - w[live].mean(1, keepdims=True)
            noise.append(float(np.min(sosfiltfilt(lg.ALPHA_BAND_SOS, xa, axis=1)[:, FS // 2:-FS // 2].std(1))))
        elif s >= 26:
            c.append(rec)
    best = lg.alpha_rule(o, c, chans)
    if best is None:
        return None, None
    if not (np.median(noise) <= lg.ALPHA_NOISE_MAX_UV):
        return "noisy", "noisy"
    old_ok = (best["closed_db"] - best["open_db"]) >= 3.0 and best["closed_db"] >= 3.0     # the previous height rule
    return ("pass" if best["ok"] else "fail"), ("pass" if old_ok else "fail")


recs = []
for path in sorted(glob.glob("recordings/paing_2026110[78]_*raw*.csv")):
    rows = []
    for line in open(path):
        if line.startswith("#"):
            continue
        try:
            rows.append([float(v) for v in line.split(",")[1:9]])
        except ValueError:
            continue
    x = np.array(rows).T
    if x.shape[1] >= 60 * FS:
        recs.append(x)

for name, chans in list(SETS.items())[:1]:
    res = {"null": [], "injected real alpha": [], "flank-only attack (no alpha)": []}
    k = 0
    for x in recs:
        for t0 in range(0, x.shape[1] // FS - 42, 10):
            for key, kw in (("null", {}), ("injected real alpha", dict(inject=donors[k % len(donors)])), ("flank-only attack (no alpha)", dict(attack=True))):
                r = check(x, t0, chans, **kw)
                if r[0] is not None:
                    res[key].append(r)
            k += 1
    print(f"{name}: share PASS among testable checks (not too noisy), new band-specific rule vs old height rule")
    for key, v in res.items():
        v = [r for r in v if r[0] != "noisy"]
        new = np.mean([r[0] == "pass" for r in v]); old = np.mean([r[1] == "pass" for r in v])
        print(f"   {key:30s} n {len(v):3d}   new {new:5.1%}   old {old:5.1%}", flush=True)
