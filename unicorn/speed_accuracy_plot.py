"""One figure: held-out accuracy vs calibration time for several window lengths.
Same protocol as calibration_curve.py (Nakanishi 2015, 12 classes, blocks 9 to 15 held out).

    .venv/bin/python unicorn/speed_accuracy_plot.py        -> data/speed_accuracy.png
"""
import glob
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from calibration_curve import FREQS, FS, K_LIST, TEST_BLOCKS, load  # noqa: E402
from trca import CCA, TRCA  # noqa: E402

WINDOWS = [0.5, 1.0, 1.5, 2.0]
COLORS = ["#c0202a", "#d08a00", "#1a7fb5", "#1a9c3a"]


def main():
    files = sorted(glob.glob("data/nakanishi2015/s*.mat"), key=lambda p: int(os.path.basename(p)[1:-4]))
    classes = list(range(12))
    res = {}
    for w in WINDOWS:
        cca_acc, trca_acc = [], {k: [] for k in K_LIST}
        for f in files:
            X, y, blk = load(f, w, classes)
            test = np.isin(blk, TEST_BLOCKS)
            lab, _ = CCA(FREQS, FS).predict(X[test])
            cca_acc.append((lab == y[test]).mean())
            for k in K_LIST:
                m = TRCA().fit(X[blk < k], y[blk < k])
                lab, _ = m.predict(X[test])
                trca_acc[k].append((lab == y[test]).mean())
        res[w] = (np.mean(cca_acc), [np.mean(trca_acc[k]) for k in K_LIST], [np.std(trca_acc[k]) for k in K_LIST])
        print(f"window {w:g} s: CCA {res[w][0]:.2f}  TRCA " + " ".join(f"{m:.2f}" for m in res[w][1]), flush=True)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for w, c in zip(WINDOWS, COLORS):
        cca, means, sds = res[w]
        secs = [k * 12 * w for k in K_LIST]
        ax.errorbar(secs, means, yerr=sds, marker="o", ms=4, color=c, lw=1.6, capsize=2, label=f"{w:g} s window, personal (TRCA)")
        ax.axhline(cca, color=c, ls="--", lw=1, alpha=0.7)
        ax.text(205, cca, f"{w:g} s, generic (CCA)", color=c, fontsize=8, va="center")
    ax.axhline(1 / 12, color="#bbb", ls=":", lw=1)
    ax.text(205, 1 / 12, "chance", color="#999", fontsize=8, va="center")
    ax.set_xlim(0, 200)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("personal calibration time, s")
    ax.set_ylabel("held-out accuracy, 12 targets")
    ax.set_title("Nakanishi 2015, 10 subjects, blocks 9 to 15 held out", fontsize=10)
    ax.legend(frameon=False, fontsize=8, loc="center right", bbox_to_anchor=(1.0, 0.42))
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig("data/speed_accuracy.png", dpi=160)
    print("saved data/speed_accuracy.png")


if __name__ == "__main__":
    main()
