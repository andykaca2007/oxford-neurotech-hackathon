"""5 channels vs 8 channels, paired per person (CRITIQUE stats-5).

"5 channels lose nothing" compared two means (0.762 vs 0.762) with no spread. This computes the per-person held-out
AUC for the 8-channel recipe (same robust chain, invariant mask, gradient boosting, leave-one-person-out over the 36
eegmat people), pairs it with the 5-channel per-person AUCs in models/lab_demo_loso.json (same recipe, written by
loadmonitor/lab_demo.py), and reports the paired difference with a bootstrap 95 percent CI and a Wilcoxon signed-rank
test. Writes models/channel_pair.json. About 5 minutes (feature extraction for 36 people).

    .venv/bin/python tests/channel_pair_test.py
"""
import json
import os
import sys
import warnings

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "loadmonitor"))
sys.path.insert(0, os.path.join(ROOT, "headset"))
os.chdir(ROOT)
warnings.filterwarnings("ignore")
import joblib  # noqa: E402
from scipy.stats import wilcoxon  # noqa: E402
from sklearn.base import clone  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402
import model_search as ms  # noqa: E402
import readiness_model as rm  # noqa: E402

LIVE = joblib.load("models/readiness.joblib")
cfg = LIVE["feat_cfg"]
CH8 = ["Fz", "C3", "Cz", "C4", "Pz", "P3", "P4", "O1"]


def per_person(channels):
    rm.CH[:] = channels
    X, y, subj = ms.build(4.0, True, True, cfg)
    nb = 6 - int(bool(cfg.get("drop_delta"))) - int(bool(cfg.get("drop_gamma")))
    mask = np.ones(X.shape[1], bool); mask[:nb * len(channels)] = False; mask[-1] = False      # as --fit-best --invariant
    X = X[:, mask]
    gb = dict(ms.models())["grad boosting"]
    per = {}
    for s in sorted(set(subj)):
        tr, te = subj != s, subj == s
        p = clone(gb).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
        per[s] = float(roc_auc_score(y[te], p))
    return per, int(mask.sum())


def main():
    five = json.load(open("models/lab_demo_loso.json"))["per_person_auc"]
    print(f"5-channel per-person AUCs from models/lab_demo_loso.json: {len(five)} people, median {np.median(list(five.values())):.3f}", flush=True)
    eight, nfeat = per_person(CH8)
    keys = sorted(set(five) & set(eight))
    a5 = np.array([five[k] for k in keys]); a8 = np.array([eight[k] for k in keys])
    d = a5 - a8
    rng = np.random.default_rng(0)
    boot = np.array([np.mean(d[rng.integers(0, len(d), len(d))]) for _ in range(10000)])
    lo, hi = np.percentile(boot, [2.5, 97.5])
    try:
        w = wilcoxon(a5, a8)
        p = float(w.pvalue)
    except ValueError:
        p = float("nan")
    out = dict(n=len(keys), features_8ch=nfeat, mean_5=float(a5.mean()), mean_8=float(a8.mean()), median_5=float(np.median(a5)), median_8=float(np.median(a8)),
               paired_diff_mean=float(d.mean()), paired_diff_sd=float(d.std(ddof=1)), ci95=[float(lo), float(hi)], wilcoxon_p=p,
               n_5_better=int(np.sum(d > 0)), n_8_better=int(np.sum(d < 0)), per_person_8ch={k: round(eight[k], 3) for k in keys})
    json.dump(out, open("models/channel_pair.json", "w"), indent=1)
    print(f"n {out['n']}: 5 ch mean {out['mean_5']:.3f} (median {out['median_5']:.3f}), 8 ch mean {out['mean_8']:.3f} (median {out['median_8']:.3f}); "
          f"paired 5 minus 8: mean {out['paired_diff_mean']:+.3f}, sd {out['paired_diff_sd']:.3f}, bootstrap 95% CI {lo:+.3f} to {hi:+.3f}, "
          f"Wilcoxon p {p:.3f}; 5 ch better for {out['n_5_better']}, 8 ch better for {out['n_8_better']}", flush=True)
    print("wrote models/channel_pair.json")


if __name__ == "__main__":
    main()
