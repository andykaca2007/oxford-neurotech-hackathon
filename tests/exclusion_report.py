"""Share of seconds each recording loses under the protocol's exclusion rules (CRITIQUE claims-adv1, 8 Nov).

    .venv/bin/python tests/exclusion_report.py

Per whole second of each raw recording (60 s or longer):
  original rule (PROTOCOL.md, written 7 Nov): any of the 8 channels on the +/-200 mV rail, or above 150 uV RMS in
    1 to 40 Hz (50 Hz notched), invalidates that second
  amended rule (8 Nov, after seeing the data): the same, but only on the 5 model channels Fz C3 Cz Pz O1
  gauge: of the rows the gauge wrote after its baseline in the last replay (tests/replay_all.py logs), the share it
    scored rather than held (a held row has NaN features: a model channel lost, or fewer than 2 clean)
"""
import glob
import os
import sys

import numpy as np
from scipy.signal import butter, iirnotch, sosfiltfilt, tf2sos

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "headset"))
os.chdir(ROOT)
from montage import MONTAGE  # noqa: E402

FS = 250
MODEL = ["Fz", "C3", "Cz", "Pz", "O1"]
BB = butter(4, [1, 40], btype="band", fs=FS, output="sos")
NO = tf2sos(*iirnotch(50.0, 30.0, fs=FS))

print(f"{'recording':24s} {'s':>5s} {'orig 8ch':>9s} {'amend 5ch':>10s} {'gauge scored':>13s}")
tot = np.zeros(3)
g_rows = g_held = 0
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
    n = x.shape[1] // FS
    if n < 60:
        continue
    x = x[:, :n * FS]
    rail = (np.abs(np.abs(x) - 200000) < 1).reshape(8, n, FS).any(2)
    xf = sosfiltfilt(BB, sosfiltfilt(NO, x - x.mean(1, keepdims=True), axis=1), axis=1)
    loud = xf.reshape(8, n, FS).std(2) > 150
    bad = rail | loud
    m5 = [MONTAGE.index(c) for c in MODEL]
    orig = bad.any(0).mean()
    amend = bad[m5].any(0).mean()
    name = os.path.basename(path)[:21]
    logs = glob.glob(f"/tmp/replay*_{name}.csv")
    scored = "not replayed"
    if logs:
        lines = open(max(logs, key=os.path.getmtime)).read().splitlines()[1:]
        scored = "0 (no baseline)"
        if lines:
            held = sum(1 for ln in lines if ln.split(",")[6:7] in (["nan"],))
            g_rows += len(lines); g_held += held
            scored = f"{100 * (1 - held / len(lines)):5.0f}% of {len(lines)}"
    tot += [n, orig * n, amend * n]
    print(f"{name:24s} {n:5d} {100 * orig:8.0f}% {100 * amend:9.0f}% {scored:>13s}")
print(f"{'all':24s} {int(tot[0]):5d} {100 * tot[1] / tot[0]:8.0f}% {100 * tot[2] / tot[0]:9.0f}% "
      f"{100 * (1 - g_held / max(g_rows, 1)):6.0f}% of {g_rows}")
print("orig and amend columns: share of seconds EXCLUDED; gauge column: share of post-baseline rows SCORED")
