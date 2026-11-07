from spoof import make_scene, run_device

SEEDS = range(5)


def test_undefended_device_is_hijacked():
    # Passes before you write anything: this is the attack working.
    for s in SEEDS:
        assert run_device(*make_scene("spoof", rng=s), defended=False) > 0.8
        assert run_device(*make_scene("still", rng=s), defended=False) < 0.1


def test_defence_blocks_the_attack():
    for s in SEEDS:
        rate = run_device(*make_scene("spoof", rng=s), defended=True)
        assert rate < 0.1, f"seed {s}: still hijacked in {rate:.0%} of windows"


def test_defence_keeps_real_tremor():
    for s in SEEDS:
        rate = run_device(*make_scene("tremor", rng=s), defended=True)
        assert rate > 0.9, f"seed {s}: real tremor treated in only {rate:.0%} of windows"
