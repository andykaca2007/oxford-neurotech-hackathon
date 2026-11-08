"""Figures for the mental-load model: loss over iterations, ROC, learning curve, confusion, features.

    .venv/bin/python loadmonitor/model_figures.py        -> figures/model_figures.png (+ the numbers printed)

Same data and features as readiness_model.py (baseline-relative). The loss curve trains the
logistic regression by plain gradient descent so every iteration is visible: train loss on 30
people, held-out loss on the other 6, no peeking. The rest use leave-one-subject-out.
"""
import glob
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from readiness_model import CH, epochs_of, load_edf  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import confusion_matrix, roc_curve, roc_auc_score  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

FEAT_NAMES = [f"{b} {c}" for b in ("theta", "alpha", "beta") for c in CH] + ["Fz theta/alpha", "Pz alpha/beta"]


def load_all():
    X, y, subj = [], [], []
    for rest_path in sorted(glob.glob("data/eegmat/Subject*_1.edf")):
        sid = re.search(r"Subject(\d+)_1", rest_path).group(1)
        xr, fs = load_edf(rest_path)
        xt, _ = load_edf(rest_path.replace("_1.edf", "_2.edf"))
        er_all = epochs_of(xr, fs)
        base = np.mean(er_all[:7], axis=0)
        er = [e - base for e in er_all[7:22]]
        et = [e - base for e in epochs_of(xt, fs)]
        X += er + et
        y += [0] * len(er) + [1] * len(et)
        subj += [sid] * (len(er) + len(et))
    return np.array(X), np.array(y), np.array(subj)


def gd_logreg(Xtr, ytr, Xte, yte, iters=400, lr=0.05, l2=1e-2):
    """Gradient-descent logistic regression, returns train/test log-loss per iteration."""
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
    Xtr, Xte = (Xtr - mu) / sd, (Xte - mu) / sd
    w, b = np.zeros(Xtr.shape[1]), 0.0
    tr, te = [], []
    sig = lambda z: 1 / (1 + np.exp(-z))
    for _ in range(iters):
        p = sig(Xtr @ w + b)
        g = Xtr.T @ (p - ytr) / len(ytr) + l2 * w
        w -= lr * g
        b -= lr * (p - ytr).mean()
        eps = 1e-9
        pt = sig(Xte @ w + b)
        tr.append(-np.mean(ytr * np.log(p + eps) + (1 - ytr) * np.log(1 - p + eps)))
        te.append(-np.mean(yte * np.log(pt + eps) + (1 - yte) * np.log(1 - pt + eps)))
    return np.array(tr), np.array(te)


def main():
    X, y, subj = load_all()
    subjects = np.unique(subj)
    print(f"{len(subjects)} subjects, {len(X)} epochs, {X.shape[1]} features")

    # 1. loss over iterations: 30 train subjects, 6 held out
    rng = np.random.default_rng(0)
    held = rng.choice(subjects, 6, replace=False)
    m = np.isin(subj, held)
    tr_loss, te_loss = gd_logreg(X[~m], y[~m], X[m], y[m])

    # 2. LOSO predictions for ROC + confusion
    probs = np.zeros(len(y))
    for s in subjects:
        t = subj == s
        clf = make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=2000)).fit(X[~t], y[~t])
        probs[t] = clf.predict_proba(X[t])[:, 1]
    fpr, tpr, _ = roc_curve(y, probs)
    auc = roc_auc_score(y, probs)
    cm = confusion_matrix(y, probs > 0.5)

    # 3. learning curve: held-out accuracy vs number of training subjects
    ns = [4, 8, 12, 18, 24, 30, 35]
    lc = []
    for n in ns:
        accs = []
        for rep in range(8):
            test = rng.choice(subjects, 1)[0]
            pool = [s for s in subjects if s != test]
            train = rng.choice(pool, n, replace=False)
            a_, b_ = np.isin(subj, train), subj == test
            clf = make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=2000)).fit(X[a_], y[a_])
            accs.append((clf.predict(X[b_]) == y[b_]).mean())
        lc.append((np.mean(accs), np.std(accs)))
        print(f"train on {n:2d} people: held-out accuracy {lc[-1][0]:.2f} +/- {lc[-1][1]:.2f}")

    # 4. feature weights from the full model
    full = make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=2000)).fit(X, y)
    w = full[-1].coef_[0]

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 3, figsize=(15, 8.5))
    ax = ax.ravel()
    ax[0].plot(tr_loss, color="k", label="train, 30 people")
    ax[0].plot(te_loss, color="#c0202a", label="held out, 6 people")
    ax[0].set_xlabel("iteration"); ax[0].set_ylabel("log loss"); ax[0].set_title("Training: loss over iterations"); ax[0].legend(frameon=False)
    ax[1].plot(fpr, tpr, color="k"); ax[1].plot([0, 1], [0, 1], ls=":", color="#aaa")
    ax[1].set_xlabel("false positive rate"); ax[1].set_ylabel("true positive rate"); ax[1].set_title(f"ROC, leave-one-subject-out, AUC {auc:.2f}")
    ax[2].errorbar(ns, [a for a, _ in lc], yerr=[s for _, s in lc], marker="o", color="k")
    ax[2].axhline(0.5, ls=":", color="#aaa"); ax[2].set_ylim(0.3, 1)
    ax[2].set_xlabel("people in the training set"); ax[2].set_ylabel("accuracy on a new person"); ax[2].set_title("Learning curve")
    im = ax[3].imshow(cm, cmap="Greys")
    for i in range(2):
        for j in range(2):
            ax[3].text(j, i, cm[i, j], ha="center", va="center", color="w" if cm[i, j] > cm.max() / 2 else "k", fontsize=14)
    ax[3].set_xticks([0, 1]); ax[3].set_xticklabels(["predicted rest", "predicted load"]); ax[3].set_yticks([0, 1]); ax[3].set_yticklabels(["rest", "load"])
    ax[3].set_title("Confusion matrix, held-out epochs")
    order = np.argsort(np.abs(w))[::-1][:10]
    ax[4].barh([FEAT_NAMES[i] for i in order][::-1], w[order][::-1], color=["#c0202a" if v > 0 else "#1a7fb5" for v in w[order][::-1]])
    ax[4].axvline(0, color="k", lw=0.8); ax[4].set_title("Top features (red pushes toward load)"); ax[4].set_xlabel("weight")
    h_rest = probs[y == 0]; h_load = probs[y == 1]
    ax[5].hist(h_rest, bins=25, alpha=0.7, color="#1a7fb5", label="rest epochs"); ax[5].hist(h_load, bins=25, alpha=0.7, color="#c0202a", label="load epochs")
    ax[5].axvline(0.5, color="k", ls=":"); ax[5].set_xlabel("model probability of load"); ax[5].set_title("Held-out scores by true class"); ax[5].legend(frameon=False)
    for a_ in ax:
        for s_ in ("top", "right"):
            a_.spines[s_].set_visible(False)
    fig.suptitle("Mental-load model: PhysioNet eegmat, 36 subjects, 5 channels, baseline-relative features", y=0.995)
    fig.tight_layout()
    os.makedirs("data", exist_ok=True)
    fig.savefig("figures/model_figures.png", dpi=150)
    print(f"final train loss {tr_loss[-1]:.3f}, held-out loss {te_loss[-1]:.3f}; AUC {auc:.3f}; confusion {cm.tolist()}")
    print("saved figures/model_figures.png")


if __name__ == "__main__":
    main()
