"""Hijack-and-defend warm-up for the Oxford Neurotech Hackathon (7 to 8 Nov 2026).

The victim (PREP.md 4a) is a closed-loop wrist stimulator: when the wrist
IMU shows tremor-band power, it stimulates. The attacker shakes the wrist
sensor at 6 Hz on a still arm, and the device stimulates anyway.

Defence 1 adds a second IMU higher on the forearm. Real tremor moves hand
and forearm together, so the two sensors agree in the tremor band. A shake
applied at the wrist sensor reaches the forearm sensor only weakly. You
write that check: is_genuine().

The attacker here replays a REAL tremor recording, so a check on how the
wrist signal looks (frequency drift, harmonics) cannot catch it. Only the
second sensor can.

Run the checks:  python3 -m pytest -q test_spoof.py
"""

import numpy as np
from scipy import signal

FS = 200            # Hz
BAND = (4.5, 8.0)   # Hz, tremor band (same as tremor.py)
WINDOW_S = 2.0      # seconds of data per stimulate / don't decision
STIM_POWER = 0.05   # tremor-band power (g^2) above which the victim stimulates

FOREARM_GAIN = 0.4  # real tremor seen at the forearm, relative to the wrist
LEAK_GAIN = 0.02    # attacker's shake that leaks from wrist to forearm sensor
NOISE = 0.3         # sensor noise, each IMU independent


def _tremor(n, fs, rng, f0=6.0):
    """Tremor waveform with drifting frequency and waxing amplitude."""
    t = np.arange(n) / fs
    f = f0 + 0.4 * np.sin(2 * np.pi * 0.07 * t + rng.uniform(0, 2 * np.pi))
    phi = 2 * np.pi * np.cumsum(f) / fs + rng.uniform(0, 2 * np.pi)
    amp = 1 + 0.4 * np.sin(2 * np.pi * 0.2 * t + rng.uniform(0, 2 * np.pi))
    return amp * np.cos(phi) + 0.25 * amp * np.cos(2 * phi + 0.5)


def make_scene(kind, seconds=20.0, fs=FS, rng=None):
    """Two IMU traces (wrist, forearm) for one scene.

    kind = "tremor": a real tremor moves both sensors.
           "still":  arm at rest, only slow voluntary movement and noise.
           "spoof":  arm at rest, attacker shakes the wrist sensor with a
                     replayed real tremor recording.
    Slow voluntary movement (0.3 Hz) moves both sensors in every scene.
    """
    rng = np.random.default_rng(rng)
    n = int(seconds * fs)
    t = np.arange(n) / fs
    move = 2.0 * np.sin(2 * np.pi * 0.3 * t + rng.uniform(0, 2 * np.pi))
    wrist = move + NOISE * rng.standard_normal(n)
    forearm = 0.7 * move + NOISE * rng.standard_normal(n)
    if kind == "tremor":
        tr = _tremor(n, fs, rng)
        wrist += tr
        forearm += FOREARM_GAIN * np.roll(tr, 2)   # ~10 ms mechanical lag
    elif kind == "spoof":
        fake = _tremor(n, fs, rng)                 # a recording, replayed
        wrist += fake
        forearm += LEAK_GAIN * fake
    elif kind != "still":
        raise ValueError(kind)
    return wrist, forearm


def band_power(x, fs=FS, band=BAND):
    """Mean power of x inside band (a causal band-pass, as on the ESP32)."""
    b, a = signal.butter(2, band, btype="band", fs=fs)
    return float(np.mean(signal.lfilter(b, a, x - x.mean()) ** 2))


def is_genuine(wrist, forearm, fs=FS, band=BAND):
    """Defence 1: True if the wrist's tremor is also seen at the forearm.

    TODO (yours, about 5 to 8 lines). Inputs are one WINDOW_S window from
    each IMU. Return True for real tremor, False for a shake applied at the
    wrist sensor only.

    Suggested route:
      1. f, C = signal.coherence(wrist, forearm, fs=fs, nperseg=100)
         C is between 0 and 1 at each frequency: 1 = the forearm is a
         fixed linear copy of the wrist there, 0 = unrelated.
      2. average C over f inside band
      3. compare with a threshold you choose

    Choices that are yours, and that you defend to the judges:
      - the threshold. With 2 s windows and nperseg=100 there are only
        about 7 segments, so even unrelated signals read about 0.15 to 0.25
        coherence (estimation bias). Pick something clear of that.
      - whether to ALSO check the forearm/wrist amplitude ratio is
        physically plausible (here real tremor gives about 0.4).
    """
    raise NotImplementedError("write is_genuine")


def run_device(wrist, forearm, defended, fs=FS):
    """Slide the victim along a scene, one decision per WINDOW_S window.

    Returns the fraction of windows in which it stimulated.
    """
    w = int(WINDOW_S * fs)
    stims = []
    for i in range(0, len(wrist) - w + 1, w):
        a, b = wrist[i:i + w], forearm[i:i + w]
        stim = band_power(a, fs) > STIM_POWER
        if stim and defended:
            stim = is_genuine(a, b, fs)
        stims.append(stim)
    return float(np.mean(stims))
