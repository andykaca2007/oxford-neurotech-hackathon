"""The six presentation figures, editorial style (loadmonitor/figstyle.py), all from real data.

    .venv/bin/python loadmonitor/figures_editorial.py        # writes figures/slides/best8/1..8 (about 6 min; ML pass cached)

1 how it works   2 raw to clean (stage by stage, plus the spectrum)   3 training curve   4 ROC on unseen people   5 live demo trace   6 app (screenshot)
"""
import csv
import glob
import json
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "headset"))
os.chdir(ROOT)
import warnings  # noqa: E402
warnings.filterwarnings("ignore")
import joblib  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from scipy.signal import butter, hilbert, iirnotch, resample_poly, sosfiltfilt, tf2sos, welch  # noqa: E402
from sklearn.base import clone  # noqa: E402
from sklearn.metrics import roc_auc_score, roc_curve  # noqa: E402

import figstyle as F  # noqa: E402
import model_search as ms  # noqa: E402
import readiness_model as rm  # noqa: E402
from montage import MONTAGE  # noqa: E402

FS = 250
BEST = os.path.join(F.OUT, "best8")
os.makedirs(BEST, exist_ok=True)
live = joblib.load("models/readiness.joblib")
CH, cfg = list(live["channels"]), live["feat_cfg"]
NOTCH = tf2sos(*iirnotch(50.0, 30.0, fs=FS))


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


def out(fig, n, name):
    F.save(fig, name)
    import shutil
    shutil.copy(os.path.join(F.OUT, name), os.path.join(BEST, f"{n}_{name}"))


# ---------- 1 how it works ----------
fig = F.page("Eight electrodes become one number, once a second", "Every stage runs on the last 4 seconds of EEG; the model is the only learned part")
a = fig.add_axes([F.LEFT, 0.12, F.RIGHT - F.LEFT, 0.66]); a.set_xlim(0, 100); a.set_ylim(0, 100); a.axis("off"); a.grid(False)
steps = [("Headset", "8 dry electrodes, 250 Hz", False), ("Contact check", "open, noisy or clean, per electrode", False),
         ("Cleaning chain", "detrend, notch, reference, band-pass, burst mask, ASR", False), ("Features", "29 relative band powers and ratios", False),
         ("Model", "gradient boosting, 36 people, held-out AUC 0.76", True), ("Personal scale", "0 = your own rest, alarm at 50", False),
         ("Page", "load, why it moved, head map", False)]
n = len(steps); w = 11.5; gap = (100 - n * w) / (n - 1)
for i, (t, s, hot) in enumerate(steps):
    x = i * (w + gap)
    a.add_patch(Rectangle((x, 64), w, 14, fill=hot, fc=F.ACCENT if hot else F.PAGE, ec=F.ACCENT if hot else F.INK2, lw=1.0))
    a.text(x + w / 2, 71, t, ha="center", va="center", fontsize=15, color=F.PAGE if hot else F.INK, weight="medium")
    import textwrap
    a.text(x + w / 2, 59, "\n".join(textwrap.wrap(s, 22)), ha="center", va="top", fontsize=12, color=F.INK2, linespacing=1.3)
    if i < n - 1:
        a.annotate("", (x + w + gap - 0.4, 71), (x + w + 0.4, 71), arrowprops=dict(arrowstyle="-|>", color=F.INK2, lw=1.0, mutation_scale=12))
a.text(0, 30, "If any model electrode is open the number is held; if one is noisy the number is shown grey with the alarm off.", fontsize=14, color=F.INK, va="center")
a.text(0, 23, "A bad signal is reported as bad, never scored.", fontsize=14, color=F.INK2, va="center")
F.source(fig, "Source: loadmonitor/load_gauge.py, gauge_server.py, web/index.html. Optional Claude debrief when an API key is set.")
out(fig, 1, "how_it_works.png")

