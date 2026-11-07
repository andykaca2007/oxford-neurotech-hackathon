"""How much calibration does a personal SSVEP decoder need? Public-data answer.

Dataset: Nakanishi et al. 2015 (PLoS ONE), 10 subjects, 12 targets at 9.25 to 14.75 Hz,
8 occipital channels (PO7 PO3 POz PO4 PO8 O1 Oz O2), 256 Hz, 15 blocks of 4 s.
Credited; downloaded from github.com/mnakanishi/12JFPM_SSVEP.

Protocol (held-out blocks, never split inside a block):
  for each subject, for k calibration blocks in {1, 2, 3, 5, 8}: train TRCA on the first k
  blocks, test on blocks 9 to 15 (7 held-out blocks, same for every k). CCA has no training and
  is scored on the same test blocks. Window: --win seconds from stimulus onset (default 2 s,
  like the live system). Classes: --classes 4 uses the 4 targets closest to our live tiles.

    .venv/bin/python explored/ssvep/calibration_curve.py            # prints a table, saves curve.png
    .venv/bin/python explored/ssvep/calibration_curve.py --win 3 --classes 12
"""
import argparse
import glob
import os
import sys

import numpy as np
import scipy.io as sio
from scipy.signal import butter, sosfiltfilt

sys.path.insert(0, os.path.dirname(__file__))
from trca import CCA, TRCA, itr_bits_per_trial  # noqa: E402

FS = 256
FREQS = [9.25, 11.25, 13.25, 9.75, 11.75, 13.75, 10.25, 12.25, 14.25, 10.75, 12.75, 14.75]
DELAY_S = 0.15          # visual latency used by the authors
TEST_BLOCKS = list(range(8, 15))
K_LIST = [2, 3, 5, 8]   # TRCA needs at least 2 trials per class (its S matrix is a sum over trial pairs)


def load(path, win_s, classes):
    eeg = sio.loadmat(path)["eeg"]  # (12 targets, 8 ch, 1114 samples, 15 blocks)
    a = 38 + int(DELAY_S * FS)     # README: stimulus onset at the 39th sample; add 0.15 s visual latency
    n = int(win_s * FS)
    sos = butter(4, [6, 40], btype="band", fs=FS, output="sos")
    X, y, blk = [], [], []
    for c in classes:
        for b in range(15):
            seg = eeg[c, :, :, b]
            seg = sosfiltfilt(sos, seg - seg.mean(1, keepdims=True), axis=1)
            X.append(seg[:, a:a + n])
            y.append(c)
            blk.append(b)
    return np.array(X), np.array(y), np.array(blk)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/nakanishi2015")
    ap.add_argument("--win", type=float, default=2.0)
    ap.add_argument("--classes", type=int, default=4, choices=[4, 12])
    ap.add_argument("--out", default="figures/calibration_curve.png")
    a = ap.parse_args()

    # 4 classes nearest to the live tiles (7.5, 8.57, 10, 12 Hz): pick 4 well-spread targets
    classes = [0, 6, 1, 7] if a.classes == 4 else list(range(12))   # 9.25, 10.25, 11.25, 12.25 Hz
    freqs = [FREQS[c] for c in classes]
    files = sorted(glob.glob(os.path.join(a.data, "s*.mat")), key=lambda p: int(os.path.basename(p)[1:-4]))
    if not files:
        sys.exit("no s*.mat files in " + a.data)

    acc_cca, acc_trca = [], {k: [] for k in K_LIST}
    for f in files:
        X, y, blk = load(f, a.win, classes)
        test = np.isin(blk, TEST_BLOCKS)
        cca = CCA(freqs, FS)
        lab, _ = cca.predict(X[test])
        acc_cca.append((np.array(classes)[lab] == y[test]).mean())
        for k in K_LIST:
            train = blk < k
            m = TRCA().fit(X[train], y[train])
            lab, _ = m.predict(X[test])
            acc_trca[k].append((lab == y[test]).mean())
        print(f"{os.path.basename(f)}: CCA {acc_cca[-1]:.2f}  TRCA " + " ".join(f"k{k}={acc_trca[k][-1]:.2f}" for k in K_LIST), flush=True)

    n = len(classes)
    trial_s = a.win + 0.5
    print(f"\n{n} classes, {a.win:.0f} s window, {len(files)} subjects, test = blocks 9 to 15")
    print(f"CCA (0 s calibration):     acc {np.mean(acc_cca):.3f} +/- {np.std(acc_cca):.3f}   ITR {60 / trial_s * itr_bits_per_trial(np.mean(acc_cca), n):.1f} bit/min")
    for k in K_LIST:
        m = np.mean(acc_trca[k])
        print(f"TRCA, {k} block(s) = {k * n * a.win:4.0f} s calib: acc {m:.3f} +/- {np.std(acc_trca[k]):.3f}   ITR {60 / trial_s * itr_bits_per_trial(m, n):.1f} bit/min")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        secs = [k * n * a.win for k in K_LIST]
        means = [np.mean(acc_trca[k]) for k in K_LIST]
        sds = [np.std(acc_trca[k]) for k in K_LIST]
        fig, ax = plt.subplots(figsize=(6.4, 4))
        ax.errorbar(secs, means, yerr=sds, marker="o", color="k", label="TRCA, per-person")
        ax.axhline(np.mean(acc_cca), color="#888", ls="--", label="CCA, no calibration")
        ax.axhline(1 / n, color="#ccc", ls=":", label="chance")
        ax.set_xlabel("calibration time, s")
        ax.set_ylabel(f"held-out accuracy, {n} classes, {a.win:g} s window")
        ax.set_ylim(0, 1.02)
        ax.set_title(f"Nakanishi 2015, {len(files)} subjects, blocks 9 to 15 held out")
        ax.legend(frameon=False)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        fig.tight_layout()
        fig.savefig(a.out, dpi=150)
        print("saved", a.out)
    except ImportError:
        pass


if __name__ == "__main__":
    main()
