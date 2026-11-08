"""Four more 16:9 slides (black, same style as slide_figures.py), from real data.

    .venv/bin/python loadmonitor/slide_figures_extra.py

07 system:   headset to page, every stage the live gauge runs
08 brain:    posterior alpha (Pz, O1) and frontal theta (Fz), rest vs mental arithmetic, each of the 36 lab people
09 dry cap:  for each electrode of Paing's cap, share of recorded seconds OPEN, noisy or usable (all 7 and 8 Nov recordings)
"""
import glob
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "headset"))
os.chdir(ROOT)
import warnings  # noqa: E402
warnings.filterwarnings("ignore")
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402
from scipy.signal import butter, iirnotch, resample_poly, sosfiltfilt, tf2sos, welch  # noqa: E402

import readiness_model as rm  # noqa: E402
from montage import MONTAGE  # noqa: E402
import slide_style as st  # noqa: E402

FS = 250

# ---- 07 system diagram ----
fig = st.slide("How it works", "Every stage runs once a second on the last 4 seconds of EEG")
a = fig.add_axes([0.03, 0.08, 0.94, 0.74]); a.set_xlim(0, 100); a.set_ylim(0, 60); a.axis("off")
row1 = [("Unicorn\nBCI Core-8", "8 dry electrodes\n250 Hz, Bluetooth", st.DIM),
        ("Bridge", "g.Pype to LSL stream\nraw CSV saved", st.DIM),
        ("Contact check", "open / noisy / clean\nper electrode", st.YEL),
        ("Cleaning chain", "detrend, notch, reference,\nband-pass, burst mask, ASR", st.BLU)]
row2 = [("Features", "relative theta, alpha, beta,\nratios, entropy (24 to 29)", st.BLU),
        ("Model", "gradient boosting, trained on\n36 people, lab AUC 0.76", st.GRN),
        ("Personal scale", "load 0 = your own rest\n12 s smoothing, alarm at 50", st.GRN),
        ("Page", "load, why it moved,\nhead map, debrief", st.FG)]
def box(x, y, title, sub, col):
    a.add_patch(FancyBboxPatch((x, y), 20, 15, boxstyle="round,pad=0.4,rounding_size=1.2", fc="#0b0b0b", ec=col, lw=1.6))
    a.text(x + 10, y + 10.4, title, ha="center", va="center", fontsize=17, color=col, weight="bold", linespacing=1.1)
    a.text(x + 10, y + 4.2, sub, ha="center", va="center", fontsize=12, color=st.DIM, linespacing=1.3)
xs = [2, 27, 52, 77]
for x, (t_, s_, c_) in zip(xs, row1):
    box(x, 38, t_, s_, c_)
for x, (t_, s_, c_) in zip(xs[::-1], row2):          # bottom row runs right to left (a snake), so the turn is one short arrow
    box(x, 8, t_, s_, c_)
for x0, x1 in zip(xs[:-1], xs[1:]):
    a.annotate("", (x1 - 0.5, 45.5), (x0 + 20.5, 45.5), arrowprops=dict(arrowstyle="->", color=st.DIM, lw=1.5))
    a.annotate("", (x0 + 20.5, 15.5), (x1 - 0.5, 15.5), arrowprops=dict(arrowstyle="->", color=st.DIM, lw=1.5))
a.annotate("", (87, 23.6), (87, 37.4), arrowprops=dict(arrowstyle="->", color=st.DIM, lw=1.5))
a.text(41, 30.5, "electrode open: load held  ·  electrode noisy: load greyed, alarm off", ha="center", color=st.YEL, fontsize=14)
st.save(fig, "07_system.png", "loadmonitor/load_gauge.py (gauge), gauge_server.py (page server), web/index.html (page). Optional Claude debrief when an API key is set.")

# ---- 08 brain: rest vs arithmetic per person ----
rm.CH[:] = ["Fz", "Pz", "O1"]
NO = tf2sos(*iirnotch(50.0, 30.0, fs=FS))
def rel(x, lo, hi):
    f, p = welch(x - x.mean(), fs=FS, nperseg=2 * FS)
    tot = p[(f >= 4) & (f < 30)].sum()
    return 10 * np.log10(p[(f >= lo) & (f < hi)].sum() / tot)