# ---------- 2 and 3: the chain stage by stage, one dry-cap window ----------
rm.CH[:] = CH
idx = [MONTAGE.index(c) for c in CH]
x = load_raw(sorted(glob.glob("recordings/paing_20261108_011525_raw*.csv"))[0])[idx]
best, best_e = None, None
for e in range(30 * FS, x.shape[1], FS):
    w_ = x[:, e - 4 * FS:e]
    if np.any(np.abs(np.abs(w_) - 200000) < 1) or np.any(w_.std(1) < 1e-6):
        continue
    hum = w_[CH.index("Pz")] - w_[CH.index("Pz")].mean()
    if best is None or hum.std() > best:
        best, best_e = hum.std(), e
    if best_e is not None and e > best_e + 60 * FS:
        break
w = x[:, best_e - 4 * FS:best_e]
asr = ms.ASR(cfg["asr"])
base = [x[:, e - 4 * FS:e] for e in range(4 * FS, 30 * FS, FS)]
base = [b for b in base if not (np.any(np.abs(np.abs(b) - 200000) < 1) or np.any(b.std(1) < 1e-6))]
if len(base) >= 5:
    asr.fit([ms.clean_window(b, FS, cfg) for b in base])
j = CH.index("Pz"); t = np.arange(w.shape[1]) / FS
ok = (w.std(1) > 1e-6) & ~np.any(np.abs(np.abs(w) - 200000) < 1, axis=1)
y = w - w.mean(1, keepdims=True); stages = [("Raw", "from the amplifier", y.copy())]
tt_ = np.linspace(-1, 1, y.shape[1]); V = np.vander(tt_, int(cfg["detrend"]) + 1)
coef, *_ = np.linalg.lstsq(V, y.T, rcond=None); y = y - (V @ coef).T; stages.append(("Detrend", "slow drift removed", y.copy()))
for f0 in (50.0, 100.0):
    y = sosfiltfilt(tf2sos(*iirnotch(f0, 30.0, fs=FS)), y, axis=1)
stages.append(("Notch", "50 and 100 Hz mains removed", y.copy()))
y = y - np.median(y[ok], axis=0, keepdims=True); stages.append(("Reference", "shared noise removed", y.copy()))
y = sosfiltfilt(butter(cfg.get("order", 4), [cfg["lo"], cfg["hi"]], btype="band", fs=FS, output="sos"), y, axis=1)
stages.append(("Band-pass", "4 to 30 Hz kept", y.copy()))
env = np.abs(hilbert(y, axis=1)); bad = env > cfg["burst"] * np.median(env, axis=1, keepdims=True) + 1e-9
edge = int(0.5 * FS); bad[:, :edge] = False; bad[:, -edge:] = False
k_ = max(3, int(FS * 0.05)); soft = np.array([np.convolve(bb.astype(float), np.ones(k_) / k_, mode="same") for bb in bad])
y = y * np.clip(1.0 - soft * 1.5, 0.0, 1.0)
assert np.allclose(y, ms.clean_window(w, FS, cfg))
stages.append(("Burst mask", "sudden jumps zeroed", y.copy()))
if asr.V is not None:
    y = asr(y); stages.append(("ASR", "components far above rest removed", y.copy()))

