"""Model search for the mental-load classifier, scored leave-one-subject-out.

    .venv/bin/python loadmonitor/model_search.py            # prints a table, saves figures/model_search.png
    .venv/bin/python loadmonitor/model_search.py --save     # also writes the best model to models/readiness.joblib

What varies:
  window      2, 4, 6 s of EEG per decision
  overlap     0 (no augmentation) or 50 percent sliding windows (2x the epochs)
  features    basic (17: theta/alpha/beta log power x 5 ch + 2 ratios)
              rich (adds delta 1-4, low beta 13-20, high beta 20-30, gamma 30-40, relative powers,
                    spectral entropy, Fz-Pz theta gradient, blink-band power on Fz)
  model       logistic regression (C grid), LDA with shrinkage, RBF SVM, random forest,
              gradient boosting, small MLP
Every row: mean balanced accuracy over 36 held-out subjects, mean AUC, and the train-set accuracy
so the gap (over/underfitting) is visible. The C grid is picked on the same LOSO, so treat the
best logistic row as slightly optimistic (nested CV would be the strict version).
"""
import argparse
import glob
import os
import re
import sys
import warnings

import numpy as np
from scipy.signal import butter, sosfiltfilt, welch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from readiness_model import CH, load_edf  # noqa: E402

warnings.filterwarnings("ignore")
BANDS_BASIC = {"theta": (4, 8), "alpha": (8, 13), "beta": (13, 30)}
BANDS_RICH = {"delta": (1, 4), "theta": (4, 8), "alpha": (8, 13), "lbeta": (13, 20), "hbeta": (20, 30), "gamma": (30, 40)}


def feats(x, fs, rich):
    sos = butter(4, [1, 40], btype="band", fs=fs, output="sos")
    x = sosfiltfilt(sos, x - x.mean(1, keepdims=True), axis=1)
    f, p = welch(x, fs=fs, nperseg=int(fs * 2), axis=1)
    bands = BANDS_RICH if rich else BANDS_BASIC
    bp = {b: p[:, (f >= lo) & (f < hi)].mean(1) for b, (lo, hi) in bands.items()}
    out = [np.log(bp[b] + 1e-12) for b in bands]
    fz, pz, cz = CH.index("Fz"), CH.index("Pz"), CH.index("Cz")
    th = bp["theta"]; al = bp["alpha"]
    be = bp["beta"] if not rich else bp["lbeta"] + bp["hbeta"]
    out.append(np.array([np.log(th[fz] / al[fz]), np.log(al[pz] / be[pz])]))
    if rich:
        tot = sum(bp.values()) + 1e-12
        out += [np.log(bp[b] / tot + 1e-12) for b in bands]                      # relative powers
        psd = p[:, (f >= 1) & (f < 40)]; psd = psd / psd.sum(1, keepdims=True)
        out.append(-(psd * np.log(psd + 1e-12)).sum(1))                            # spectral entropy per ch
        out.append(np.array([np.log(th[fz]) - np.log(th[pz]), np.log(al[cz] / th[cz])]))
        lo = p[:, (f >= 0.5) & (f < 4)].mean(1)
        out.append(np.array([np.log(lo[fz] + 1e-12)]))                            # blink band on Fz
    return np.concatenate(out)


def build(win_s, overlap, rich):
    X, y, subj = [], [], []
    for rest_path in sorted(glob.glob("data/eegmat/Subject*_1.edf")):
        sid = re.search(r"Subject(\d+)_1", rest_path).group(1)
        xr, fs = load_edf(rest_path)
        xt, _ = load_edf(rest_path.replace("_1.edf", "_2.edf"))
        n = int(win_s * fs); step = n // 2 if overlap else n
        def ep(x, start_s, end_s):
            a, b = int(start_s * fs), int(end_s * fs)
            return [feats(x[:, i:i + n], fs, rich) for i in range(a, min(b, x.shape[1]) - n + 1, step)]
        base = np.mean(ep(xr, 0, 28), axis=0)
        er = [e - base for e in ep(xr, 30, 90)]
        et = [e - base for e in ep(xt, 0, 60)]
        X += er + et; y += [0] * len(er) + [1] * len(et); subj += [sid] * (len(er) + len(et))
    return np.array(X), np.array(y), np.array(subj)


def models():
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC
    yield "logreg C=0.1", make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=3000))
    yield "logreg C=0.5", make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=3000))
    yield "logreg C=2", make_pipeline(StandardScaler(), LogisticRegression(C=2.0, max_iter=3000))
    yield "LDA shrinkage", make_pipeline(StandardScaler(), LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto"))
    yield "SVM rbf C=1", make_pipeline(StandardScaler(), SVC(C=1.0, gamma="scale", probability=True))
    yield "random forest", RandomForestClassifier(n_estimators=300, min_samples_leaf=5, random_state=0, n_jobs=-1)
    yield "grad boosting", GradientBoostingClassifier(n_estimators=200, max_depth=2, learning_rate=0.05, random_state=0)
    yield "MLP 32", make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(32,), alpha=1e-2, max_iter=800, random_state=0))


