"""Interleaved personal calibration: the one implementation used by the live gauge and by the tests.

The gauge collects feature windows (already baseline-relative) into blocks 0..n-1, rest on even blocks and silent
subtraction on odd blocks. leave_one_pair_out() trains a shrinkage LDA on all pairs but one, scores the held-out pair,
and repeats for every pair. The mean held-out AUC decides whether the personal model is used (bar in load_gauge.py,
CAL_MIN_AUC); the held-out rest scores become the rest anchor for the load mapping.

tests/calib_null.py runs this same function on recordings with no real alternation (the null) and on lab data
(rest-only null, and rest/arithmetic positive control).
"""
import numpy as np


def make_lda():
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return make_pipeline(StandardScaler(), LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto"))


def leave_one_pair_out(blocks, n_blocks):
    """blocks: {block index: list or array of feature vectors}. Returns dict(auc, folds, oof_rest).

    auc is the mean over held-out pairs (nan if no pair could be scored); folds lists each pair's AUC; oof_rest holds the
    held-out decision values of the rest windows, used as the rest anchor."""
    from sklearn.metrics import roc_auc_score
    folds, oof_rest = [], []
    for hp in range(n_blocks // 2):                            # hold out one rest block and the task block after it
        tr = [b for b in range(n_blocks) if b // 2 != hp and b in blocks and len(blocks[b])]
        te = [b for b in (2 * hp, 2 * hp + 1) if b in blocks and len(blocks[b])]
        if len(te) < 2 or len({b % 2 for b in tr}) < 2:
            continue
        Xtr = np.vstack([np.asarray(blocks[b]) for b in tr]); ytr = np.concatenate([[b % 2] * len(blocks[b]) for b in tr])
        Xte = np.vstack([np.asarray(blocks[b]) for b in te]); yte = np.concatenate([[b % 2] * len(blocks[b]) for b in te])
        m = make_lda().fit(Xtr, ytr)
        folds.append(float(roc_auc_score(yte, m.predict_proba(Xte)[:, 1])))
        oof_rest.extend(m.decision_function(Xte[yte == 0]).tolist())
    return dict(auc=float(np.mean(folds)) if folds else float("nan"), folds=folds, oof_rest=oof_rest)


def binomial_upper(k, n, conf=0.95):
    """Exact one-sided upper confidence bound on a rate after k successes in n independent trials."""
    from scipy.stats import beta
    return 1.0 if k >= n else float(beta.ppf(conf, k + 1, n - k))