fig = F.page("Six filters take a dry electrode from 6,000 µV of noise to 34 µV of EEG", "The same 4 seconds at Pz on Paing's cap: the signal after each stage (each row on its own scale) and its power spectrum")
n = len(stages); top, bot = 0.79, 0.16; h = (top - bot) / n
for i, (nm, what, yy) in enumerate(stages):
    ax = fig.add_axes([0.235, top - (i + 1) * h + 0.008, 0.265, h - 0.016]); ax.grid(False); ax.axis("off")
    last = i == n - 1
    ax.plot(t, yy[j], color=F.ACCENT if last else F.INK, lw=1.3 if last else 0.9); ax.set_xlim(0, 4)
    fig.text(F.LEFT, top - (i + 0.5) * h + 0.010, nm, fontsize=15, color=F.ACCENT if last else F.INK, va="center", weight="medium")
    fig.text(F.LEFT, top - (i + 0.5) * h - 0.014, what, fontsize=11, color=F.INK2, va="center")
    r = yy[j][FS // 2:-FS // 2].std()
    fig.text(0.515, top - (i + 0.5) * h, f"{r:,.0f}", fontsize=16, color=F.ACCENT if last else F.INK, va="center", ha="left")
fig.text(0.515, top + 0.008, "µV RMS", fontsize=13, color=F.INK2, va="bottom")
ax.axis("on"); ax.spines["bottom"].set_visible(True); ax.spines["bottom"].set_color(F.INK2); ax.set_yticks([]); ax.set_xticks([0, 2, 4]); ax.set_xticklabels(["0", "2", "4 s"])
a = F.axes(fig, (0.61, 0.16, 0.30, 0.63))
pick = [(0, F.GREY, 1.1), (2, F.INK2, 1.1), (4, F.INK, 1.8), (n - 1, F.ACCENT, 2.4)]
for lo, hi, nm in ((4, 8, "θ"), (8, 13, "α"), (13, 30, "β")):
    a.axvspan(lo, hi, color=F.BAND, lw=0)
    a.text((lo + hi) / 2, 2e7, nm, ha="center", va="top", fontsize=13, color=F.INK2)
for i, col, lw in pick:
    f_, p_ = welch(stages[i][2][j], fs=FS, nperseg=2 * FS)
    a.semilogy(f_, p_ + 1e-5, color=col, lw=lw)
a.set_xlim(0, 110); a.set_ylim(1e-4, 5e7); a.set_xticks([0, 50, 100]); a.set_xticklabels(["0", "50", "100 Hz"]); a.set_yticks([1e-4, 1e0, 1e4])
a.set_yticklabels(["0.0001", "1", "10,000"]); a.text(0, 1.02, "µV² per Hz", transform=a.transAxes, fontsize=13, color=F.INK2, va="bottom")
a.annotate("50 Hz mains", (50, 1e5), xytext=(60, 4e6), color=F.INK2, fontsize=12, arrowprops=dict(arrowstyle="-", color=F.INK2, lw=0.75))
F.end_label(a, 110, 1.5, "raw", F.GREY, size=12); F.end_label(a, 110, 0.15, "notched", F.INK2, size=12)
a.text(36, 8e-2, "band-passed", color=F.INK, fontsize=12, ha="left", va="center", bbox=dict(fc=F.PAGE, ec="none", pad=1.5)); F.end_label(a, 110, 2e-3, "full chain", F.ACCENT, weight="medium", size=12)
F.source(fig, "Source: recording paing_20261108_011525, Pz. Stage outputs verified identical to the live code (model_search.clean_window). Scalp EEG is about 10 to 50 µV. Spectrum: Welch, 2 s segments.")
out(fig, 2, "raw_to_clean.png")

# ---------- 5 and 6: training curve and ROC, one leave-one-person-out pass ----------
cache = "models/_slide_feats.npz"
rm.CH[:] = CH
if os.path.exists(cache):
    z = np.load(cache, allow_pickle=True); X, yv, subj = z["X"], z["y"], z["subj"]
else:
    X, yv, subj = ms.build(4.0, True, True, cfg); np.savez(cache, X=X, y=yv, subj=subj)
nb = 6 - int(bool(cfg.get("drop_delta"))) - int(bool(cfg.get("drop_gamma")))
mask = np.ones(X.shape[1], bool); mask[:nb * len(CH)] = False; mask[-1] = False
X = X[:, mask]
gb = dict(ms.models())["grad boosting"]; n_est = gb.get_params()["n_estimators"]; stg = np.arange(1, n_est + 1)
cache2 = "models/_slide_loso.joblib"
if os.path.exists(cache2):
    tr_auc, te_auc, pp, py, per_curves = joblib.load(cache2)
else:
    tr_auc, te_auc, pps, pys, per_curves = [], [], [], [], []
    for s_ in sorted(set(subj)):
        tr, te = subj != s_, subj == s_
        m = clone(gb).fit(X[tr], yv[tr])
        tr_auc.append([roc_auc_score(yv[tr], p[:, 1]) for p in m.staged_predict_proba(X[tr])])
        te_auc.append([roc_auc_score(yv[te], p[:, 1]) for p in m.staged_predict_proba(X[te])])
        p = m.predict_proba(X[te])[:, 1]; pps.append(p); pys.append(yv[te]); per_curves.append(roc_curve(yv[te], p)[:2])
    tr_auc, te_auc = np.array(tr_auc), np.array(te_auc); pp, py = np.concatenate(pps), np.concatenate(pys)
    joblib.dump((tr_auc, te_auc, pp, py, per_curves), cache2)
pooled = roc_auc_score(py, pp); med_auc = float(np.median(te_auc[:, -1]))

fig = F.page("On a new person the model stops improving after about 50 trees", "AUC, rest vs arithmetic, as trees are added; mean of 36 leave-one-person-out rounds, band = middle half")
a = F.axes(fig, (F.LEFT, 0.16, 0.76, 0.62))
for arr, col, nm in ((tr_auc, F.GREY, "training people"), (te_auc, F.ACCENT, "person never seen")):
    mu = arr.mean(0)
    a.fill_between(stg, np.percentile(arr, 25, axis=0), np.percentile(arr, 75, axis=0), color=col, alpha=0.18, lw=0)
    a.plot(stg, mu, color=col, lw=2.6 if col == F.ACCENT else 2.0)
    F.end_label(a, n_est, mu[-1], f"{nm}  {mu[-1]:.2f}", F.INK2 if col == F.GREY else col, weight="medium" if col == F.ACCENT else "normal")
a.axhline(0.5, color=F.INK2, lw=1.0, ls=(0, (4, 3))); F.end_label(a, n_est, 0.5, "chance", F.INK2)
a.set_xlim(1, n_est); a.set_ylim(0.45, 1.0); a.set_xlabel("boosting trees"); a.set_yticks([0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
F.source(fig, "Source: PhysioNet EEG during mental arithmetic, 36 people. Live recipe: 5 channels, cleaning chain, 29 amplitude-invariant features, 200 trees of depth 2.")
out(fig, 3, "training_curve.png")

fig = F.page(f"On people it has never seen, the model reaches an AUROC of {pooled:.2f}", "Each of 36 people scored by a model trained on the other 35, one 4 s window at a time; grey = one person, green = all pooled")
a = fig.add_axes([0.30, 0.15, 0.40, 0.63]); a.tick_params(axis="y", length=0); a.grid(True, axis="both")
for fpr, tpr in per_curves:
    a.plot(fpr, tpr, color=F.GREY, lw=0.8, alpha=0.6)
fpr, tpr, _ = roc_curve(py, pp)
a.plot(fpr, tpr, color=F.ACCENT, lw=3.0)
a.plot([0, 1], [0, 1], color=F.INK2, lw=1.0, ls=(0, (4, 3)))
a.set_xlim(0, 1); a.set_ylim(0, 1); a.set_aspect("equal")
a.set_xlabel("false positive rate: rest called load"); a.text(-0.02, 1.02, "true positive rate: arithmetic caught", transform=a.transAxes, fontsize=F.T_AX, color=F.INK2, va="bottom")
fig.text(0.76, 0.66, f"{pooled:.2f}", fontsize=56, color=F.ACCENT, weight="medium", va="center")
fig.text(0.76, 0.60, "pooled AUROC, held out", fontsize=F.T_AX, color=F.INK2)
fig.text(0.76, 0.48, f"{med_auc:.2f}", fontsize=36, color=F.INK, va="center")
fig.text(0.76, 0.43, "median per person", fontsize=F.T_AX, color=F.INK2)
fig.text(0.76, 0.33, f"{int(np.sum(te_auc[:, -1] >= 0.7))} of 36", fontsize=36, color=F.INK, va="center")
fig.text(0.76, 0.28, "people at 0.7 or better", fontsize=F.T_AX, color=F.INK2)
F.source(fig, "Source: PhysioNet EEG during mental arithmetic (gel cap). Per-window scores before the live 12 s smoothing. Not validated on the dry cap.")
out(fig, 4, "roc.png")

# ---------- 7 live demo trace ----------
logp = os.path.join(F.OUT, "_lab_demo_gauge.csv")
port = subprocess.run([sys.executable, "tests/free_port.py"], capture_output=True, text=True).stdout.strip()
srv = subprocess.Popen([sys.executable, "loadmonitor/gauge_server.py", port], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    time.sleep(1.2)
    subprocess.run([sys.executable, "loadmonitor/load_gauge.py", "--replay", "demo/lab_eegmat_s09_raw.csv", "--model", "models/readiness_demo.joblib",
                    "--speed", "40", "--web", "--web-port", port, "--no-ui", "--alarm", "50", "--hold", "20", "--smooth", "12", "--log", logp],
                   capture_output=True, timeout=600)
finally:
    srv.terminate(); subprocess.run(["rmdir", f"/tmp/oxn_test_port_{port}"], capture_output=True)
R = list(csv.DictReader(open(logp))); os.remove(logp)
tt = np.array([float(r["t"]) for r in R]); L = np.array([float(r["load_pct"]) for r in R]); A = np.array([int(r["alarm"]) for r in R])
xl = load_raw("demo/lab_eegmat_s09_raw.csv")
al = []
for e in range(4 * FS, xl.shape[1] + 1, FS):
    al.append(np.mean([10 * np.log10(welch(xl[MONTAGE.index(c), e - 4 * FS:e] - xl[MONTAGE.index(c), e - 4 * FS:e].mean(), fs=FS, nperseg=2 * FS)[1][(np.arange(0, 125.5, 0.5) >= 8) & (np.arange(0, 125.5, 0.5) < 13)].mean()) for c in ("Pz", "O1")]))
al = np.array(al); ta = np.arange(4, 4 + len(al)); al = al - al[(ta >= 4) & (ta < 34)].mean(); al_s = np.convolve(al, np.ones(9) / 9, mode="same")
fig = F.page("A held-out person's load climbs during arithmetic and falls back at rest", "Lab EEG replayed through the live gauge; load with 0 = that person's own rest; posterior alpha below, dB vs rest")
a = F.axes(fig, (F.LEFT, 0.46, 0.80, 0.32)); b = F.axes(fig, (F.LEFT, 0.19, 0.80, 0.19))
for lo, hi, nm in ((34, 90, "rest"), (90, 150, "arithmetic"), (150, 210, "recovery")):
    a.axvspan(lo, hi, color=F.BAND if nm == "arithmetic" else F.PAGE, lw=0); b.axvspan(lo, hi, color=F.BAND if nm == "arithmetic" else F.PAGE, lw=0)
    a.text((lo + hi) / 2, 104, nm, ha="center", va="bottom", fontsize=14, color=F.INK)
a.plot(tt, L, color=F.INK, lw=2.6); a.fill_between(tt, 0, L, where=A > 0, color=F.ACCENT, alpha=0.35, lw=0)
a.axhline(50, color=F.INK2, lw=1.0, ls=(0, (4, 3))); F.end_label(a, 210, 50, "alarm line", F.INK2); F.end_label(a, 210, L[-1], "load", F.INK, weight="medium")
a.set_ylim(0, 115); a.set_yticks([0, 25, 50, 75, 100]); a.set_xlim(34, 210); a.tick_params(labelbottom=False)
b.plot(ta, al_s, color=F.INK2, lw=1.8); b.axhline(0, color=F.GREY, lw=0.75); F.end_label(b, 210, al_s[-3], "posterior alpha", F.INK2)
b.set_xlim(34, 210); b.set_yticks([-4, 0, 4]); b.set_xticks([40, 80, 120, 160, 200]); b.set_xticklabels(["40", "80", "120", "160", "200 s"])
F.source(fig, "Source: PhysioNet eegmat person 09, held out of the model's training. Shaded span = where the alarm was on (load above 50 for 20 s; it lingers from the 12 s smoothing).\n"
         "The recovery minute is the same person's earlier rest; the dataset has no rest after the task. Alpha: 8 to 13 Hz, mean of Pz and O1, 9 s smoothing.")
out(fig, 5, "live_demo.png")

# ---------- 8 app: the real page, untouched ----------
import shutil
shutil.copy(os.path.join(F.OUT, "10_app.png"), os.path.join(BEST, "6_app.png"))
print("wrote figures/slides/best8/6_app.png (screenshot)")
print(f"pooled AUROC {pooled:.3f}, median per person {med_auc:.3f}")
