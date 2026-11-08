"""Personal SSVEP calibration: record cued trials from the live stream, fit TRCA, save it.

Run the stim in trial mode and this at the same time:
    .venv/bin/python explored/ssvep/ssvep_stim.py --trials 12 --on 4 --off 2     (3 trials per tile = 48 s of looking)
    .venv/bin/python explored/ssvep/ssvep_calibrate.py --lsl --out models/paing.npz
Or from a recording with a cue log:
    .venv/bin/python explored/ssvep/ssvep_calibrate.py --fake --out models/fake.npz        (synthetic, for testing)

It listens for "cue i" / "rest" from the stim on UDP 5006, cuts one epoch per cue
(--epoch s after a --latency s delay), band-passes 5 to 40 Hz with a 50 Hz notch,
fits ensemble TRCA on the 4 occipital channels and reports a leave-one-trial-out
accuracy for TRCA and CCA on the same epochs. The .npz holds the filters and templates
for ssvep_decode.py --model.
"""
import argparse
import os
import socket
import sys
import threading
import time
from collections import deque

import numpy as np
from scipy.signal import butter, iirnotch, lfilter, lfilter_zi, sosfilt, sosfilt_zi

sys.path.insert(0, os.path.dirname(__file__))
from trca import CCA, TRCA  # noqa: E402

FS = 250
FREQS = [7.5, 60.0 / 7, 10.0, 12.0]
CH_NAMES = ["Fz", "C3", "Cz", "C4", "Pz", "PO7", "POz", "PO8"]
USE_IDX = [5, 6, 7, 4]  # PO7 POz PO8 Pz


class Filters:
    def __init__(self, nch):
        self.sos = butter(4, [5, 40], btype="band", fs=FS, output="sos")
        self.zi = [sosfilt_zi(self.sos) * 0 for _ in range(nch)]
        self.nb, self.na = iirnotch(50.0, 30.0, fs=FS)
        self.nzi = [lfilter_zi(self.nb, self.na) * 0 for _ in range(nch)]

    def push(self, x):
        out = np.empty_like(x)
        for c in range(x.shape[1]):
            y, self.zi[c] = sosfilt(self.sos, x[:, c], zi=self.zi[c])
            y, self.nzi[c] = lfilter(self.nb, self.na, y, zi=self.nzi[c])
            out[:, c] = y
        return out


