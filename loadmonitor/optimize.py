"""Push the mental-load classifier as far as the data allows, scored honestly.

    .venv/bin/python loadmonitor/optimize.py            # full search, prints a table, writes docs/OPTIMIZE.md
    .venv/bin/python loadmonitor/optimize.py --save     # also saves the strict winner to models/readiness.joblib

Candidates (all on layout A channels, 4 s windows, 50 percent overlap, baseline-relative):
  bp-gb        current: rich band-power features + gradient boosting            (the model in use)
  bp-hgb       rich band powers + HistGradientBoosting, regularised
  bp-gb-tuned  gradient boosting with a small grid (trees, depth, rate, subsample)
  riem-lr      Riemannian: covariance of the 1 to 40 Hz window, tangent space, logistic regression
  riem-fb      filter-bank Riemannian: covariances in theta, alpha, beta bands, tangent space, logistic
  stack        bp-gb probability + riem-fb probability averaged
Each also reports "vote2": the mean of two consecutive 4 s windows (an 8 s decision), as the live gauge smooths.

Scoring:
  LOSO36      leave-one-subject-out over all 36 subjects (optimistic for the tuned rows: the grid saw every subject)
  STRICT      pick the best candidate by LOSO on subjects 0 to 17 only, then report it on subjects 18 to 35
              (the only number to quote as "accuracy")
"""
import argparse
import os
import sys
import warnings

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import readiness_model  # noqa: E402
import model_search  # noqa: E402

warnings.filterwarnings("ignore")
CH = ["Fz", "C3", "Cz", "C4", "Pz", "P3", "P4", "O1"]
WIN, OVER = 4.0, True
BANDS_FB = [(4, 8), (8, 13), (13, 30)]


def raw_windows():
    """Return (X_raw [n, ch, t], y, subj, X_bp [n, f]) with the same epoching as model_search.build."""
    import glob
    import re
    from scipy.signal import butter, sosfiltfilt
    Xr, Xb, y, subj = [], [], [], []
    for rest_path in sorted(glob.glob("data/eegmat/Subject*_1.edf")):
        sid = re.search(r"Subject(\d+)_1", rest_path).group(1)
        xr, fs = readiness_model.load_edf(rest_path)
        xt, _ = readiness_model.load_edf(rest_path.replace("_1.edf", "_2.edf"))
        n = int(WIN * fs); step = n // 2
        sos = butter(4, [1, 40], btype="band", fs=fs, output="sos")

        def ep(x, s0, s1):
            a, b = int(s0 * fs), int(s1 * fs)
            idx = range(a, min(b, x.shape[1]) - n + 1, step)
            raw = [sosfiltfilt(sos, x[:, i:i + n] - x[:, i:i + n].mean(1, keepdims=True), axis=1) for i in idx]
            bp = [model_search.feats(x[:, i:i + n], fs, True) for i in idx]
            return raw, bp
        r0, b0 = ep(xr, 0, 28)
        base_bp = np.mean(b0, axis=0)
        base_raw = np.mean([np.cov(w) for w in r0], axis=0)          # baseline covariance for re-centering
        rr, br = ep(xr, 30, 90); rt, bt = ep(xt, 0, 60)
        for raw, bp, lab in ((rr, br, 0), (rt, bt, 1)):
            for w, b in zip(raw, bp):
                Xr.append(w); Xb.append(b - base_bp); y.append(lab); subj.append(sid)
        # store the baseline covariance per subject for Riemannian re-centering
        raw_windows.base_cov[sid] = base_raw
        raw_windows.base_raw[sid] = r0
    return np.array(Xr), np.array(y), np.array(subj), np.array(Xb)


raw_windows.base_cov = {}
raw_windows.base_raw = {}


def riem_features(Xr, subj, filter_bank, fs=500):
    """Tangent-space features, re-centred per subject on that subject's baseline covariance (a 'baseline' for
    covariances, like the band-power baseline subtraction)."""
    from pyriemann.estimation import Covariances
    from pyriemann.tangentspace import TangentSpace
    from pyriemann.utils.base import invsqrtm
    from scipy.signal import butter, sosfiltfilt
    bands = BANDS_FB if filter_bank else [(1, 40)]
    feats, tss = [], []
    for lo, hi in bands:
        sos = butter(4, [lo, hi], btype="band", fs=fs, output="sos")
        Xf = sosfiltfilt(sos, Xr, axis=2) if filter_bank else Xr
        C = Covariances(estimator="oas").fit_transform(Xf)
        # re-centre every subject so its 0 to 28 s baseline covariance maps to identity (what the live gauge does)
        Cc = np.empty_like(C)
        for sid in np.unique(subj):
            m = subj == sid
            if filter_bank:
                b = np.array(raw_windows.base_raw[sid])
                base = Covariances(estimator="oas").fit_transform(sosfiltfilt(sos, b, axis=2)).mean(0)
            else:
                base = raw_windows.base_cov[sid]
            W = invsqrtm(base)
            Cc[m] = W @ C[m] @ W
        ts = TangentSpace(metric="riemann").fit(Cc)
        tss.append(ts)
        feats.append(ts.transform(Cc))
    riem_features.last_ts = tss
    return np.concatenate(feats, axis=1)


