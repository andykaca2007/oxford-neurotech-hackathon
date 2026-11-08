"""calibration.leave_one_pair_out: buffered folds leave the held-out pair's neighbours out of training (CRITIQUE calib-4)."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "loadmonitor"))
import calibration  # noqa: E402


def test_separable_blocks_score_high_and_neighbours_are_skipped():
    rng = np.random.default_rng(0)
    blocks = {b: rng.normal(0, 1, (12, 6)) + (2.0 if b % 2 else 0.0) for b in range(8)}
    r = calibration.leave_one_pair_out(blocks, 8, buffered=True)
    assert len(r["folds"]) == 4 and r["auc"] > 0.9
    # blocks 1 and 4 missing: pairs 0 and 2 cannot be held out; pairs 1 and 3 still train on both classes
    r2 = calibration.leave_one_pair_out({k: v for k, v in blocks.items() if k not in (1, 4)}, 8, buffered=True)
    assert len(r2["folds"]) == 2


def test_null_is_near_chance():
    rng = np.random.default_rng(1)
    aucs = [calibration.leave_one_pair_out({b: rng.normal(0, 1, (12, 6)) for b in range(8)}, 8, buffered=True)["auc"] for _ in range(40)]
    assert 0.35 < float(np.median(aucs)) < 0.65
