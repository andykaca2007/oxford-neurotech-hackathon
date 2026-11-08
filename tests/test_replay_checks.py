"""replay_all.check_log flags broken-but-finite sessions (CRITIQUE fatigue-adv2)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay_all  # noqa: E402

HDR = "t,load_pct,fatigue_pct,alarm,condition,contact,f0,f1\n"


def _log(tmp_path, rows):
    p = tmp_path / "g.csv"
    p.write_text(HDR + "".join(rows))
    return str(p)


def test_healthy_log_passes(tmp_path):
    rows = [f"{t},{t % 7}.0,50.{t % 9},0,none,1,{1 + t * 0.1:.3f},{-1 - t * 0.2:.3f}\n" for t in range(100)]
    c = replay_all.check_log(_log(tmp_path, rows))
    assert c["bad"] == 0 and c["scored"] == 100


def test_held_rows_are_not_broken(tmp_path):
    rows = [f"{t},0.0,50.0,0,none,1,nan,nan\n" for t in range(100)]
    c = replay_all.check_log(_log(tmp_path, rows))
    assert c["bad"] == 0 and c["scored"] == 0


def test_zeroed_frozen_and_pinned_fail(tmp_path):
    zero = [f"{t},0.0,50.{t % 9},0,none,1,0.0,0.0\n" for t in range(5)]
    assert replay_all.check_log(_log(tmp_path, zero))["zeroed"] == 5
    frozen = [f"{t},10.0,50.{t % 9},0,none,1,0.5,0.7\n" for t in range(61)]
    assert replay_all.check_log(_log(tmp_path, frozen))["longest"] >= 60
    pinned = [f"{t},10.0,100.0,0,none,1,{t * 0.1:.3f},0.7\n" for t in range(30)]
    c = replay_all.check_log(_log(tmp_path, pinned))
    assert c["pinned"] == 30 and c["bad"] >= 1
