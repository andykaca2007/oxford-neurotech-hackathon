import numpy as np

from swallow import cue_times, detect, find_bursts, make_session

SEEDS = range(5)
TOL = 0.6  # s, a detection counts if its centre is this close to a true swallow


def _match(found, truth):
    hits = sum(any(abs(f - t) <= TOL for f in found) for t in truth)
    false = sum(not any(abs(f - t) <= TOL for t in truth) for f in found)
    return hits, false


def test_pipeline_finds_every_swallow_burst():
    # Passes before you write anything: the bursts are there to classify.
    for s in SEEDS:
        x, truth = make_session(swallows=6, rng=s)
        centres = [b["centre"] for b in find_bursts(x)]
        hits, _ = _match(centres, truth)
        assert hits == len(truth)


def test_cue_logic():
    # Passes before you write anything.
    assert cue_times([10, 20, 30], seconds=60, T=30) == []
    assert cue_times([10], seconds=100, T=30) == [40, 70]


def test_counts_swallows_in_a_quiet_session():
    for s in SEEDS:
        x, truth = make_session(swallows=6, rng=s)
        hits, false = _match(detect(x), truth)
        assert hits >= 5, f"seed {s}: found {hits} of {len(truth)} swallows"
        assert false == 0, f"seed {s}: {false} false swallows"


def test_ignores_talking_and_chewing():
    for s in SEEDS:
        x, truth = make_session(swallows=4, talk_s=[(5, 30)], chew_s=[(60, 30)], rng=s)
        hits, false = _match(detect(x), truth)
        assert hits >= 3, f"seed {s}: found {hits} of {len(truth)} swallows"
        assert false <= 1, f"seed {s}: {false} false swallows from 60 s of talking + chewing"
