import numpy as np

from tremor import FS, echt_phase, make_tremor, naive_phase, phase_error_deg, plv, track


def median_error(estimator, x, true_phase):
    idx, est = track(x, estimator)
    return np.median(phase_error_deg(est, true_phase[idx - 1]))


def test_clean_sinusoid_is_near_exact():
    t = np.arange(0, 10, 1 / FS)
    phi = 2 * np.pi * 6.0 * t + 0.7
    err = median_error(echt_phase, np.cos(phi), np.angle(np.exp(1j * phi)))
    assert err < 3.0, f"median error {err:.1f} deg on a clean 6 Hz cosine"


def test_noisy_tremor_tracked():
    for seed in range(3):
        _, x, ph = make_tremor(snr=1.0, rng=seed)
        err = median_error(echt_phase, x, ph)
        assert err < 25.0, f"seed {seed}: median error {err:.1f} deg"


def test_beats_naive_hilbert_by_15_degrees():
    for seed in range(3):
        _, x, ph = make_tremor(snr=1.0, rng=seed)
        mine = median_error(echt_phase, x, ph)
        base = median_error(naive_phase, x, ph)
        assert mine < base - 15.0, f"seed {seed}: ecHT {mine:.1f} vs naive {base:.1f}"


def test_plv_helper():
    assert abs(plv([0.3] * 50) - 1.0) < 1e-12
    rng = np.random.default_rng(0)
    assert plv(rng.uniform(-np.pi, np.pi, 5000)) < 0.05