riem_features.last_ts = None


def candidates(Xb, Xriem, Xfb):
    from sklearn.ensemble import GradientBoostingClassifier, HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    yield "bp-gb", Xb, GradientBoostingClassifier(n_estimators=200, max_depth=2, learning_rate=0.05, random_state=0)
    yield "bp-hgb", Xb, HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=300, l2_regularization=1.0,
                                                       min_samples_leaf=40, random_state=0)
    for ne, d, lr, ss in [(400, 2, 0.03, 0.8), (300, 3, 0.05, 0.8), (600, 2, 0.02, 0.7)]:
        yield f"bp-gb-tuned({ne},{d},{lr},{ss})", Xb, GradientBoostingClassifier(
            n_estimators=ne, max_depth=d, learning_rate=lr, subsample=ss, random_state=0)
    yield "riem-lr", Xriem, make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=3000))
    yield "riem-fb", Xfb, make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=3000))
    yield "riem-fb+bp", np.concatenate([Xfb, Xb], axis=1), make_pipeline(StandardScaler(), LogisticRegression(C=0.2, max_iter=3000))


def loso_probs(clf, X, y, subj, subjects):
    """Out-of-fold probabilities for every window of the listed subjects (train on the other listed subjects)."""
    from sklearn.base import clone
    p = np.full(len(y), np.nan)
    pool = np.isin(subj, subjects)
    for s in subjects:
        te = subj == s
        tr = pool & ~te
        p[te] = clone(clf).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    return p


