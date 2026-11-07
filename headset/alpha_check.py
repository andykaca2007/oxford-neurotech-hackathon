"""Contact and alpha check on the live Unicorn LSL stream. Speaks the instructions.

    .venv/bin/python headset/alpha_check.py

10 s eyes open, 10 s eyes closed. Reports per channel: RMS (uV), 50 Hz mains share,
alpha (8 to 12 Hz) power closed / open. Good occipital contact: Oz, PO7, PO8 ratio
of 2 or more. Ratio near 1 everywhere: the back electrodes are not on the scalp.
"""
import subprocess
import time

import numpy as np
from pylsl import StreamInlet, resolve_byprop
from scipy.signal import butter, sosfiltfilt, welch

FS = 250
SOS = butter(4, [1, 40], btype="band", fs=FS, output="sos")
CH = ["Fz", "C3", "Cz", "C4", "Pz", "PO7", "Oz", "PO8"]


def say(text):
    print("#", text, flush=True)
    subprocess.Popen(["say", text])


def grab(inlet, seconds):
    out = []
    t0 = time.monotonic()
    while time.monotonic() - t0 < seconds:
        s, _ = inlet.pull_sample(timeout=1.0)
        if s:
            out.append(s[:8])
    return np.array(out)


def report(x, label):
    raw_rms = np.sqrt(((x - x.mean(0)) ** 2).mean(0))
    print(f"{label} raw drift RMS: " + " ".join(f"{c}={r / 1000:.1f}mV" for c, r in zip(CH, raw_rms)))
    x = sosfiltfilt(SOS, x - x.mean(0), axis=0)  # 1 to 40 Hz, what the decoder sees
    f, p = welch(x, fs=FS, nperseg=FS * 2, axis=0)
    alpha = p[(f >= 8) & (f <= 12)].mean(0)
    mains = p[(f >= 49) & (f <= 51)].mean(0)
    total = p[(f >= 1) & (f <= 40)].mean(0)
    rms = np.sqrt((x ** 2).mean(0))
    print(f"{label}: " + " ".join(f"{c}={r:.0f}uV" for c, r in zip(CH, rms)))
    print(f"   50 Hz share: " + " ".join(f"{c}={m / t:.1f}" for c, m, t in zip(CH, mains, total)))
    return alpha


def main():
    streams = resolve_byprop("name", "Unicorn", timeout=10)
    if not streams:
        raise SystemExit("no LSL stream named Unicorn: is unicorn_gpype.py running?")
    inlet = StreamInlet(streams[0])
    say("Eyes open. Look at the wall. Ten seconds.")
    time.sleep(2)
    a_open = report(grab(inlet, 10), "eyes open ")
    say("Now close your eyes. Keep them closed.")
    time.sleep(2)
    a_closed = report(grab(inlet, 10), "eyes closed")
    say("Open your eyes. Done.")
    print("alpha closed/open: " + " ".join(f"{c}={r:.1f}" for c, r in zip(CH, a_closed / a_open)))


if __name__ == "__main__":
    main()
