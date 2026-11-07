"""Mental-load model: rest vs mental arithmetic from EEG band powers, held-out subjects.

Dataset: Zyma et al. 2019, "EEG during mental arithmetic tasks", PhysioNet eegmat 1.0.0.
36 subjects, 23 channels (10-20), 500 Hz. Subject_1 = 3 min rest (eyes closed is NOT it: it is
quiet rest), Subject_2 = 1 min of serial subtraction. Credited; data in data/eegmat.

We use only channels our headset has alive: Fz, C3, Cz, C4, Pz (the Core-8 montage minus the
dead occipital ones). Features per 4 s epoch: log band power theta 4-8, alpha 8-13, beta 13-30
per channel, plus Fz theta/alpha and Pz alpha/beta ratios. Classifier: logistic regression.
Evaluation: leave-one-subject-out, epoch-level balanced accuracy and AUC. Rest epochs are
subsampled to 1 min per subject so the classes are balanced.

    .venv/bin/python unicorn/readiness_model.py            # prints LOSO results, saves models/readiness.joblib
"""
import glob
import os
import re
import sys

import numpy as np
import pyedflib
from scipy.signal import butter, sosfiltfilt, welch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

CH = ["Fz", "C3", "Cz", "C4", "Pz"]
BANDS = {"theta": (4, 8), "alpha": (8, 13), "beta": (13, 30)}
EPOCH_S = 4.0
BASELINE = "--raw" not in sys.argv   # default: features relative to the person's own 28 s rest baseline


def features(x, fs):
    """x: (n_ch, n_s) in the CH order. Returns a 1-D feature vector (same code used live)."""
    sos = butter(4, [1, 40], btype="band", fs=fs, output="sos")
    x = sosfiltfilt(sos, x - x.mean(1, keepdims=True), axis=1)
    f, p = welch(x, fs=fs, nperseg=int(fs * 2), axis=1)
    bp = {b: p[:, (f >= lo) & (f < hi)].mean(1) for b, (lo, hi) in BANDS.items()}
    feats = [np.log(bp[b] + 1e-12) for b in BANDS]           # 3 x 5
    fz, pz = CH.index("Fz"), CH.index("Pz")
    feats.append(np.array([np.log(bp["theta"][fz] / bp["alpha"][fz]), np.log(bp["alpha"][pz] / bp["beta"][pz])]))
    return np.concatenate(feats)


def load_edf(path):
    f = pyedflib.EdfReader(path)
    labels = [l.replace("EEG ", "").strip() for l in f.getSignalLabels()]
    fs = f.getSampleFrequency(0)
    idx = [labels.index(c) for c in CH]
    x = np.array([f.readSignal(i) for i in idx])
    f.close()
    return x, fs


def epochs_of(x, fs, max_s=None):
    n = int(EPOCH_S * fs)
    total = x.shape[1] if max_s is None else min(x.shape[1], int(max_s * fs))
    return [features(x[:, i:i + n], fs) for i in range(0, total - n + 1, n)]


def main():
    files = sorted(glob.glob("data/eegmat/Subject*_1.edf"))
    if not files:
        sys.exit("no data in data/eegmat")
    X, y, subj = [], [], []
    for rest_path in files:
        sid = re.search(r"Subject(\d+)_1", rest_path).group(1)
        task_path = rest_path.replace("_1.edf", "_2.edf")
        xr, fs = load_edf(rest_path)
        xt, _ = load_edf(task_path)
        er_all = epochs_of(xr, fs)          # 3 min rest: first 30 s = the person's own baseline
        base = np.mean(er_all[:7], axis=0)   # 7 epochs x 4 s = 28 s of baseline
        er = er_all[7:7 + 15]                # the next 60 s of rest
        et = epochs_of(xt, fs)
        if BASELINE:
            er = [e - base for e in er]
            et = [e - base for e in et]
        X += er + et
        y += [0] * len(er) + [1] * len(et)
        subj += [sid] * (len(er) + len(et))
    X, y, subj = np.array(X), np.array(y), np.array(subj)
    print(("BASELINE-RELATIVE features" if BASELINE else "RAW features") + f": {len(files)} subjects, {len(X)} epochs of {EPOCH_S:.0f} s, {X.shape[1]} features, channels {CH}")

    accs, aucs, probs = [], [], np.zeros(len(y))
    for s in np.unique(subj):
        tr, te = subj != s, subj == s
        clf = make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=2000))
        clf.fit(X[tr], y[tr])
        p = clf.predict_proba(X[te])[:, 1]
        probs[te] = p
        accs.append(balanced_accuracy_score(y[te], p > 0.5))
        aucs.append(roc_auc_score(y[te], p) if len(np.unique(y[te])) > 1 else np.nan)
    print(f"leave-one-subject-out: balanced accuracy {np.mean(accs):.3f} +/- {np.std(accs):.3f}, "
          f"AUC {np.nanmean(aucs):.3f}, chance 0.5")
    print(f"pooled held-out AUC {roc_auc_score(y, probs):.3f}")

    clf = make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=2000)).fit(X, y)
    os.makedirs("models", exist_ok=True)
    import joblib
    joblib.dump(dict(model=clf, channels=CH, bands=BANDS, epoch_s=EPOCH_S, loso_bal_acc=float(np.mean(accs)),
                     loso_auc=float(np.nanmean(aucs)), n_subjects=len(files)), "models/readiness.joblib")
    print("saved models/readiness.joblib")


if __name__ == "__main__":
    main()
