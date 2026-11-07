"""SwallowCue warm-up for the Oxford Neurotech Hackathon (7 to 8 Nov 2026).

People with Parkinson's drool because they swallow too rarely. SwallowCue
reads muscle activity under the chin (EMG), counts swallows, and buzzes a
wristband only when no swallow has happened for T seconds.

The hard part is telling a swallow from talking and chewing: all three
fire the same chin muscles. This file fakes a chin EMG recording with all
three, finds the muscle bursts for you, and leaves the decision to you:
is_swallow().

Run the checks:  python3 -m pytest -q test_swallow.py
"""

import numpy as np
from scipy import signal

FS = 250           # Hz, an OpenBCI Cyton's rate (sees up to 125 Hz)
EMG_BAND = (20, 120)
ENV_CUTOFF = 5     # Hz, smoothing for the envelope
ON_FACTOR = 3.0    # burst = envelope above ON_FACTOR x the quiet level


# ----------------------------------------------------------------------------
# Fake recording
# ----------------------------------------------------------------------------

def _burst(n, fs, start_s, dur_s, amp, rng):
    """One muscle burst: noise shaped by a smooth on-off window."""
    out = np.zeros(n)
    i0, m = int(start_s * fs), max(int(dur_s * fs), 2)
    i1 = min(i0 + m, n)
    out[i0:i1] = amp * np.hanning(m)[: i1 - i0] * rng.standard_normal(i1 - i0)
    return out


def make_session(seconds=120.0, fs=FS, swallows=6, talk_s=(), chew_s=(), rng=None):
    """Fake under-chin EMG.

    swallows: how many swallows, spread out with quiet around them.
              Each is one long-ish burst (0.6 to 1.2 s).
    talk_s:   list of (start, length) in seconds. Talking = many short
              syllable bursts (0.08 to 0.25 s) with short gaps.
    chew_s:   list of (start, length). Chewing = a regular train of
              0.25 to 0.4 s bursts about every 0.7 s.

    Returns (x, true_swallow_centres_in_seconds).
    """
    rng = np.random.default_rng(rng)
    n = int(seconds * fs)
    x = rng.standard_normal(n)                       # electrode noise
    busy = [(s, s + L) for s, L in list(talk_s) + list(chew_s)]

    centres = []
    tries = 0
    while len(centres) < swallows and tries < 10000:
        tries += 1
        d = rng.uniform(0.6, 1.2)
        s = rng.uniform(2, seconds - 3)
        clear = all(s + d + 2 < a or s - 2 > b for a, b in busy)
        clear &= all(abs(s - c) > 6 for c in centres)
        if clear:
            x += _burst(n, fs, s, d, rng.uniform(6, 10), rng)
            centres.append(s + d / 2)

    for start, length in talk_s:
        t = start
        while t < start + length:
            d = rng.uniform(0.08, 0.25)
            x += _burst(n, fs, t, d, rng.uniform(3, 8), rng)
            t += d + rng.uniform(0.05, 0.3)

    for start, length in chew_s:
        t, period = start, rng.uniform(0.6, 0.8)
        while t < start + length:
            d = rng.uniform(0.25, 0.4)
            x += _burst(n, fs, t, d, rng.uniform(5, 9), rng)
            t += period + rng.uniform(-0.05, 0.05)

    return x, sorted(centres)


# ----------------------------------------------------------------------------
# Pipeline (given): filter -> envelope -> bursts
# ----------------------------------------------------------------------------

def envelope(x, fs=FS):
    """Band-pass the EMG, rectify, smooth. Causal, as on a live stream."""
    b, a = signal.butter(4, EMG_BAND, btype="band", fs=fs)
    y = np.abs(signal.lfilter(b, a, x))
    b, a = signal.butter(2, ENV_CUTOFF, fs=fs)
    return signal.lfilter(b, a, y)


