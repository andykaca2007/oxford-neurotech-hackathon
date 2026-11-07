"""Tremor phase-tracking warm-up for the Oxford Neurotech Hackathon (7 to 8 Nov 2026).

The project (PREP.md 4a) cues the wrist at a chosen point in each tremor
cycle. That needs the tremor's phase NOW, at the newest sample, from a
causal window. The textbook Hilbert transform gives a clean phase in the
middle of a window and a distorted one at the ends (Gibbs effect), which
is exactly where you need it.

Schreglmann et al. 2021 (Nature Communications 12:363) fixed this with the
endpoint-corrected Hilbert transform (ecHT). You write it below.

Run the checks:  python3 -m pytest -q
"""

import numpy as np
from scipy import signal

FS = 200            # Hz, an MPU6050 does this easily
BAND = (4.5, 8.0)   # Hz. Geometric centre sqrt(4.5 * 8) = 6 Hz, the tremor here


def make_tremor(fs=FS, seconds=20.0, f0=6.0, snr=1.0, rng=None):
    """Fake wrist accelerometer trace with a known true tremor phase.

    tremor = A(t) * cos(phi(t)): frequency drifts around f0, amplitude
    waxes and wanes, plus a 2nd harmonic, a large slow voluntary movement
    (0.3 Hz) and white sensor noise scaled by 1/snr.
    Returns (t, x, true_phase) with true_phase wrapped to (-pi, pi].
    """
    rng = np.random.default_rng(rng)
    n = int(fs * seconds)
    t = np.arange(n) / fs
    f = (f0 + 0.4 * np.sin(2 * np.pi * 0.07 * t + rng.uniform(0, 2 * np.pi))
         + 0.15 * np.cumsum(rng.standard_normal(n)) / np.sqrt(n))
    phi = 2 * np.pi * np.cumsum(f) / fs + rng.uniform(0, 2 * np.pi)
    amp = 1 + 0.4 * np.sin(2 * np.pi * 0.2 * t + rng.uniform(0, 2 * np.pi))
    x = (amp * np.cos(phi)
         + 3.0 * np.sin(2 * np.pi * 0.3 * t + rng.uniform(0, 2 * np.pi))
         + 0.25 * amp * np.cos(2 * phi + 0.5)
         + rng.standard_normal(n) / snr)
    return t, x, np.angle(np.exp(1j * phi))


def naive_phase(window, fs=FS, band=BAND):
    """Baseline: band-pass the window, Hilbert it, read the LAST sample.

    Fine mid-window, wrong at the end. This is what you are beating.
    """
    b, a = signal.butter(2, band, btype="band", fs=fs)
    return np.angle(signal.hilbert(signal.filtfilt(b, a, window))[-1])


def echt_phase(window, fs=FS, band=BAND):
    """Phase (radians) of the tremor at the LAST sample of window.

    TODO (yours, about 8 lines). The ecHT recipe:
      1. remove the window mean, FFT it  (np.fft.fft)
      2. build the analytic-signal mask h: h[0] = 1, positive frequencies
         x2, negative frequencies 0, and for even n the Nyquist bin = 1
      3. design a causal 2nd-order Butterworth band-pass on band
         (signal.butter(2, band, btype="band", fs=fs)) and evaluate its
         frequency response H at |FFT frequencies|
         (np.fft.fftfreq(n, 1/fs), then signal.freqz(b, a, worN=..., fs=fs))
      4. multiply spectrum * h * H, inverse FFT
      5. return np.angle of the LAST sample

    Why step 3 is causal on purpose: the causal filter's phase response
    weights the end of the window so the edge distortion cancels. A
    Butterworth band-pass has zero phase only at its geometric centre, so a
    band not centred on the tremor gives a constant phase bias (your poles
    and Bode block, in the wild).
    """
    raise NotImplementedError("write echt_phase")


def track(x, estimator, fs=FS, window_s=1.0, step=4, band=BAND):
    """Run an estimator causally along x, one estimate every step samples.

    Returns (idx, phase): phase[k] is the estimate for sample idx[k] - 1,
    using only x[idx[k] - window : idx[k]].
    """
    w = int(window_s * fs)
    idx = np.arange(w, len(x), step)
    return idx, np.array([estimator(x[i - w:i], fs, band) for i in idx])


def phase_error_deg(est, true):
    """Absolute circular error in degrees, 0 to 180."""
    return np.degrees(np.abs(np.angle(np.exp(1j * (np.asarray(est) - np.asarray(true))))))


def plv(phases):
    """Phase-locking value of cue times: 1 = every cue at the same phase,
    about 0 = random timing. The headline number for the live demo."""
    return float(np.abs(np.mean(np.exp(1j * np.asarray(phases)))))