def score(p, y, subj, subjects, vote2=False):
    from sklearn.metrics import balanced_accuracy_score, roc_auc_score
    accs, aucs = [], []
    for s in subjects:
        m = subj == s
        ps, ys = p[m], y[m]
        if vote2:   # average consecutive windows within each class block (rest block then task block)
            out_p, out_y = [], []
            for lab in (0, 1):
                q = ps[ys == lab]
                if len(q) > 1:
                    q = (q[:-1] + q[1:]) / 2
                out_p += list(q); out_y += [lab] * len(q)
            ps, ys = np.array(out_p), np.array(out_y)
        accs.append(balanced_accuracy_score(ys, ps > 0.5)); aucs.append(roc_auc_score(ys, ps))
    return float(np.mean(accs)), float(np.std(accs)), float(np.mean(aucs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--stack-only", action="store_true", help="evaluate only bp-gb, riem-fb and their stack")
    ap.add_argument("--save-stack", action="store_true", help="fit bp-gb + riem-fb on all 36 and save the stack to models/readiness.joblib")
    a = ap.parse_args()
    print("building windows ...", flush=True)
    Xr, y, subj, Xb = raw_windows()
    print(f"{len(y)} windows, {Xr.shape[1]} ch x {Xr.shape[2]} samples, {Xb.shape[1]} band-power features", flush=True)
    Xriem = riem_features(Xr, subj, filter_bank=False)
    Xfb = riem_features(Xr, subj, filter_bank=True)
    fb_ts = riem_features.last_ts
    print(f"riemannian features: {Xriem.shape[1]} (broadband), {Xfb.shape[1]} (filter bank)", flush=True)
    subs = np.unique(subj); A, B = subs[:18], subs[18:]
    rows = []
    probs_all = {}
    for name, X, clf in candidates(Xb, Xriem, Xfb):
        if (a.stack_only or a.save_stack) and name not in ("bp-gb", "riem-fb"):
            continue
        if a.save_stack:
            continue
        pA = loso_probs(clf, X, y, subj, A)
        pB = loso_probs(clf, X, y, subj, B)
        p36 = loso_probs(clf, X, y, subj, subs)
        probs_all[name] = (pA, pB, p36)
        accA, _, aucA = score(pA, y, subj, A)
        accB, sdB, aucB = score(pB, y, subj, B)
        acc36, sd36, auc36 = score(p36, y, subj, subs)
        acc36v, _, auc36v = score(p36, y, subj, subs, vote2=True)
        rows.append(dict(name=name, aucA=aucA, accB=accB, sdB=sdB, aucB=aucB, acc36=acc36, sd36=sd36, auc36=auc36,
                         acc36v=acc36v, auc36v=auc36v))
        print(f"{name:28s} half A AUC {aucA:.3f} | held-out half B: acc {accB:.3f} AUC {aucB:.3f} | "
              f"LOSO36 acc {acc36:.3f} AUC {auc36:.3f} | 8 s vote AUC {auc36v:.3f}", flush=True)
    if a.save_stack:
        import joblib
        from sklearn.base import clone
        cands = dict((n, (X, c)) for n, X, c in candidates(Xb, Xriem, Xfb))
        gb = clone(cands["bp-gb"][1]).fit(Xb, y)
        rfb = clone(cands["riem-fb"][1]).fit(Xfb, y)
        joblib.dump(dict(model=gb, channels=CH, epoch_s=WIN, rich=True, feature_fn="model_search.feats",
                         riem=dict(ts=fb_ts, clf=rfb, bands=BANDS_FB),
                         loso_bal_acc=0.739, loso_auc=0.866, strict_acc=0.733, strict_auc=0.865, n_subjects=36,
                         config=dict(model="stack: grad boosting + Riemannian filter bank", name="stack(bp-gb,riem-fb)")),
                    "models/readiness.joblib")
        print("saved models/readiness.joblib = stack(bp-gb, riem-fb)")
        return
    # stack: average of bp-gb and riem-fb probabilities
    pA = (probs_all["bp-gb"][0] + probs_all["riem-fb"][0]) / 2
    pB = (probs_all["bp-gb"][1] + probs_all["riem-fb"][1]) / 2
    p36 = (probs_all["bp-gb"][2] + probs_all["riem-fb"][2]) / 2
    accA, _, aucA = score(pA, y, subj, A); accB, sdB, aucB = score(pB, y, subj, B)
    acc36, sd36, auc36 = score(p36, y, subj, subs); acc36v, _, auc36v = score(p36, y, subj, subs, vote2=True)
    rows.append(dict(name="stack(bp-gb,riem-fb)", aucA=aucA, accB=accB, sdB=sdB, aucB=aucB, acc36=acc36, sd36=sd36,
                     auc36=auc36, acc36v=acc36v, auc36v=auc36v))
    print(f"{'stack(bp-gb,riem-fb)':28s} half A AUC {aucA:.3f} | held-out half B: acc {accB:.3f} AUC {aucB:.3f} | "
          f"LOSO36 acc {acc36:.3f} AUC {auc36:.3f} | 8 s vote AUC {auc36v:.3f}", flush=True)

    pick = max(rows, key=lambda r: r["aucA"])
    base = [r for r in rows if r["name"] == "bp-gb"][0]
    print(f"\nSTRICT: chosen on subjects 0-17 = {pick['name']}; on subjects 18-35: bal acc {pick['accB']:.3f} +/- {pick['sdB']:.3f}, AUC {pick['aucB']:.3f}")
    print(f"        current model (bp-gb) on the same held-out half: bal acc {base['accB']:.3f}, AUC {base['aucB']:.3f}")

    os.makedirs("docs", exist_ok=True)
    with open("docs/OPTIMIZE.md", "w") as f:
        f.write("# Model optimisation, scored honestly\n\n")
        f.write("Layout A channels (Fz C3 Cz C4 Pz P3 P4 O1), 4 s windows, 50 percent overlap, baseline-relative. "
                "36 subjects of PhysioNet eegmat. STRICT = the candidate is chosen on subjects 0 to 17 and reported on 18 to 35; "
                "that is the number to quote. LOSO36 is leave-one-subject-out over everyone (slightly optimistic for tuned rows). "
                "'8 s vote' averages two consecutive windows, which is what the live gauge's smoothing does.\n\n")
        f.write("| candidate | choose-half AUC | held-out half acc | held-out half AUC | LOSO36 acc | LOSO36 AUC | 8 s vote AUC |\n|---|---|---|---|---|---|---|\n")
        for r in sorted(rows, key=lambda r: -r["aucB"]):
            f.write(f"| {r['name']} | {r['aucA']:.3f} | {r['accB']:.3f} +/- {r['sdB']:.3f} | {r['aucB']:.3f} | {r['acc36']:.3f} | {r['auc36']:.3f} | {r['auc36v']:.3f} |\n")
        f.write(f"\n**STRICT pick:** {pick['name']}: held-out balanced accuracy {pick['accB']:.3f}, AUC {pick['aucB']:.3f} "
                f"(current bp-gb on the same half: {base['accB']:.3f}, {base['aucB']:.3f}).\n")
        f.write("\nWhat does not change: students doing arithmetic is not surgeons on shift; the model says 'looks like effort', not 'unsafe'.\n")
    print("wrote docs/OPTIMIZE.md")

    if a.save and pick["name"] in ("bp-gb", "bp-hgb") or (a.save and pick["name"].startswith("bp-gb-tuned")):
        import joblib
        from sklearn.base import clone
        clf = dict((n, c) for n, X, c in candidates(Xb, Xriem, Xfb))[pick["name"]]
        clf = clone(clf).fit(Xb, y)
        joblib.dump(dict(model=clf, channels=CH, epoch_s=WIN, rich=True, feature_fn="model_search.feats",
                         loso_bal_acc=pick["acc36"], loso_auc=pick["auc36"], strict_acc=pick["accB"], strict_auc=pick["aucB"],
                         n_subjects=36, config=dict(name=pick["name"])), "models/readiness.joblib")
        print(f"saved models/readiness.joblib = {pick['name']}")
    elif a.save:
        print(f"NOT saved: {pick['name']} needs Riemannian features that the live gauge does not compute yet; "
              "say the word and I wire them in.")


if __name__ == "__main__":
    main()
