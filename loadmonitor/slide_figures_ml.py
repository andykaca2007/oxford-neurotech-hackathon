"""Training curve and ROC slides for the live model, from one leave-one-subject-out run (same recipe as the live model).

    .venv/bin/python loadmonitor/slide_figures_ml.py        # about 5 minutes; features cached in models/_slide_feats.npz

For each of the 36 eegmat people: train gradient boosting (live settings) on the other 35, score that person's windows
at every boosting stage. Gives
  11 training curve: mean train AUC and mean held-out AUC (per person) against the number of boosting trees
  12 ROC: pooled held-out ROC over all 36 people with its AUC, and each person's own curve faintly behind it
"""
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
import joblib  # noqa: E402
from sklearn.base import clone  # noqa: E402
from sklearn.metrics import roc_auc_score, roc_curve  # noqa: E402

import model_search as ms  # noqa: E402
import readiness_model as rm  # noqa: E402
import slide_style as st  # noqa: E402

live = joblib.load("models/readiness.joblib")
CH, cfg = list(live["channels"]), live["feat_cfg"]
cache = "models/_slide_feats.npz"
if os.path.exists(cache):
    z = np.load(cache, allow_pickle=True); X, y, subj = z["X"], z["y"], z["subj"]
else:
    rm.CH[:] = CH
    X, y, subj = ms.build(4.0, True, True, cfg)
    np.savez(cache, X=X, y=y, subj=subj)
nb = 6 - int(bool(cfg.get("drop_delta"))) - int(bool(cfg.get("drop_gamma")))
mask = np.ones(X.shape[1], bool); mask[:nb * len(CH)] = False; mask[-1] = False
X = X[:, mask]
gb = dict(ms.models())["grad boosting"]
n_est = gb.get_params()["n_estimators"]
stages = np.arange(1, n_est + 1)
tr_auc, te_auc = np.zeros((0, n_est)), np.zeros((0, n_est))
pooled_p, pooled_y, per_curves = [], [], []
for s in sorted(set(subj)):
    tr, te = subj != s, subj == s
    m = clone(gb).fit(X[tr], y[tr])
    tr_auc = np.vstack([tr_auc, [roc_auc_score(y[tr], p[:, 1]) for p in m.staged_predict_proba(X[tr])]])
    te_auc = np.vstack([te_auc, [roc_auc_score(y[te], p[:, 1]) for p in m.staged_predict_proba(X[te])]])
    p = m.predict_proba(X[te])[:, 1]
    pooled_p.append(p); pooled_y.append(y[te]); per_curves.append(roc_curve(y[te], p)[:2])
    print(f"  person {s}: held-out AUC {te_auc[-1, -1]:.3f}", flush=True)
pp, py = np.concatenate(pooled_p), np.concatenate(pooled_y)
pooled = roc_auc_score(py, pp)
med = float(np.median(te_auc[:, -1]))

# ---- 11 training curve ----
fig = st.slide("Training curve", "Gradient boosting, one tree at a time: accuracy on the training people vs on the person left out (36 rounds)")
a = fig.add_axes([0.08, 0.19, 0.86, 0.58])
for arr, col, nm in ((tr_auc, st.BLU, "training people"), (te_auc, st.GRN, "held-out person (never seen)")):
    mu, lo, hi = arr.mean(0), np.percentile(arr, 25, axis=0), np.percentile(arr, 75, axis=0)
    a.fill_between(stages, lo, hi, color=col, alpha=0.15)
    a.plot(stages, mu, color=col, lw=2.6, label=nm)
a.axhline(0.5, color=st.ORA, lw=1.2, ls="--"); a.text(n_est, 0.505, "chance", color=st.ORA, ha="right", va="bottom", fontsize=13)
a.set_xlim(1, n_est); a.set_ylim(0.45, 1.0); a.set_xlabel("number of boosting trees"); a.set_ylabel("AUC (rest vs arithmetic)")
a.legend(frameon=False, fontsize=15, loc="lower right", bbox_to_anchor=(1.0, 0.12))
a.text(n_est * 0.98, tr_auc.mean(0)[-1] + 0.012, f"{tr_auc.mean(0)[-1]:.2f}", color=st.BLU, ha="right", fontsize=15)
a.text(n_est * 0.98, te_auc.mean(0)[-1] + 0.012, f"{te_auc.mean(0)[-1]:.2f}", color=st.GRN, ha="right", fontsize=15)
st.save(fig, "11_training_curve.png", f"Lines: mean over 36 leave-one-person-out rounds; bands: 25th to 75th percentile. The gap between the lines is what does not transfer to a new person.\n"
        f"Live recipe: 5 channels (Fz C3 Cz Pz O1), cleaning chain, {X.shape[1]} amplitude-invariant features, {n_est} trees of depth 2. PhysioNet eegmat.")

# ---- 12 ROC ----
fig = st.slide("ROC on people the model never saw", "Each of 36 people scored by a model trained on the other 35; rest vs mental arithmetic, one 4 s window at a time")
a = fig.add_axes([0.30, 0.13, 0.40, 0.66])
for fpr, tpr in per_curves:
    a.plot(fpr, tpr, color=st.DIM, lw=0.7, alpha=0.25)
fpr, tpr, _ = roc_curve(py, pp)
a.plot(fpr, tpr, color=st.GRN, lw=3.2, label=f"all 36 pooled: AUROC {pooled:.2f}")
a.plot([0, 1], [0, 1], color=st.ORA, ls="--", lw=1.2, label="chance: 0.50")
a.set_xlim(0, 1); a.set_ylim(0, 1); a.set_aspect("equal")
a.set_xlabel("false positive rate (rest called load)"); a.set_ylabel("true positive rate (arithmetic caught)")
a.legend(frameon=False, fontsize=14, loc="lower right")
fig.text(0.74, 0.62, f"{pooled:.2f}", fontsize=64, color=st.GRN, weight="bold")
fig.text(0.74, 0.57, "pooled held-out AUROC", fontsize=15, color=st.FG)
fig.text(0.74, 0.47, f"{med:.2f}", fontsize=40, color=st.FG)
fig.text(0.74, 0.43, "median per person", fontsize=15, color=st.DIM)
fig.text(0.74, 0.33, f"{int(np.sum(te_auc[:, -1] >= 0.7))} of 36", fontsize=40, color=st.FG)
fig.text(0.74, 0.29, "people at 0.7 or more", fontsize=15, color=st.DIM)
st.save(fig, "12_roc.png", "Grey: each person's own ROC. Green: all held-out windows pooled. Per-window scores before the live smoothing; lab gel-cap data, not validated on the dry cap.")
print(f"pooled AUROC {pooled:.3f}, median per person {med:.3f}, final train {tr_auc.mean(0)[-1]:.3f}, held-out {te_auc.mean(0)[-1]:.3f}")
