"""Filter-bank Riemannian features for the live gauge, matching loadmonitor/optimize.py 'riem-fb'.

For one 4 s window (8 ch): band-pass in theta, alpha, beta; OAS covariance per band; re-centre with the wearer's
baseline covariance (W = base^-1/2, C -> W C W, so the baseline maps to identity); tangent-space map with the
reference fitted on the training set; concatenate the three bands (3 x 36 = 108 numbers).
"""
import numpy as np
from scipy.signal import butter, sosfiltfilt

BANDS = [(4, 8), (8, 13), (13, 30)]


def _cov(x):
    from pyriemann.estimation import Covariances
    return Covariances(estimator="oas").transform(x[None])[0]


class RiemFB:
    def __init__(self, fs, tangent_spaces):
        """tangent_spaces: list of fitted pyriemann TangentSpace, one per band (from training)."""
        self.fs = fs
        self.ts = tangent_spaces
        self.sos = [butter(4, [lo, hi], btype="band", fs=fs, output="sos") for lo, hi in BANDS]
        self.W = None

    def covs(self, x):
        """x: (ch, t) one window, already mean-removed or not (we remove it). Returns a list of per-band covariances."""
        x = x - x.mean(1, keepdims=True)
        return [_cov(sosfiltfilt(s, x, axis=1)) for s in self.sos]

    def set_baseline(self, cov_lists):
        """cov_lists: list over baseline windows of the per-band covariance lists."""
        from pyriemann.utils.base import invsqrtm
        self.W = []
        for b in range(len(BANDS)):
            base = np.mean([c[b] for c in cov_lists], axis=0)
            self.W.append(invsqrtm(base))

    def features(self, covs):
        out = []
        for b, c in enumerate(covs):
            cc = self.W[b] @ c @ self.W[b]
            out.append(self.ts[b].transform(cc[None])[0])
        return np.concatenate(out)
