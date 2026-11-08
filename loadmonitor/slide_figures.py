"""Four 16:9 slide figures from real data, black ground to match the page.

    .venv/bin/python loadmonitor/slide_figures.py        # writes figures/slides/01..04_*.png (1920 x 1080)

01 DSP, time:   one 4 s window of Paing's dry cap (Pz), raw vs after the live cleaning chain
02 DSP, freq:   the same window's spectrum, raw vs cleaned (50/100 Hz mains removed, 4 to 30 Hz kept)
03 ML, accuracy: held-out AUC for each of the 36 lab people (models/lab_demo_loso.json)
04 ML, demo:    the lab demo replay through the live gauge: load over time with rest / arithmetic / recovery, and the
                person's posterior alpha change (Pz, O1) vs their own baseline
"""
import glob
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "headset"))
os.chdir(ROOT)
import warnings  # noqa: E402
warnings.filterwarnings("ignore")
import joblib  # noqa: E402
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from scipy.signal import welch  # noqa: E402

import model_search as ms  # noqa: E402
from montage import MONTAGE  # noqa: E402

FS = 250
OUT = os.path.join(ROOT, "figures", "slides")
os.makedirs(OUT, exist_ok=True)
BG, FG, DIM, LINE = "#000000", "#e5e5e5", "#767676", "#2b2b2b"
YEL, ORA, BLU, GRN = "#fab413", "#f05a24", "#4f8fe8", "#2fbf71"
names = {f.name for f in font_manager.fontManager.ttflist}
FONT = next((f for f in ("Avenir Next", "Avenir", "Helvetica Neue", "Helvetica") if f in names), "DejaVu Sans")
plt.rcParams.update({"font.family": FONT, "font.size": 15, "text.color": FG, "axes.labelcolor": FG, "axes.edgecolor": LINE,
                     "xtick.color": DIM, "ytick.color": DIM, "axes.facecolor": BG, "figure.facecolor": BG,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": "#161616",
                     "grid.linewidth": 0.8, "savefig.facecolor": BG})


def slide(title, sub):
    fig = plt.figure(figsize=(16, 9), dpi=120)
    fig.text(0.05, 0.92, title, fontsize=30, color=FG, weight="bold")
    fig.text(0.05, 0.875, sub, fontsize=15, color=DIM)
    return fig


def save(fig, name, note):
    fig.text(0.05, 0.015, note, fontsize=11, color=DIM, va="bottom", linespacing=1.4)
    fig.savefig(os.path.join(OUT, name))
    plt.close(fig)
    print("wrote", os.path.join("figures", "slides", name))


def load_raw(path):
    rows = []
    for line in open(path):
        if line.startswith("#") or line.startswith("t,"):
            continue
        try:
            rows.append([float(v) for v in line.split(",")[1:9]])
        except ValueError:
            continue
    return np.array(rows).T


# ---- 01 / 02: one dry-cap window, raw vs after the live chain ----
live = joblib.load("models/readiness.joblib")
cfg, CH = live["feat_cfg"], list(live["channels"])
ms.CH[:] = CH
idx = [MONTAGE.index(c) for c in CH]
x = load_raw(sorted(glob.glob("recordings/paing_20261108_011525_raw*.csv"))[0])[idx]
best, best_e = None, None
for e in range(30 * FS, x.shape[1], FS):                      # a window with every model channel connected
    w = x[:, e - 4 * FS:e]
    if np.any(np.abs(np.abs(w) - 200000) < 1) or np.any(w.std(1) < 1e-6):
        continue
    hum = w[CH.index("Pz")] - w[CH.index("Pz")].mean()
    if best is None or hum.std() > best:                       # show a typical noisy window, not a cherry-picked clean one
        best, best_e = hum.std(), e
    if best_e is not None and e > best_e + 60 * FS:
        break
w = x[:, best_e - 4 * FS:best_e]
asr = ms.ASR(cfg["asr"])
base = [x[:, e - 4 * FS:e] for e in range(4 * FS, 30 * FS, FS)]
base = [b for b in base if not (np.any(np.abs(np.abs(b) - 200000) < 1) or np.any(b.std(1) < 1e-6))]
asr.fit([ms.clean_window(b, FS, cfg) for b in base]) if len(base) >= 5 else None
clean = ms.clean_window(w, FS, cfg)
if asr.V is not None:
    clean = asr(clean)
j = CH.index("Pz")
raw_pz = w[j] - w[j].mean()
t = np.arange(w.shape[1]) / FS

