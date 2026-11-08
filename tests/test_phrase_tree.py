"""Tests for the 16-phrase tree. Run from the repo root:  python -m pytest tests"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "explored", "communication"))
from phrase_tree import TREE, PhraseTree, check_tree  # noqa: E402


def test_tree_is_four_by_four_and_unique():
    check_tree(TREE)
    phrases = PhraseTree().all_phrases()
    assert len(phrases) == 16 and len(set(phrases)) == 16


def test_root_shows_groups():
    assert PhraseTree().labels() == [label for label, _ in TREE]


def test_two_looks_say_a_phrase_then_return_to_groups():
    t = PhraseTree()
    assert t.select(0, now=0.0) is None          # first look opens NEED
    assert t.labels() == TREE[0][1]
    assert t.select(0, now=2.0) == "Water, please"
    assert t.group is None                       # back at the root


def test_every_phrase_is_reachable_by_its_path():
    t = PhraseTree()
    for phrase in t.all_phrases():
        g, p = t.path(phrase)
        assert t.select(g, now=0.0) is None
        assert t.select(p, now=1.0) == phrase


def test_timeout_returns_to_groups_and_late_look_starts_over():
    t = PhraseTree(timeout_s=8.0)
    t.select(2, now=0.0)                         # open PEOPLE
    assert t.select(3, now=9.0) is None          # too late: this look opens ANSWER instead
    assert t.group == 3
    assert t.tick(now=20.0) is True and t.group is None


def test_one_stray_pick_never_says_anything():
    t = PhraseTree()
    assert t.select(1, now=0.0) is None
    t.tick(now=100.0)
    assert t.group is None


def test_bad_tile_and_bad_tree_are_rejected():
    with pytest.raises(ValueError):
        PhraseTree().select(4, now=0.0)
    with pytest.raises(ValueError):
        check_tree(TREE[:3])
    with pytest.raises(ValueError):
        check_tree([("A", ["x", "x", "y", "z"])] + TREE[1:])
