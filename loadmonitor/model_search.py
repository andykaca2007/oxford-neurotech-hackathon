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


# Processing config, saved into the model file and applied identically live. ROBUST: dry electrodes on hair give
# 50 Hz mains hum and sub-4 Hz drift that together can be 90 percent of the power; a notch, a steeper 3 Hz high-pass
# and no delta band keep the features on the bands the model is about.
FEAT_CFG = dict(lo=1.0, hi=40.0, notch=False, order=4, drop_delta=False)
ROBUST_CFG = dict(lo=4.0, hi=30.0, notch=True, order=8, drop_delta=True, median=True, car="median", burst=4.0, drop_gamma=True, asr=5.0, detrend=3)


def clean_window(x, fs, cfg):
    """Everything before the spectrum: re-reference, notch comb, band-pass, burst masking. Shared by feats() and ASR."""
    from scipy.signal import iirnotch, tf2sos
    # dead channels judged on the RAW window, per sample: flat, or ANY sample on the +/-200 mV rail (open input).
    # (Testing the mean after mean removal never fired; a channel that rails for part of a window injected a
    # 200 mV step. CRITIQUE dsp-1, dsp-2.)
    ok = (x.std(1) > 1e-6) & ~np.any(np.abs(np.abs(x) - 200000) < 1, axis=1)
    x = x - x.mean(1, keepdims=True)
    if cfg.get("detrend"):
        # polynomial detrend: fit and subtract a low-order polynomial per channel, the slow electrode drift and sweat
        # potential that an IIR high-pass only attenuates at the window edges
        t = np.linspace(-1, 1, x.shape[1])
        V = np.vander(t, int(cfg["detrend"]) + 1)
        coef, *_ = np.linalg.lstsq(V, x.T, rcond=None)
        x = x - (V @ coef).T
    if cfg.get("notch"):
        for f0 in (50.0, 100.0):
            if f0 < fs / 2:
                b, a_ = iirnotch(f0, 30.0, fs=fs)
                x = sosfiltfilt(tf2sos(b, a_), x, axis=1)
    if cfg.get("car"):
        # common reference: noise shared by all electrodes (mains through a poor ground, body drift) cancels;
        # median across channels resists one bad electrode; dead or railed channels are left out
        if ok.sum() >= 2:
            ref = np.median(x[ok], axis=0, keepdims=True) if cfg["car"] == "median" else x[ok].mean(0, keepdims=True)
            x = x - ref
    x[~ok] = 0.0          # a dead channel stays empty; before, referencing turned it into -ref, a plausible fake trace
    sos = butter(cfg.get("order", 4), [cfg["lo"], cfg["hi"]], btype="band", fs=fs, output="sos")
    x = sosfiltfilt(sos, x, axis=1)
    if cfg.get("burst"):
        # burst masking: samples whose Hilbert broadband envelope exceeds k x the window median are zeroed with a
        # short taper, so a movement spike never reaches the band powers
        from scipy.signal import hilbert as _hilbert
        env = np.abs(_hilbert(x, axis=1))
        thr = cfg["burst"] * np.median(env, axis=1, keepdims=True) + 1e-9
        bad = env > thr
        # do not flag the first and last 0.5 s: there the order-8 band-pass's own edge transient lifts the envelope, so on a
        # dry cap the mask zeroed 30 and 24 percent of the edges (5.8 percent in the middle), lab EEG under 1 percent (CRITIQUE dsp-4)
        edge = int(0.5 * fs)
        if bad.shape[1] > 4 * edge:
            bad[:, :edge] = False
            bad[:, -edge:] = False
        if bad.any():
            k = max(3, int(fs * 0.05))
            w = np.ones(k) / k
            soft = np.array([np.convolve(b.astype(float), w, mode="same") for b in bad])
            x = x * np.clip(1.0 - soft * 1.5, 0.0, 1.0)
    return x


class ASR:
    """Artefact subspace reconstruction, the simple form: learn the principal components of the wearer's clean
    resting signal; in each window, drop any component whose RMS exceeds k x its resting RMS and rebuild the window
    from the rest. Calibrated per person from the baseline, so it needs no training data."""

    def __init__(self, k=5.0):
        self.k, self.V, self.ref = k, None, None

    def fit(self, windows):
        X = np.concatenate(windows, axis=1)                      # (ch, t)
        C = np.cov(X)
        w, V = np.linalg.eigh(C)
        self.V = V
        proj = V.T @ X
        sd = proj.std(1)
        # floor: a near-zero component (a dead or flat channel in the baseline) would otherwise make every later
        # window "artefact" and ASR would delete the whole signal (CRITIQUE fatigue-1, gauge-adv1)
        self.ref = np.maximum(sd, 0.01 * float(np.median(sd)) + 1e-9)

    def __call__(self, x):
        if self.V is None:
            return x
        proj = self.V.T @ x
        bad = proj.std(1) > self.k * self.ref
        if bad.any():
            proj[bad] = 0.0
            x = self.V @ proj
        return x


