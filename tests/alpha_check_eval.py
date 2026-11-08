"""Alpha check: false-pass rate (null) and sensitivity (real lab alpha injected), with the gauge's own rule.

    .venv/bin/python tests/alpha_check_eval.py            # about 2 minutes

For each of his recordings and every 10 s start position, the check is replayed as the gauge runs it: 4 s windows each
second, heights from load_gauge.alpha_height, eyes-open phase = windows ending at 4 to 19 s, eyes-closed = 24 to 39 s,
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


def check(x, t0, chans, inject=None):
    """x: (8, n) raw slots. Returns 'pass', 'fail', 'noisy' or None (no usable channel)."""
    slots = [MONTAGE.index(c) for c in chans]
    o, c, noise = {k: [] for k in chans}, {k: [] for k in chans}, []
    for s in range(4, 40):
        e = (t0 + s) * FS
        w = x[slots, e - 4 * FS:e].copy()
        if w.shape[1] < 4 * FS:
            return None
        if inject is not None and s >= 24:
            for j, ch in enumerate(chans):
                seg = inject[ch][(s - 4) * FS:s * FS]
                w[j] = w[j] + seg
        d = dead(w)
        live = [j for j in range(len(chans)) if not d[j]]
        if not live:
            continue
        h = lg.alpha_height(w[live])
        for jj, j in enumerate(live):
            (o if 4 <= s < 20 else c if s >= 24 else {})[chans[j]].append(h[jj]) if (4 <= s < 20 or s >= 24) else None
        if 4 <= s < 20:
            xa = w[live] - w[live].mean(1, keepdims=True)
            noise.append(float(np.min(sosfiltfilt(lg.ALPHA_BAND_SOS, xa, axis=1)[:, FS // 2:-FS // 2].std(1))))
    best = None
    for ch in chans:
        if len(o[ch]) >= 5 and len(c[ch]) >= 5:
            dlt = np.median(c[ch]) - np.median(o[ch])
            if best is None or dlt > best[0]:
                best = (dlt, np.median(c[ch]))
    if best is None:
        return None
    if not (np.median(noise) <= lg.ALPHA_NOISE_MAX_UV):
        return "noisy"
    return "pass" if best[0] >= 3.0 and best[1] >= 3.0 else "fail"


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

for name, chans in SETS.items():
    null, inj = [], []
    k = 0
    for x in recs:
        for t0 in range(0, x.shape[1] // FS - 40, 10):
            r = check(x, t0, chans)
            if r is not None:
                null.append(r)
            r2 = check(x, t0, chans, inject=donors[k % len(donors)])
            k += 1
            if r2 is not None:
                inj.append(r2)
    null, inj = np.array(null), np.array(inj)
    tested_null = null[null != "noisy"]
    tested_inj = inj[inj != "noisy"]
    print(f"{name}: positions {len(null)} (about {len(null) // 4} non-overlapping)")
    print(f"   null (no eyes closing): PASS {np.mean(null == 'pass'):.1%} of all, {np.mean(tested_null == 'pass'):.1%} of testable; too noisy {np.mean(null == 'noisy'):.0%}")
    print(f"   injected real lab alpha: PASS {np.mean(inj == 'pass'):.0%} of all, {np.mean(tested_inj == 'pass'):.0%} of testable; too noisy {np.mean(inj == 'noisy'):.0%}", flush=True)