def loso(clf, X, y, subj):
    from sklearn.base import clone
    from sklearn.metrics import balanced_accuracy_score, roc_auc_score
    accs, aucs, tr_accs = [], [], []
    for s in np.unique(subj):
        te = subj == s
        m = clone(clf).fit(X[~te], y[~te])
        p = m.predict_proba(X[te])[:, 1]
        accs.append(balanced_accuracy_score(y[te], p > 0.5))
        aucs.append(roc_auc_score(y[te], p))
        tr_accs.append(balanced_accuracy_score(y[~te], m.predict(X[~te])))
    return np.mean(accs), np.std(accs), np.mean(aucs), np.mean(tr_accs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--quick", action="store_true", help="4 s windows only")
    ap.add_argument("--fit-best", action="store_true", help="skip the search: fit the known winner (4 s, overlap, rich, gradient boosting) and save it")
    ap.add_argument("--invariant", action="store_true", help="with --fit-best: drop the absolute log band powers and the blink band, keep only amplitude-invariant features (relative powers, ratios, entropy, gradient)")
    a = ap.parse_args()
    if a.fit_best:
        import joblib
        from sklearn.base import clone
        X, y, subj = build(4.0, True, True)
        mask = None
        if a.invariant:
            # feats() layout: [6 bands x n_ch log power][2 ratios][6 x n_ch relative][n_ch entropy][2 gradient][1 blink]
            mask = np.ones(X.shape[1], bool); mask[:6 * len(CH)] = False; mask[-1] = False
            X = X[:, mask]
        acc, sd, auc, tr = loso(dict(models())["grad boosting"], X, y, subj)
        clf = clone(dict(models())["grad boosting"]).fit(X, y)
        os.makedirs("models", exist_ok=True)
        joblib.dump(dict(model=clf, channels=CH, epoch_s=4.0, rich=True, feature_fn="model_search.feats", feature_mask=mask,
                         loso_bal_acc=float(acc), loso_auc=float(auc), n_subjects=36,
                         config=dict(win=4.0, overlap=True, rich=True, invariant=bool(a.invariant),
                                     model="grad boosting" + (" (amplitude-invariant features)" if a.invariant else ""))), "models/readiness.joblib")
        print(f"saved models/readiness.joblib: grad boosting, rich{' invariant' if a.invariant else ''}, 4 s, {X.shape[1]} features; LOSO bal acc {acc:.3f} +/- {sd:.3f}, AUC {auc:.3f}, train {tr:.3f}")
        return
    rows = []
    wins = [4.0] if a.quick else [2.0, 4.0, 6.0]
    for win in wins:
        for overlap in (False, True):
            for rich in (False, True):
                X, y, subj = build(win, overlap, rich)
                for name, clf in models():
                    acc, sd, auc, tr = loso(clf, X, y, subj)
                    rows.append(dict(win=win, overlap=overlap, rich=rich, model=name, acc=acc, sd=sd, auc=auc, train=tr, n=len(X), nf=X.shape[1]))
                    print(f"win {win:.0f}s overlap {int(overlap)} {'rich ' if rich else 'basic'} {name:14s} "
                          f"bal acc {acc:.3f} +/- {sd:.3f}  AUC {auc:.3f}  train acc {tr:.3f}  gap {tr - acc:+.3f}  (n={len(X)}, f={X.shape[1]})", flush=True)
    rows.sort(key=lambda r: r["auc"], reverse=True)
    print("\nTOP 8 by held-out AUC")
    for r in rows[:8]:
        print(f"  {r['auc']:.3f} AUC  {r['acc']:.3f} acc  gap {r['train'] - r['acc']:+.3f}  win {r['win']:.0f}s overlap {int(r['overlap'])} {'rich' if r['rich'] else 'basic'} {r['model']}")
    best = rows[0]

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(11, 6))
    labels = [f"{r['win']:.0f}s {'ov' if r['overlap'] else ''} {'rich' if r['rich'] else 'basic'} {r['model']}" for r in rows[:20]][::-1]
    ax.barh(labels, [r["auc"] for r in rows[:20]][::-1], color="#1a7fb5")
    ax.scatter([r["acc"] for r in rows[:20]][::-1], range(20), color="k", zorder=3, label="balanced accuracy")
    ax.axvline(0.5, ls=":", color="#aaa"); ax.set_xlim(0.4, 1.0); ax.set_xlabel("held-out AUC (bar) and balanced accuracy (dot), leave-one-subject-out")
    ax.set_title("Model search, top 20 of %d configurations" % len(rows)); ax.legend(frameon=False, loc="lower right")
    for s_ in ("top", "right"):
        ax.spines[s_].set_visible(False)
    fig.tight_layout(); os.makedirs("figures", exist_ok=True); fig.savefig("figures/model_search.png", dpi=150)
    print("saved figures/model_search.png")

    if a.save:
        import joblib
        from sklearn.base import clone
        X, y, subj = build(best["win"], best["overlap"], best["rich"])
        clf = clone(dict(models())[best["model"]]).fit(X, y)
        os.makedirs("models", exist_ok=True)
        joblib.dump(dict(model=clf, channels=CH, epoch_s=best["win"], rich=best["rich"], feature_fn="model_search.feats",
                         loso_bal_acc=best["acc"], loso_auc=best["auc"], n_subjects=36, config=best), "models/readiness.joblib")
        print(f"saved models/readiness.joblib: {best['model']}, win {best['win']:.0f} s, {'rich' if best['rich'] else 'basic'} features, AUC {best['auc']:.3f}")


if __name__ == "__main__":
    main()