def feats(x, fs, rich, cfg=None, asr=None):
    cfg = cfg or FEAT_CFG
    if cfg is FEAT_CFG or not (cfg.get("notch") or cfg.get("car") or cfg.get("burst")):
        x = x - x.mean(1, keepdims=True)
        sos = butter(cfg.get("order", 4), [cfg["lo"], cfg["hi"]], btype="band", fs=fs, output="sos")
        x = sosfiltfilt(sos, x, axis=1)
    else:
        x = clean_window(x, fs, cfg)
        if asr is not None:
            x = asr(x)
    # median-averaged Welch: the PSD is the median over 1 s segments instead of the mean, so one artefact burst inside
    # the 4 s window does not set the band power (Welch is FFT-based; median averaging is the robust estimator)
    f, p = welch(x, fs=fs, nperseg=int(fs * 1) if cfg.get("median") else int(fs * 2), noverlap=int(fs * 0.5) if cfg.get("median") else None,
                 average="median" if cfg.get("median") else "mean", axis=1)
    bands = BANDS_RICH if rich else BANDS_BASIC
    if cfg.get("drop_delta"):
        bands = {k: v for k, v in bands.items() if k != "delta"}
    if cfg.get("drop_gamma"):
        bands = {k: v for k, v in bands.items() if k != "gamma"}
    bp = {b: p[:, (f >= lo) & (f < hi)].mean(1) for b, (lo, hi) in bands.items()}
    out = [np.log(bp[b] + 1e-12) for b in bands]
    fz, pz, cz = CH.index("Fz"), CH.index("Pz"), CH.index("Cz")
    th = bp["theta"]; al = bp["alpha"]
    be = bp["beta"] if not rich else bp["lbeta"] + bp["hbeta"]
    out.append(np.array([np.log(th[fz] / al[fz]), np.log(al[pz] / be[pz])]))
    if rich:
        tot = sum(bp.values()) + 1e-12
        out += [np.log(bp[b] / tot + 1e-12) for b in bands]                      # relative powers
        psd = p[:, (f >= cfg["lo"]) & (f < cfg["hi"])]; psd = psd / psd.sum(1, keepdims=True)
        out.append(-(psd * np.log(psd + 1e-12)).sum(1))                            # spectral entropy per ch
        out.append(np.array([np.log(th[fz]) - np.log(th[pz]), np.log(al[cz] / th[cz])]))
        lo = p[:, (f >= 0.5) & (f < 4)].mean(1)
        out.append(np.array([np.log(lo[fz] + 1e-12)]))                            # blink band on Fz
    return np.concatenate(out)


def build(win_s, overlap, rich, cfg=None):
    X, y, subj = [], [], []
    for rest_path in sorted(glob.glob("data/eegmat/Subject*_1.edf")):
        sid = re.search(r"Subject(\d+)_1", rest_path).group(1)
        xr, fs = load_edf(rest_path)
        xt, _ = load_edf(rest_path.replace("_1.edf", "_2.edf"))
        n = int(win_s * fs); step = n // 2 if overlap else n
        asr = None
        if cfg and cfg.get("asr"):
            asr = ASR(cfg["asr"])
            asr.fit([clean_window(xr[:, i:i + n], fs, cfg) for i in range(0, int(28 * fs) - n + 1, step)])

        def ep(x, start_s, end_s):
            a, b = int(start_s * fs), int(end_s * fs)
            return [feats(x[:, i:i + n], fs, rich, cfg, asr) for i in range(a, min(b, x.shape[1]) - n + 1, step)]
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
    ap.add_argument("--robust", action="store_true", help="with --fit-best: 50 Hz notch, 3 Hz high-pass, no delta band (ROBUST_CFG), for dry electrodes")
    ap.add_argument("--invariant", action="store_true", help="with --fit-best: drop the absolute log band powers and the blink band, keep only amplitude-invariant features (relative powers, ratios, entropy, gradient)")
    ap.add_argument("--channels", default=None, help="with --fit-best: comma-separated channels, e.g. Fz,C3,Cz,Pz,O1 (the live model); default: readiness_model.CH (8)")
    ap.add_argument("--out", default="models/readiness_candidate.joblib", help="with --fit-best: where to save; the live gauge reads models/readiness.joblib, so pass that explicitly to replace it")
    ap.add_argument("--skip-loso", action="store_true", help="with --fit-best: fit only, no leave-one-subject-out scoring (for reproducibility checks)")
    a = ap.parse_args()
    if a.fit_best:
        import joblib
        from sklearn.base import clone
        import readiness_model as _rm
        if a.channels:
            _rm.CH[:] = [c.strip() for c in a.channels.split(",") if c.strip()]    # CH here is the same list object
        cfg = ROBUST_CFG if a.robust else FEAT_CFG
        X, y, subj = build(4.0, True, True, cfg)
        mask = None
        if a.invariant:
            # feats() layout: [nb bands x n_ch log power][2 ratios][nb x n_ch relative][n_ch entropy][2 gradient][1 blink]
            nb = 6 - int(bool(cfg.get("drop_delta"))) - int(bool(cfg.get("drop_gamma")))
            mask = np.ones(X.shape[1], bool); mask[:nb * len(CH)] = False; mask[-1] = False
            X = X[:, mask]
        if a.skip_loso:
            acc = sd = auc = tr = float("nan")
        else:
            acc, sd, auc, tr = loso(dict(models())["grad boosting"], X, y, subj)
        clf = clone(dict(models())["grad boosting"]).fit(X, y)
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        joblib.dump(dict(model=clf, channels=list(CH), epoch_s=4.0, rich=True, feature_fn="model_search.feats", feature_mask=mask, feat_cfg=cfg,
                         loso_bal_acc=float(acc), loso_auc=float(auc), n_subjects=36,
                         rebuild=" ".join(["loadmonitor/model_search.py"] + sys.argv[1:]),
                         config=dict(win=4.0, overlap=True, rich=True, invariant=bool(a.invariant), robust=bool(a.robust),
                                     model="grad boosting" + (" invariant" if a.invariant else "") + (" robust" if a.robust else "") + (f" {len(CH)}ch" if a.channels else ""))), a.out)
        print(f"saved {a.out}: grad boosting, channels {' '.join(CH)}, rich{' invariant' if a.invariant else ''}{' robust' if a.robust else ''}, 4 s, {X.shape[1]} features; LOSO bal acc {acc:.3f} +/- {sd:.3f}, AUC {auc:.3f}, train {tr:.3f}")
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