fig = slide("Cleaning a dry-electrode signal", "Same 4 seconds at Pz, Paing's dry cap: raw from the amplifier, then after the live cleaning chain")
a1 = fig.add_axes([0.07, 0.52, 0.88, 0.28]); a2 = fig.add_axes([0.07, 0.13, 0.88, 0.28])
a1.plot(t, raw_pz, color=ORA, lw=0.8); a1.set_ylabel("raw  (µV)")
a1.set_title(f"raw: {raw_pz.std():,.0f} µV RMS, drift and 50 Hz mains hum (brain signal is about 10 to 50 µV)", loc="left", color=ORA, fontsize=15, pad=8)
a2.plot(t, clean[j], color=BLU, lw=1.1); a2.set_ylabel("cleaned  (µV)"); a2.set_xlabel("time (s)")
a2.set_title(f"after the chain: {clean[j][FS // 2:-FS // 2].std():.0f} µV RMS, 4 to 30 Hz", loc="left", color=BLU, fontsize=15, pad=8)
z = np.flatnonzero(np.abs(clean[j]) < 1e-9)
if len(z) > FS // 10:
    a2.annotate("burst mask: artefact zeroed", (t[z[len(z) // 2]], 0), xytext=(t[z[len(z) // 2]] + 0.15, clean[j].max() * 0.8), color=DIM, fontsize=13,
                arrowprops=dict(arrowstyle="->", color=DIM))
for a in (a1, a2):
    a.set_xlim(0, 4)
save(fig, "01_dsp_time.png", "Chain: cubic detrend, 50/100 Hz notch, median common reference, 4 to 30 Hz band-pass, Hilbert burst mask, artefact subspace reconstruction. Recording paing_20261108_011525.")

f0, p0 = welch(raw_pz, fs=FS, nperseg=2 * FS)
f1, p1 = welch(clean[j], fs=FS, nperseg=2 * FS)
fig = slide("Where the noise lives", "Power spectrum of the same window: drift below 4 Hz and mains at 50 and 100 Hz dominate the raw signal; the chain keeps 4 to 30 Hz")
a = fig.add_axes([0.08, 0.13, 0.86, 0.66])
a.semilogy(f0, p0, color=ORA, lw=1.6, label="raw")
a.semilogy(f1, p1 + 1e-6, color=BLU, lw=2.0, label="after the chain")
for lo, hi, nm in ((4, 8, "theta"), (8, 13, "alpha"), (13, 30, "beta")):
    a.axvspan(lo, hi, color="#ffffff", alpha=0.04)
    a.text((lo + hi) / 2, a.get_ylim()[1] * 0.3, nm, ha="center", color=DIM, fontsize=14)
pk = int(np.argmin(np.abs(f0 - 50)))
a.annotate("50 Hz mains", (50, p0[pk]), xytext=(60, p0[pk] * 3), color=ORA, fontsize=14, arrowprops=dict(arrowstyle="->", color=ORA))
a.set_xlim(0, 110); a.set_xlabel("frequency (Hz)"); a.set_ylabel("power (µV² / Hz)")
a.legend(frameon=False, fontsize=14, loc="upper right")
save(fig, "02_dsp_spectrum.png", "Welch, 2 s segments. Same Pz window as the previous slide.")

# ---- 05 / 06: the chain stage by stage (same window, same code path as model_search.clean_window) ----
from scipy.signal import butter as _butter, hilbert as _hilbert, iirnotch as _iirnotch, sosfiltfilt as _sff, tf2sos as _tf2sos  # noqa: E402
stages = []
ok = (w.std(1) > 1e-6) & ~np.any(np.abs(np.abs(w) - 200000) < 1, axis=1)
y = w - w.mean(1, keepdims=True)
stages.append(("raw signal", "what the amplifier sends", y.copy()))
tt_ = np.linspace(-1, 1, y.shape[1]); V = np.vander(tt_, int(cfg["detrend"]) + 1)
coef, *_ = np.linalg.lstsq(V, y.T, rcond=None); y = y - (V @ coef).T
stages.append(("1  cubic detrend", "removes slow electrode drift and sweat potentials", y.copy()))
for f0 in (50.0, 100.0):
    b_, a_ = _iirnotch(f0, 30.0, fs=FS); y = _sff(_tf2sos(b_, a_), y, axis=1)
stages.append(("2  notch 50 and 100 Hz", "removes mains hum from the room's wiring", y.copy()))
y = y - np.median(y[ok], axis=0, keepdims=True)
stages.append(("3  median common reference", "removes noise shared by every electrode", y.copy()))
y = _sff(_butter(cfg.get("order", 4), [cfg["lo"], cfg["hi"]], btype="band", fs=FS, output="sos"), y, axis=1)
stages.append(("4  band-pass 4 to 30 Hz", "keeps theta, alpha and beta; drops muscle and drift", y.copy()))
env = np.abs(_hilbert(y, axis=1)); bad = env > cfg["burst"] * np.median(env, axis=1, keepdims=True) + 1e-9
edge = int(0.5 * FS); bad[:, :edge] = False; bad[:, -edge:] = False
k_ = max(3, int(FS * 0.05)); soft = np.array([np.convolve(bb.astype(float), np.ones(k_) / k_, mode="same") for bb in bad])
y = y * np.clip(1.0 - soft * 1.5, 0.0, 1.0)
assert np.allclose(y, ms.clean_window(w, FS, cfg)), "stage-by-stage chain differs from clean_window"
stages.append(("5  burst mask", "zeroes sudden jumps (envelope over 4 x median)", y.copy()))
if asr.V is not None:
    y = asr(y)
    stages.append(("6  artefact subspace reconstruction", "removes components over 5 x their resting power", y.copy()))
fig = slide("The cleaning chain, one filter at a time", "Same 4 seconds at Pz, Paing's dry cap; each row is the signal after one more stage (each row has its own scale)")
n = len(stages); top, bot = 0.83, 0.12; hgt = (top - bot) / n
for i, (nm, what, yy) in enumerate(stages):
    ax = fig.add_axes([0.30, top - (i + 1) * hgt + 0.012, 0.52, hgt - 0.024])
    col = ORA if i == 0 else (BLU if i == n - 1 else FG)
    ax.plot(t, yy[j], color=col, lw=1.0 if i else 0.8)
    ax.set_xlim(0, 4); ax.set_yticks([]); ax.grid(False)
    ax.spines["left"].set_visible(False)
    if i < n - 1:
        ax.set_xticks([])
        ax.spines["bottom"].set_visible(False)
    else:
        ax.set_xlabel("time (s)")
    fig.text(0.05, top - (i + 0.5) * hgt + 0.012, nm, fontsize=17, color=col, va="center", weight="bold")
    fig.text(0.05, top - (i + 0.5) * hgt - 0.018, what, fontsize=12, color=DIM, va="center")
    r = yy[j][FS // 2:-FS // 2].std()
    fig.text(0.84, top - (i + 0.5) * hgt, f"{r:,.0f} µV RMS", fontsize=17, color=col, va="center")
save(fig, "05_dsp_pipeline.png", "Code path checked against model_search.clean_window (identical output). Recording paing_20261108_011525. Brain EEG is about 10 to 50 µV.")

fig = slide("What each filter removes, in frequency", "Spectrum of the same window after successive stages")
a = fig.add_axes([0.08, 0.18, 0.86, 0.60])
pick = [0, 1, 2, 4, n - 1]
cols = [ORA, "#c97a2a", YEL, GRN, BLU]
for c, i in zip(cols, pick):
    f_, p_ = welch(stages[i][2][j], fs=FS, nperseg=2 * FS)
    a.semilogy(f_, p_ + 1e-6, color=c, lw=1.8, label=stages[i][0].split("  ")[-1])
a.set_xlim(0, 110); a.set_xlabel("frequency (Hz)"); a.set_ylabel("power (µV² / Hz)")
a.set_ylim(1e-4, 3e7)
fig.legend(*a.get_legend_handles_labels(), frameon=False, fontsize=14, loc="upper left", bbox_to_anchor=(0.06, 0.845), ncol=5)
for lo, hi, nm in ((4, 8, "theta"), (8, 13, "alpha"), (13, 30, "beta")):
    a.axvspan(lo, hi, color="#ffffff", alpha=0.04)
    a.text((lo + hi) / 2, 1.2e7, nm, ha="center", color=DIM, fontsize=13)
save(fig, "06_dsp_stage_spectra.png", "Welch, 2 s segments. The notch cuts the 50 and 100 Hz peaks; reference and band-pass remove most power below 4 Hz and above 30 Hz;\nthe burst mask and ASR take out the movement spike (blue, lower in 4 to 30 Hz). Detrend barely changes this particular window.")

# ---- 03: held-out AUC per lab person ----
d = json.load(open("models/lab_demo_loso.json"))
per = sorted(d["per_person_auc"].items(), key=lambda kv: kv[1])
fig = slide("Does it work on people it has never seen?", "Each bar: one of 36 people, scored by a model trained on the other 35 (lab EEG, rest vs mental arithmetic)")
a = fig.add_axes([0.07, 0.13, 0.88, 0.66])
cols = [YEL if k == d["pick"] else (GRN if v >= 0.7 else (DIM if v >= 0.5 else ORA)) for k, v in per]
a.bar(range(len(per)), [v for _, v in per], color=cols, width=0.75)
a.axhline(0.5, color=ORA, lw=1.2, ls="--"); a.text(36.2, 0.505, "chance", color=ORA, ha="left", va="bottom", fontsize=13); a.set_xlim(-0.8, 38.5)
a.axhline(d["median"], color=FG, lw=1.0, ls=":"); a.text(0.0, d["median"] + 0.01, f"median {d['median']:.2f}", color=FG, fontsize=13)
a.set_ylim(0.3, 1.0); a.set_xticks([]); a.set_ylabel("held-out AUC"); a.set_xlabel("36 people, sorted")
k = [i for i, (s, _) in enumerate(per) if s == d["pick"]][0]
a.annotate(f"demo person {d['pick']}", (k, per[k][1]), xytext=(k - 9, 0.97), color=YEL, fontsize=13, arrowprops=dict(arrowstyle="->", color=YEL))
save(fig, "03_ml_per_person.png", f"Green: AUC 0.7 or more ({d['n_over_0_7']} of 36). Grey: 0.5 to 0.7. Orange: below chance ({d['n_under_0_5']}). Gradient boosting on 5 channels (Fz C3 Cz Pz O1), amplitude-invariant band features. PhysioNet eegmat.")

# ---- 04: the lab demo through the live gauge ----
logp = os.path.join(OUT, "_lab_demo_gauge.csv")
port = subprocess.run([sys.executable, "tests/free_port.py"], capture_output=True, text=True).stdout.strip()
srv = subprocess.Popen([sys.executable, "loadmonitor/gauge_server.py", port], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    import time
    time.sleep(1.2)
    subprocess.run([sys.executable, "loadmonitor/load_gauge.py", "--replay", "demo/lab_eegmat_s09_raw.csv", "--model", "models/readiness_demo.joblib",
                    "--speed", "40", "--web", "--web-port", port, "--no-ui", "--alarm", "50", "--hold", "20", "--smooth", "12", "--log", logp],
                   capture_output=True, timeout=600)
finally:
    srv.terminate()
    subprocess.run(["rmdir", f"/tmp/oxn_test_port_{port}"], capture_output=True)
import csv  # noqa: E402
R = list(csv.DictReader(open(logp)))
tt = np.array([float(r["t"]) for r in R]); L = np.array([float(r["load_pct"]) for r in R]); A = np.array([int(r["alarm"]) for r in R])
xl = load_raw("demo/lab_eegmat_s09_raw.csv")
al = []
for e in range(4 * FS, xl.shape[1] + 1, FS):
    ps = []
    for c in ("Pz", "O1"):
        f, p = welch(xl[MONTAGE.index(c), e - 4 * FS:e] - xl[MONTAGE.index(c), e - 4 * FS:e].mean(), fs=FS, nperseg=2 * FS)
        ps.append(10 * np.log10(p[(f >= 8) & (f < 13)].mean()))
    al.append(np.mean(ps))
al = np.array(al); ta = np.arange(4, 4 + len(al))
al = al - al[(ta >= 4) & (ta < 34)].mean()
al_s = np.convolve(al, np.ones(9) / 9, mode="same")
fig = slide("Mental load, live, on a held-out person", "Lab EEG (public dataset, gel cap) streamed through the live gauge: rest, silent subtraction, rest")
a = fig.add_axes([0.07, 0.45, 0.88, 0.38]); b = fig.add_axes([0.07, 0.17, 0.88, 0.20], sharex=a)
for lo, hi, nm, c in ((34, 90, "rest", BLU), (90, 150, "mental arithmetic", YEL), (150, 210, "recovery", BLU)):
    for ax in (a, b):
        ax.axvspan(lo, hi, color=c, alpha=0.07)
    a.text((lo + hi) / 2, 104, nm, ha="center", color=c, fontsize=15)
a.plot(tt, L, color=FG, lw=2.4)
a.fill_between(tt, 0, L, where=A > 0, color=ORA, alpha=0.35, label="alarm (above 50 for 20 s)")
a.axhline(50, color=ORA, lw=1, ls="--")
a.set_ylim(-2, 112); a.set_ylabel("mental load (0 = own rest)"); a.legend(frameon=False, loc="lower left", bbox_to_anchor=(0.0, 0.12), fontsize=13)
b.plot(ta, al_s, color=GRN, lw=2); b.axhline(0, color=DIM, lw=0.8)
b.set_ylabel("posterior alpha\n(dB vs rest)"); b.set_xlabel("time (s)"); b.set_xlim(34, 210)
save(fig, "04_ml_live_demo.png", "Person 09, held out of the model's training. The alarm lingers into recovery because the load is smoothed over 12 s.\nThe recovery minute is the same person's earlier rest (the dataset has no rest after the task). Alpha: 8 to 13 Hz, mean of Pz and O1, 9 s smoothing.")
os.remove(logp)
