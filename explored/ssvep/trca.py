"""SSVEP decoders: CCA (no calibration) and ensemble TRCA (per-person calibration).

TRCA = task-related component analysis, Nakanishi et al. 2018, IEEE TBME 65(1):104.
Written during the Oxford Neurotech Hackathon, 7 Nov 2026, from the paper's equations.

Shapes: X is (n_trials, n_channels, n_samples). y is (n_trials,) class index.

    cca = CCA(freqs, fs, n_harm=2);            cca.predict(X) -> labels, scores
    trca = TRCA().fit(X_train, y_train);       trca.predict(X) -> labels, scores
"""
import numpy as np


class CCA:
    """Canonical correlation against sine/cosine references. Needs no training data."""

    def __init__(self, freqs, fs, n_harm=2):
        self.freqs = list(freqs)
        self.fs = fs
        self.n_harm = n_harm

    def _refs(self, n):
        t = np.arange(n) / self.fs
        out = []
        for f in self.freqs:
            cols = []
            for h in range(1, self.n_harm + 1):
                cols += [np.sin(2 * np.pi * h * f * t), np.cos(2 * np.pi * h * f * t)]
            out.append(np.column_stack(cols))
        return out

    @staticmethod
    def _cca_max(X, Y):
        X = X - X.mean(0)
        Y = Y - Y.mean(0)
        qx, _ = np.linalg.qr(X)
        qy, _ = np.linalg.qr(Y)
        return float(np.linalg.svd(qx.T @ qy, compute_uv=False)[0])

    def fit(self, X=None, y=None):
        return self

    def scores(self, X):
        refs = self._refs(X.shape[2])
        return np.array([[self._cca_max(x.T, R) for R in refs] for x in X])

    def predict(self, X):
        s = self.scores(X)
        return s.argmax(1), s


class TRCA:
    """Ensemble TRCA: one spatial filter per class that maximises reproducibility across
    the class's training trials, applied as an ensemble; score = correlation between the
    filtered test trial and the filtered class template."""

    def __init__(self, ensemble=True):
        self.ensemble = ensemble
        self.W = None          # (n_classes, n_channels)
        self.templates = None  # (n_classes, n_channels, n_samples)

    @staticmethod
    def _trca_filter(trials):
        # trials: (n_trials, n_ch, n_s). Maximise w' S w / w' Q w, with
        # S = sum over trial pairs of cross-covariance, Q = covariance of the concatenation.
        n_tr, n_ch, n_s = trials.shape
        tr = trials - trials.mean(axis=2, keepdims=True)
        S = np.zeros((n_ch, n_ch))
        for i in range(n_tr):
            for j in range(n_tr):
                if i != j:
                    S += tr[i] @ tr[j].T
        cat = np.concatenate(list(tr), axis=1)  # (n_ch, n_tr*n_s)
        Q = cat @ cat.T
        Q += 1e-6 * np.trace(Q) / n_ch * np.eye(n_ch)
        vals, vecs = np.linalg.eig(np.linalg.solve(Q, S))
        return np.real(vecs[:, np.argmax(np.real(vals))])

    def fit(self, X, y):
        classes = np.unique(y)
        self.classes_ = classes
        self.W = np.stack([self._trca_filter(X[y == c]) for c in classes])
        self.templates = np.stack([X[y == c].mean(0) for c in classes])
        return self

    def scores(self, X):
        n_cls = len(self.classes_)
        W = self.W if self.ensemble else None
        out = np.zeros((len(X), n_cls))
        for k, x in enumerate(X):
            x = x - x.mean(axis=1, keepdims=True)
            for c in range(n_cls):
                w = W if self.ensemble else self.W[c][None, :]
                a = (w @ x).ravel()
                b = (w @ self.templates[c]).ravel()
                out[k, c] = np.corrcoef(a, b)[0, 1]
        return out

    def predict(self, X):
        s = self.scores(X)
        return self.classes_[s.argmax(1)], s


def itr_bits_per_trial(p, n):
    """Information transfer rate per selection, Wolpaw definition."""
    if p <= 1.0 / n:
        return 0.0
    if p >= 1.0:
        return float(np.log2(n))
    return float(np.log2(n) + p * np.log2(p) + (1 - p) * np.log2((1 - p) / (n - 1)))
