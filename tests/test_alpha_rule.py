"""alpha_rule picks a channel that meets every criterion over one with a bigger rise that does not (CRITIQUE stats-adv2).

The critic's scenario: a flaky slot shows the largest alpha rise, a real posterior channel shows a smaller rise that
satisfies the rule. The rule must PASS on the real channel, not FAIL on the flaky one. The rule sorts candidates by
(ok, margin), so a passing channel always wins; this pins that down."""
import os
import sys
import warnings

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "loadmonitor"))
warnings.filterwarnings("ignore")
import load_gauge as lg  # noqa: E402


def windows(n, height, low, alpha, high, jitter=0.0, seed=0):
    """n windows of (height dB, bands log10 power [low, alpha, high]) with small jitter so percentiles are defined."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        b = np.array([low, alpha, high]) + rng.normal(0, jitter, 3)
        out.append((height + rng.normal(0, jitter * 10), b))
    return out


def test_passing_channel_beats_bigger_rise_that_fails():
    # Pz: alpha +3.5 dB closed vs open, flanks flat: meets rise 3, margin 3, sep 0.8
    # P4: alpha +6 dB but both flanks +5 dB too (broadband noise change, not alpha): rise wins, margin fails
    open_ws, closed_ws = [], []
    for k in range(8):
        open_ws.append({"Pz": windows(1, 0.0, 0.0, 0.0, 0.0, 0.005, k)[0], "P4": windows(1, -3.0, 0.0, 0.0, 0.0, 0.005, 10 + k)[0]})
        closed_ws.append({"Pz": windows(1, 3.5, 0.0, 0.35, 0.0, 0.005, 20 + k)[0], "P4": windows(1, 1.0, 0.5, 0.6, 0.5, 0.005, 30 + k)[0]})
    best = lg.alpha_rule(open_ws, closed_ws, ["Pz", "P4", "O1", "P3"])
    assert best is not None
    assert best["ch"] == "Pz", best
    assert best["ok"], best
    assert best["rise"] >= 3.0 and best["margin"] >= 3.0 and best["sep"] >= 0.8


def test_no_channel_meets_the_rule():
    open_ws, closed_ws = [], []
    for k in range(8):
        open_ws.append({"Pz": windows(1, 0.0, 0.0, 0.0, 0.0, 0.005, k)[0]})
        closed_ws.append({"Pz": windows(1, 1.0, 0.0, 0.1, 0.0, 0.005, 20 + k)[0]})   # +1 dB only
    best = lg.alpha_rule(open_ws, closed_ws, ["Pz", "O1"])
    assert best is not None and best["ch"] == "Pz" and not best["ok"]


def test_too_few_windows_is_untestable():
    open_ws = [{"Pz": windows(1, 0.0, 0.0, 0.0, 0.0, 0.005, k)[0]} for k in range(3)]
    closed_ws = [{"Pz": windows(1, 4.0, 0.0, 0.4, 0.0, 0.005, k)[0]} for k in range(3)]
    assert lg.alpha_rule(open_ws, closed_ws, ["Pz"]) is None