pairs = []
for path in sorted(glob.glob("data/eegmat/Subject*_1.edf")):
    xr, fs = rm.load_edf(path); xt, _ = rm.load_edf(path.replace("_1.edf", "_2.edf"))
    if fs == 500:
        xr = resample_poly(xr, 1, 2, axis=1); xt = resample_poly(xt, 1, 2, axis=1)
    def med(x, ch, lo, hi, a0, a1):
        v = [rel(sosfiltfilt(NO, x[ch, s:s + 4 * FS]), lo, hi) for s in range(a0 * FS, min(a1 * FS, x.shape[1] - 4 * FS), 2 * FS)]
        return float(np.median(v))
    ra = np.mean([med(xr, 1, 8, 13, 30, 90), med(xr, 2, 8, 13, 30, 90)]); ta = np.mean([med(xt, 1, 8, 13, 0, 60), med(xt, 2, 8, 13, 0, 60)])
    rt = med(xr, 0, 4, 8, 30, 90); tt = med(xt, 0, 4, 8, 0, 60)
    pairs.append((ra, ta, rt, tt))
P = np.array(pairs)
fig = st.slide("What the brain does during mental arithmetic", f"Each line: one of {len(P)} lab people, rest vs silent subtraction (share of 4 to 30 Hz power)")
for k, (i0, i1, nm, col) in enumerate(((0, 1, "posterior alpha (Pz, O1)", st.GRN), (2, 3, "frontal theta (Fz)", st.YEL))):
    a = fig.add_axes([0.08 + k * 0.47, 0.13, 0.38, 0.64])
    d = P[:, i1] - P[:, i0]
    for r in P:
        up = r[i1] > r[i0]
        a.plot([0, 1], [r[i0], r[i1]], color=col if (up if i0 == 2 else not up) else st.DIM, lw=1.1, alpha=0.8)
    a.plot([0, 1], [np.median(P[:, i0]), np.median(P[:, i1])], color=st.FG, lw=4)
    a.set_xticks([0, 1]); a.set_xticklabels(["rest", "arithmetic"], fontsize=15); a.set_xlim(-0.2, 1.2)
    a.set_ylabel("relative power (dB)"); a.set_title(nm, color=col, fontsize=19, loc="left", pad=12)
    n_dir = int(np.sum(d < 0)) if i0 == 0 else int(np.sum(d > 0))
    a.text(0.5, 0.02, f"{'down' if i0 == 0 else 'up'} in {n_dir} of {len(P)} people · median change {np.median(d):+.1f} dB",
           transform=a.transAxes, ha="center", color=st.FG, fontsize=14)
st.save(fig, "08_brain_markers.png", "PhysioNet eegmat (gel cap): rest file 30 to 90 s vs task file 0 to 60 s, 4 s windows, median per person. Coloured lines move in the expected direction. Thick line: median.")

# ---- 09 dry cap reality ----
BB = butter(4, [4, 30], btype="band", fs=FS, output="sos")
cnt = {c: np.zeros(3) for c in MONTAGE}
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
    for e in range(4 * FS, x.shape[1], 4 * FS):
        w = x[:, e - 4 * FS:e]
        for i, c in enumerate(MONTAGE):
            if np.any(np.abs(np.abs(w[i]) - 200000) < 1) or w[i].std() < 1e-6:
                cnt[c][0] += 1
            else:
                r = sosfiltfilt(BB, sosfiltfilt(NO, w[i] - w[i].mean()))[FS // 2:-FS // 2].std()
                cnt[c][1 if r >= 100 else 2] += 1
fig = st.slide("The hard part: dry electrodes on hair", "Paing's cap, all recordings of 7 and 8 Nov: share of 4 s windows per electrode")
a = fig.add_axes([0.08, 0.15, 0.86, 0.62])
names = MONTAGE; tot = np.array([cnt[c].sum() for c in names])
o, n_, u = (np.array([cnt[c][k] for c in names]) / tot * 100 for k in range(3))
a.bar(names, u, color=st.GRN, label="usable (under 100 µV, 4 to 30 Hz)")
a.bar(names, n_, bottom=u, color=st.YEL, label="connected but noisy")
a.bar(names, o, bottom=u + n_, color=st.ORA, label="not connected (open input)")
for i, c in enumerate(names):
    a.text(i, u[i] + 1.5, f"{u[i]:.0f}%", ha="center", color=st.BG if u[i] > 8 else st.FG, fontsize=14, weight="bold") if u[i] > 3 else None
a.set_ylabel("share of windows (%)"); a.set_ylim(0, 100); a.tick_params(axis="x", labelsize=17, colors=st.FG)
a.grid(False); a.set_axisbelow(True)
a.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.12), ncol=3, fontsize=14)
st.save(fig, "09_dry_cap.png", f"{int(tot[0])} windows per electrode. Not connected = the input touched the +/-200 mV rail. Noisy = over 100 µV in 4 to 30 Hz. The gauge scores normally only when all model electrodes are usable; otherwise it holds or greys the number.")
