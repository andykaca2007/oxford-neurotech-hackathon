"""Andy's load model (v2): a lighter cleaning chain, a simple classifier, and a personal-calibration test.

Same data (PhysioNet eegmat, 36 people, rest vs silent serial subtraction), same 8 channels, same
44 amplitude-invariant features, same baseline-relative design as the live model
(`model_search.py --fit-best --robust --invariant`). What changes, and why:

  cleaning    detrend, 50/100 Hz notch, 3 to 30 Hz band-pass (order 4). Nothing else.
              No median common reference: it subtracts whatever most electrodes share, and alpha and theta
              (the load and fatigue signals) are shared by most electrodes, so it cancels them.
              No burst masking: it blanks high-amplitude alpha and theta bursts, which is what drowsiness
              looks like. No artefact subspace reconstruction. Bad windows are skipped instead of
              repaired (compare_models.py --max-uv; the live gauge holds on noisy channels).
  classifier  logistic regression (C=0.1) unless gradient boosting wins on the choosing half of the
              subjects by more than 0.01 AUC: simpler, smoother probabilities, less to overfit.
  scoring     chosen on subjects 0-17, reported on 18-35 (and leave-one-subject-out over all 36).
  personal    tests whether ~30 s of the wearer's own rest + ~30 s of their own task, on top of the public
              model, beats the public model alone. The public data is eyes closed in a dark room (rest)
              and silent sums; live use is eyes open at a screen, so the wearer's own data should matter.

    .venv/bin/python loadmonitor/andy_model.py           # evaluate, print the table, save models/andy_load.joblib
    .venv/bin/python loadmonitor/andy_model.py --quick   # logistic only (skips boosting), a minute or two

Live, side by side with the current model:
    .venv/bin/python loadmonitor/load_gauge.py --lsl --web --model models/andy_load.joblib
On a recorded session (both models, a personal model, rest-block fatigue markers):
    .venv/bin/python loadmonitor/compare_models.py --raw <..._raw_*.csv> --markers <..._gauge_markers.csv>
"""
import argparse
import glob
import os
import re
import sys
import warnings

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from readiness_model import CH, load_edf  # noqa: E402
import model_search as ms  # noqa: E402

warnings.filterwarnings("ignore")

# The light chain. model_search.feats() runs clean_window() when notch is on; car and burst off; no asr key.
LIGHT_CFG = dict(lo=3.0, hi=30.0, notch=True, order=4, drop_delta=True, drop_gamma=True, median=True,
                 detrend=3, car=False, burst=False)
WIN_S = 4.0


def invariant_mask(n_feat, n_ch, cfg):
    """Same selection as model_search.py --invariant: drop the absolute log band powers and the blink band."""
    nb = 6 - int(bool(cfg.get("drop_delta"))) - int(bool(cfg.get("drop_gamma")))
    mask = np.ones(n_feat, bool)
    mask[:nb * n_ch] = False
    mask[-1] = False
    return mask


def build(cfg, win_s=WIN_S):
    """Like model_search.build (4 s windows, 50 percent overlap, features minus the mean of the first 28 s of
    rest), plus each window's start time in its file, for the personal-calibration split."""
    X, y, subj, t0 = [], [], [], []
    for rest_path in sorted(glob.glob("data/eegmat/Subject*_1.edf")):
        sid = re.search(r"Subject(\d+)_1", rest_path).group(1)
        xr, fs = load_edf(rest_path)
        xt, _ = load_edf(rest_path.replace("_1.edf", "_2.edf"))
        n = int(win_s * fs)
        step = n // 2
        asr = None
        if cfg.get("asr"):
            asr = ms.ASR(cfg["asr"])
            asr.fit([ms.clean_window(xr[:, i:i + n], fs, cfg) for i in range(0, int(28 * fs) - n + 1, step)])

        def ep(x, a_s, b_s):
            a, b = int(a_s * fs), min(int(b_s * fs), x.shape[1])
            starts = list(range(a, b - n + 1, step))
            return [ms.feats(x[:, i:i + n], fs, True, cfg, asr) for i in starts], [i / fs for i in starts]

        fb, _ = ep(xr, 0, 28)
        base = np.mean(fb, axis=0)
        fr, tr = ep(xr, 30, 90)
        ft, tt = ep(xt, 0, 60)
        X += [f - base for f in fr + ft]
        y += [0] * len(fr) + [1] * len(ft)
        subj += [sid] * (len(fr) + len(ft))
        t0 += tr + tt
    X = np.nan_to_num(np.array(X), nan=0.0, posinf=0.0, neginf=0.0)
    return X, np.array(y), np.array(subj), np.array(t0)


def logreg(C=0.1):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=5000))


def boosting():
    from sklearn.ensemble import GradientBoostingClassifier
    return GradientBoostingClassifier(n_estimators=200, max_depth=2, learning_rate=0.05, random_state=0)