def fake_session(n_per_class=4, epoch_s=3.0, seed=1):
    """Yields (t, eeg8, cue) like the live path, with cue = class index or None."""
    rng = np.random.default_rng(seed)
    order = [i % 4 for i in range(4 * n_per_class)]
    rng.shuffle(order)
    n = 0
    phase, amp = 0.0, 1.0
    for k in order + [None]:
        for _ in range(int((epoch_s + 2.0) * FS)):
            t = n / FS
            local = (_ / FS)
            eeg = rng.normal(0, 10, 8)
            phase += 2 * np.pi * 9.3 / FS + rng.normal(0, 0.08)
            amp = 0.995 * amp + 0.005 * rng.uniform(0.3, 1.7)
            eeg += 10 * amp * np.sin(phase)
            if k is not None and local < epoch_s + 0.3:
                s = 8 * (np.sin(2 * np.pi * FREQS[k] * t) + 0.4 * np.sin(2 * np.pi * 2 * FREQS[k] * t))
                for c in USE_IDX:
                    eeg[c] += s
            yield t, eeg, (k if local < epoch_s + 0.3 else None)
            n += 1


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--lsl", action="store_true")
    g.add_argument("--fake", action="store_true")
    ap.add_argument("--epoch", type=float, default=3.0, help="s of EEG kept per cue")
    ap.add_argument("--latency", type=float, default=0.3, help="s skipped after cue onset")
    ap.add_argument("--out", default="models/personal.npz")
    ap.add_argument("--max-trials", type=int, default=0, help="stop after this many cues (0 = until stim stops / Ctrl-C)")
    ap.add_argument("--tiles", type=int, default=4, choices=[4, 12], help="tile set, must match ssvep_stim.py --tiles")
    ap.add_argument("--channels", help="comma list, e.g. POz,Pz,Cz when PO7/PO8 are dead (default PO7,POz,PO8,Pz)")
    a = ap.parse_args()
    global USE_IDX, FREQS
    if a.tiles != 4:
        from tiles import tile_set
        FREQS = tile_set(a.tiles)["freqs"]
    if a.channels:
        USE_IDX = [CH_NAMES.index(c.strip()) for c in a.channels.split(",")]
        print(f"# calibrating from {a.channels} -> indices {USE_IDX}", flush=True)

    filt = Filters(len(USE_IDX))
    n_lat, n_ep = int(a.latency * FS), int(a.epoch * FS)
    epochs, labels = [], []
    cur = {"cue": None, "buf": [], "since": 0}

    if a.lsl:
        from pylsl import StreamInlet, resolve_byprop
        streams = resolve_byprop("name", "Unicorn", timeout=10)
        if not streams:
            sys.exit("no LSL stream named Unicorn")
        inlet = StreamInlet(streams[0])
        cue_box = {"i": None}

        def listen():
            rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            rx.bind(("127.0.0.1", 5006))
            while True:
                msg, _ = rx.recvfrom(64)
                p = msg.decode().split()
                cue_box["i"] = int(p[1]) if p[0] == "cue" else None
        threading.Thread(target=listen, daemon=True).start()

        def src():
            t0 = None
            while True:
                s, ts = inlet.pull_sample()
                if t0 is None:
                    t0 = ts
                yield ts - t0, np.array(s[:8]), cue_box["i"]
        source = src()
        print("# listening for cues from ssvep_stim.py --trials ...; Ctrl-C when the stim says done", flush=True)
    else:
        source = fake_session()

    try:
        for t, eeg, cue in source:
            y = filt.push(eeg[USE_IDX][None, :])[0]
            if cue is not None and cur["cue"] is None:
                cur.update(cue=cue, buf=[], since=0)
            if cur["cue"] is not None:
                if cue is None and cur["since"] < n_lat + n_ep:
                    print(f"# cue {cur['cue']} ended early at {cur['since'] / FS:.1f} s, dropped", flush=True)
                    cur["cue"] = None
                    continue
                cur["since"] += 1
                if cur["since"] > n_lat:
                    cur["buf"].append(y)
                if len(cur["buf"]) == n_ep:
                    epochs.append(np.array(cur["buf"]).T)
                    labels.append(cur["cue"])
                    print(f"# epoch {len(epochs)}: tile {cur['cue']} at t={t:.1f}", flush=True)
                    cur["cue"] = None
                    if a.max_trials and len(epochs) >= a.max_trials:
                        break
    except KeyboardInterrupt:
        pass

    X, y = np.array(epochs), np.array(labels)
    if len(X) < 8 or len(np.unique(y)) < len(FREQS):
        sys.exit(f"not enough epochs ({len(X)}) or classes ({np.unique(y)}): need at least 2 per tile for every tile")
    print(f"\n{len(X)} epochs, per tile {np.bincount(y, minlength=len(FREQS)).tolist()}, {a.epoch:.0f} s each = {len(X) * a.epoch:.0f} s of calibration")

    # leave-one-trial-out: TRCA refit without the held-out epoch, CCA needs no fit
    cca = CCA(FREQS, FS)
    cca_lab, _ = cca.predict(X)
    hit_trca = 0
    for i in range(len(X)):
        m = np.ones(len(X), bool)
        m[i] = False
        if np.bincount(y[m], minlength=len(FREQS)).min() < 2:
            continue
        lab, _ = TRCA().fit(X[m], y[m]).predict(X[i:i + 1])
        hit_trca += int(lab[0] == y[i])
    print(f"leave-one-out on these epochs: CCA {np.mean(cca_lab == y):.0%}   TRCA {hit_trca / len(X):.0%}")

    model = TRCA().fit(X, y)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    np.savez(a.out, W=model.W, templates=model.templates, classes=model.classes_, freqs=FREQS,
             use_idx=USE_IDX, epoch_s=a.epoch, n_epochs=len(X), X=X, y=y)
    print("saved", a.out)


if __name__ == "__main__":
    main()