def find_bursts(x, fs=FS):
    """Muscle bursts as dicts with:
    start, end, centre (s), duration (s), peak (envelope units),
    gap_before, gap_after (s of quiet to the neighbouring burst; inf at the ends).
    """
    env = envelope(x, fs)
    quiet = np.median(env)
    on = env > ON_FACTOR * quiet
    edges = np.flatnonzero(np.diff(on.astype(int)))
    if on[0]:
        edges = np.r_[0, edges]
    if on[-1]:
        edges = np.r_[edges, len(on) - 1]
    bursts = []
    for i0, i1 in zip(edges[::2], edges[1::2]):
        if (i1 - i0) / fs < 0.05:                    # ignore blips
            continue
        bursts.append(dict(start=i0 / fs, end=i1 / fs, centre=(i0 + i1) / 2 / fs,
                           duration=(i1 - i0) / fs, peak=float(env[i0:i1].max())))
    for k, bu in enumerate(bursts):
        bu["gap_before"] = bu["start"] - bursts[k - 1]["end"] if k else np.inf
        bu["gap_after"] = bursts[k + 1]["start"] - bu["end"] if k + 1 < len(bursts) else np.inf
    return bursts


# ----------------------------------------------------------------------------
# Yours
# ----------------------------------------------------------------------------

def is_swallow(burst):
    """True if this burst is a swallow, False if it looks like talking or chewing.

    TODO (yours, about 5 to 8 lines). You get one burst dict from
    find_bursts(): duration, peak, gap_before, gap_after (seconds).

    What separates them in this fake data (and roughly in real chin EMG):
      - swallow: one long muscle burst with quiet around it
      - talking: many short bursts close together; neighbouring syllables
        can MERGE into one longer burst
      - chewing: medium bursts repeating every ~0.7 s

    Careful: the MEASURED duration is shorter than the real muscle
    activity, because the threshold clips the rising and falling edges.
    Do not trust the generator's numbers; look at what find_bursts()
    reports. Start with print_burst_stats() below, then pick your rule.

    Decisions that are yours, and that you defend to the judges:
      - the duration window. Too narrow misses short swallows; too wide
        lets merged speech in.
      - how much quiet you require around a swallow (gap_before/after).
        People do swallow in the middle of a meal, so a strict rule
        undercounts while eating. Which error is worse for a drooling cue:
        a missed swallow (an extra buzz) or a false swallow (a missed buzz)?
    """
    raise NotImplementedError("write is_swallow")


# ----------------------------------------------------------------------------
# Cue logic (given)
# ----------------------------------------------------------------------------

def cue_times(swallow_times, seconds, T=30.0):
    """When the wristband buzzes: T s after the last swallow (or the start),
    then every T s until the next swallow."""
    cues, last = [], 0.0
    events = sorted(swallow_times) + [seconds]
    for s in events:
        t = last + T
        while t < s:
            cues.append(t)
            t += T
        last = s
    return cues


def print_burst_stats(seeds=range(10)):
    """Look before you choose: measured duration and quiet-around (min gap)
    for each kind of burst. Run:  python3 -c "import swallow; swallow.print_burst_stats()" """
    kinds = {"swallow": [], "talking": [], "chewing": []}
    for s in seeds:
        x, truth = make_session(swallows=4, talk_s=[(5, 30)], chew_s=[(60, 30)], rng=s)
        for b in find_bursts(x):
            if any(abs(b["centre"] - t) < 0.6 for t in truth):
                k = "swallow"
            else:
                k = "talking" if b["start"] < 36 else "chewing"
            kinds[k].append((b["duration"], min(b["gap_before"], b["gap_after"])))
    for k, v in kinds.items():
        v = np.array(v)
        print(f"{k:8s} n={len(v):4d}  duration {v[:, 0].min():.2f} to {v[:, 0].max():.2f} s"
              f"   quiet around {v[:, 1].min():.2f} to {v[:, 1].max():.2f} s")


def detect(x, fs=FS):
    """Swallow times (burst centres) the device would count."""
    return [b["centre"] for b in find_bursts(x, fs) if is_swallow(b)]