def loso(make, X, y, subj, pool):
    """Leave one subject out, training only on subjects in `pool`. Returns {subject: (balanced acc, AUC)}."""
    from sklearn.metrics import balanced_accuracy_score, roc_auc_score
    out = {}
    for s in pool:
        tr = np.isin(subj, pool) & (subj != s)
        te = subj == s
        m = make().fit(X[tr], y[tr])
        p = m.predict_proba(X[te])[:, 1]
        out[s] = (balanced_accuracy_score(y[te], p > 0.5), roc_auc_score(y[te], p))
    return out


def personal_eval(make_public, X, y, subj, t0):
    """Per held-out subject: public model (trained on the other 35) vs a personal model trained on the subject's
    first ~32 s of rest and ~32 s of task vs the average of the two, all scored on the subject's later windows.
    Rest windows start 30-58 s (calibration) and 62-86 s (test); task windows 0-28 s and 32-56 s: a 4 s gap, so
    no test window shares a sample with a calibration window."""
    from sklearn.metrics import roc_auc_score
    res = {"public": [], "personal": [], "hybrid": []}
    for s in np.unique(subj):
        te = subj == s
        pub = make_public().fit(X[~te], y[~te])
        Xs, ys, ts = X[te], y[te], t0[te]
        cal = ((ys == 0) & (ts < 60)) | ((ys == 1) & (ts < 30))
        test = ((ys == 0) & (ts >= 62)) | ((ys == 1) & (ts >= 32))
        per = logreg(0.1).fit(Xs[cal], ys[cal])
        pp = pub.predict_proba(Xs[test])[:, 1]
        pq = per.predict_proba(Xs[test])[:, 1]
        for k, p in (("public", pp), ("personal", pq), ("hybrid", 0.5 * (pp + pq))):
            res[k].append(roc_auc_score(ys[test], p))
    return {k: np.array(v) for k, v in res.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="logistic only, skip gradient boosting")
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args()

    if not glob.glob("data/eegmat/Subject*_1.edf"):
        sys.exit("no data in data/eegmat (PhysioNet eegmat 1.0.0, 36 subjects x 2 EDF files)")
    X, y, subj, t0 = build(LIGHT_CFG)
    mask = invariant_mask(X.shape[1], len(CH), LIGHT_CFG)
    X = X[:, mask]
    subjects = np.unique(subj)
    choose, report = subjects[:18], subjects[18:]
    print(f"light chain (detrend, notch, 3-30 Hz, no reference, no masking): {len(subjects)} subjects, "
          f"{len(X)} windows, {X.shape[1]} invariant features")

    cands = {"logistic C=0.1": logreg}
    if not a.quick:
        cands["grad boosting"] = boosting
    pick = {}
    for name, make in cands.items():
        r = loso(make, X, y, subj, choose)
        pick[name] = np.mean([v[1] for v in r.values()])
        print(f"  choosing half (subjects 0-17, LOSO inside the half): {name:15s} AUC {pick[name]:.3f}")
    best = "logistic C=0.1"
    if "grad boosting" in pick and pick["grad boosting"] > pick["logistic C=0.1"] + 0.01:
        best = "grad boosting"
    make = cands[best]
    r = loso(make, X, y, subj, subjects)
    acc_all = np.mean([v[0] for v in r.values()])
    auc_all = np.mean([v[1] for v in r.values()])
    acc_rep = np.mean([r[s][0] for s in report])
    auc_rep = np.mean([r[s][1] for s in report])
    print(f"picked {best}: reporting half (subjects 18-35) balanced acc {acc_rep:.3f}, AUC {auc_rep:.3f}; "
          f"LOSO over all 36: balanced acc {acc_all:.3f}, AUC {auc_all:.3f}")

    pe = personal_eval(make, X, y, subj, t0)
    print("personal calibration (later windows of each held-out subject; ~32 s rest + ~32 s task to calibrate):")
    for k in ("public", "personal", "hybrid"):
        print(f"  {k:8s} AUC {pe[k].mean():.3f} +/- {pe[k].std():.3f}   (subjects 18-35: {pe[k][18:].mean():.3f})")

    if not a.no_save:
        import joblib
        clf = make().fit(X, y)
        os.makedirs("models", exist_ok=True)
        joblib.dump(dict(model=clf, channels=list(CH), epoch_s=WIN_S, rich=True, feature_fn="model_search.feats",
                         feature_mask=mask, feat_cfg=dict(LIGHT_CFG), loso_bal_acc=float(acc_all), loso_auc=float(auc_all),
                         n_subjects=len(subjects),
                         config=dict(win=WIN_S, overlap=True, rich=True, invariant=True, model=f"andy v2: {best}, light chain"),
                         personal_auc={k: float(v.mean()) for k, v in pe.items()}), "models/andy_load.joblib")
        print("saved models/andy_load.joblib (load_gauge.py --model models/andy_load.joblib)")


if __name__ == "__main__":
    main()
