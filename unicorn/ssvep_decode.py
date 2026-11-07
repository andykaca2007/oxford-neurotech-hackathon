# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "pyserial"]
# ///
"""SSVEP decoder: which tile is the wearer looking at?

Input, pick one:
    --fake                 synthetic SSVEP (no hardware), cycles through the 4 targets every 6 s
    --csv s0.csv           replay a unicorn_mac.py log at real speed (or --speed 5)
    --lsl                  live from an LSL stream named Unicorn (unicorn_mac.py --lsl, or the
                           Windows Unicorn LSL sender; needs: uv pip install pylsl)
Outputs:
    prints one line per hop: t, the 4 CCA scores, the pick
    UDP "pick i" to ssvep_stim.py (localhost 5005) so the tile lights up
    --cue-port /dev/cu.usbserial-XXXX: buzzes the ESP32 wristband, i+1 pulses for tile i
        add --buzz-on phrase with ssvep_stim.py --tree: buzz only when a phrase is finished
        (group+1 pulses), and use --refractory 4 so the second look is decoded from fresh EEG
    --log run.csv: t, cued, scores, pick (cued comes from the stim's trial mode)
At the end (Ctrl-C) prints the trial score: picks that matched the cued tile, misses, abstains,
and picks made while no cue was on (false selections per minute).

Pipeline: 4 occipital channels (PO7, Oz, PO8, Pz) -> band-pass 5 to 40 Hz -> notch 50 Hz
-> sliding window (--win s, --hop s) -> CCA against sin/cos references at f and 2f
for f in 7.5, 8.571, 10, 12 Hz -> score per target -> pick_target(scores) -> cue.

pick_target() is YOURS (see below). Until you write it, every window abstains.
"""
import argparse
import socket
import sys
import threading
import time
from collections import deque

import numpy as np
from scipy.signal import butter, iirnotch, sosfilt, sosfilt_zi, lfilter, lfilter_zi

FS = 250
FREQS = [7.5, 60.0 / 7, 10.0, 12.0]
CH_NAMES = ["Fz", "C3", "Cz", "C4", "Pz", "PO7", "Oz", "PO8"]
USE = ["PO7", "Oz", "PO8", "Pz"]
USE_IDX = [CH_NAMES.index(c) for c in USE]
HARMONICS = 2


# ---------------------------------------------------------------------------
# YOUR RULE. scores is a list of 4 floats in [0, 1], one per tile, in FREQS order.
# Return the tile index (0..3) to select, or None to abstain.
#
# Things to decide, and they are the whole project:
#   - absolute floor: below what score is it noise? (fake data gives ~0.6 for the
#     true target and ~0.2 to 0.3 for the others; real heads are lower and closer)
#   - margin: how far ahead of the runner-up must the winner be?
#   - persistence: ask for the same winner on 2 or 3 consecutive hops (the caller
#     gives you `history`, the last few picks including None) so one noisy window
#     cannot fire the wristband. More persistence = fewer false cues, slower.
#   - refractory: after a pick, the caller already waits --refractory s.
# Write 5 to 10 lines. Test with --fake, then --csv on a real recording.
# ---------------------------------------------------------------------------
FLOOR = 0.45      # best score below this: nobody is looking, or bad contact
MARGIN = 0.15     # best must beat the runner-up by this much
_last_best = None  # raw argmax of the previous hop, for persistence


def pick_target(scores: list[float], history: list) -> int | None:
    # Rule written by Claude on 7 Nov 2026 at Paing's request; constants retuned at the table.
    global _last_best
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    best, second = order[0], order[1]
    agree = _last_best == best
    _last_best = best
    if scores[best] < FLOOR:
        return None
    if scores[best] - scores[second] < MARGIN:
        return None
    if not agree:  # same winner on two consecutive hops (1 s) before firing
        return None
    return best


def cca_max(X: np.ndarray, Y: np.ndarray) -> float:
    """Largest canonical correlation between X (n x p) and Y (n x q)."""
    X = X - X.mean(axis=0)
    Y = Y - Y.mean(axis=0)
    qx, _ = np.linalg.qr(X)
    qy, _ = np.linalg.qr(Y)
    s = np.linalg.svd(qx.T @ qy, compute_uv=False)
    return float(s[0])


def references(n: int) -> list[np.ndarray]:
    t = np.arange(n) / FS
    refs = []
    for f in FREQS:
        cols = []
        for h in range(1, HARMONICS + 1):
            cols += [np.sin(2 * np.pi * h * f * t), np.cos(2 * np.pi * h * f * t)]
        refs.append(np.column_stack(cols))
    return refs


class Filters:
    def __init__(self, nch):
        self.sos = butter(4, [5, 40], btype="band", fs=FS, output="sos")
        self.zi = [sosfilt_zi(self.sos) * 0 for _ in range(nch)]
        b, a = iirnotch(50.0, 30.0, fs=FS)
        self.nb, self.na = b, a
        self.nzi = [lfilter_zi(b, a) * 0 for _ in range(nch)]

    def push(self, x: np.ndarray) -> np.ndarray:
        out = np.empty_like(x)
        for c in range(x.shape[1]):
            y, self.zi[c] = sosfilt(self.sos, x[:, c], zi=self.zi[c])
            y, self.nzi[c] = lfilter(self.nb, self.na, y, zi=self.nzi[c])
            out[:, c] = y
        return out


# ---------------------------------------------------------------------------
# sources: each yields (t_seconds, eeg[8] uV) one sample at a time
# ---------------------------------------------------------------------------
def src_fake(seed=0, snr=1.0, period_s=6.0):
    rng = np.random.default_rng(seed)
    n = 0
    phase = 0.0
    amp = 1.0
    while True:
        t = n / FS
        k = int(t // period_s) % 4
        eeg = rng.normal(0, 10, 8)
        # alpha-ish background: ~9.3 Hz with wandering phase and amplitude, so it is
        # not a clean sine (a clean one at a target frequency fools CCA completely)
        phase += 2 * np.pi * 9.3 / FS + rng.normal(0, 0.08)
        amp = 0.995 * amp + 0.005 * rng.uniform(0.3, 1.7)
        eeg += 10 * amp * np.sin(phase)
        ssvep = snr * 10 * (np.sin(2 * np.pi * FREQS[k] * t) + 0.4 * np.sin(2 * np.pi * 2 * FREQS[k] * t))
        for c in USE_IDX:
            eeg[c] += ssvep
        yield t, eeg, k
        n += 1


def src_csv(path, speed=1.0):
    """Replay a recording: unicorn_mac.py logs (t,counter,batt,8 EEG,...) or g.Pype
    CsvWriter files from unicorn_gpype.py (comment lines, then Time, Ch01..Ch08)."""
    t0 = None
    w0 = time.monotonic()
    with open(path) as f:
        header = None
        for line in f:
            if line.startswith("#"):
                continue
            if header is None:
                header = [h.strip() for h in line.split(",")]
                eeg_cols = slice(1, 9) if header[0].lower().startswith("time") else slice(3, 11)
                continue
            p = line.strip().split(",")
            if len(p) < 9:
                continue
            t = float(p[0])
            eeg = np.array([float(v) for v in p[eeg_cols]])
            if t0 is None:
                t0 = t
            lag = (t - t0) / speed - (time.monotonic() - w0)
            if lag > 0:
                time.sleep(lag)
            yield t, eeg, None


def src_lsl():
    from pylsl import StreamInlet, resolve_byprop
    streams = resolve_byprop("name", "Unicorn", timeout=10)
    if not streams:
        sys.exit("no LSL stream named Unicorn")
    inlet = StreamInlet(streams[0])
    print(f"# LSL: {inlet.info().channel_count()} ch at {inlet.info().nominal_srate()} Hz", flush=True)
    t0 = None
    while True:
        s, ts = inlet.pull_sample()
        if t0 is None:
            t0 = ts
        yield ts - t0, np.array(s[:8]), None


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--fake", action="store_true")
    g.add_argument("--csv")
    g.add_argument("--lsl", action="store_true")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--win", type=float, default=3.0)
    ap.add_argument("--hop", type=float, default=0.5)
    ap.add_argument("--refractory", type=float, default=2.0, help="s after a pick before the next")
    ap.add_argument("--cue-port")
    ap.add_argument("--buzz-on", choices=["pick", "phrase"], default="pick",
                    help="pick: buzz tile+1 pulses on every pick (old behaviour); phrase: only when "
                         "ssvep_stim.py --tree finishes a phrase, group+1 pulses")
    ap.add_argument("--log")
    ap.add_argument("--seconds", type=float, default=0, help="stop after this many signal seconds (0 = run until Ctrl-C)")
    ap.add_argument("--model", help="personal TRCA model from ssvep_calibrate.py; scores come from it, CCA is logged beside")
    a = ap.parse_args()

    trca = None
    if a.model:
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from trca import TRCA
        m = np.load(a.model)
        trca = TRCA()
        trca.W, trca.templates, trca.classes_ = m["W"], m["templates"], m["classes"]
        a.win = float(m["epoch_s"])  # window must match the template length
        print(f"# personal model {a.model}: {int(m['n_epochs'])} epochs, window set to {a.win:.1f} s", flush=True)

    src = src_fake() if a.fake else src_csv(a.csv, a.speed) if a.csv else src_lsl()
    nwin = int(a.win * FS)
    nhop = int(a.hop * FS)
    refs = references(nwin)
    filt = Filters(len(USE_IDX))
    buf = deque(maxlen=nwin)

    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    cue_now = {"i": None}

    ser = None
    if a.cue_port:
        import serial
        ser = serial.Serial(a.cue_port, 115200, timeout=0.1)

    def buzz(i):
        def run():
            for _ in range(i + 1):
                ser.write(b"b\n")
                time.sleep(0.6)
        threading.Thread(target=run, daemon=True).start()

    def listen():  # messages from ssvep_stim.py: cues (--trials) and finished phrases (--tree)
        rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rx.bind(("127.0.0.1", 5006))
        while True:
            msg, _ = rx.recvfrom(64)
            p = msg.decode().split()
            if p[0] == "cue":
                cue_now["i"] = int(p[1])
            elif p[0] == "rest":
                cue_now["i"] = None
            elif p[0] == "phrase" and ser and a.buzz_on == "phrase":
                print(f"# phrase done: group {p[1]}, phrase {p[2]} -> buzz {int(p[1]) + 1}", flush=True)
                buzz(int(p[1]))  # group 0..3 -> 1..4 pulses, so the carer knows NEED/BODY/PEOPLE/ANSWER
    threading.Thread(target=listen, daemon=True).start()

    log = open(a.log, "w") if a.log else None
    if log:
        log.write("t,cued,s0,s1,s2,s3,pick" + (",c0,c1,c2,c3" if trca is not None else "") + "\n")

    history = deque(maxlen=5)
    last_pick_t = -1e9
    stats = dict(hit=0, miss=0, abstain=0, false=0, t_free=0.0)
    since = 0
    t = 0.0
    try:
        for t, eeg, truth in src:
            if a.seconds and t > a.seconds:
                break
            buf.append(filt.push(eeg[USE_IDX][None, :])[0])
            since += 1
            if len(buf) < nwin or since < nhop:
                continue
            since = 0
            X = np.array(buf)
            cca_scores = [cca_max(X, R) for R in refs]
            if trca is not None:
                scores = trca.scores(X.T[None, :, :])[0].tolist()
            else:
                scores = cca_scores
            cued = truth if a.fake else cue_now["i"]
            if t - last_pick_t < a.refractory:
                pick = None
            else:
                try:
                    pick = pick_target(scores, list(history))
                except NotImplementedError:
                    pick = None
            history.append(pick)
            if pick is not None:
                last_pick_t = t
                tx.sendto(f"pick {pick}".encode(), ("127.0.0.1", 5005))
                if ser and a.buzz_on == "pick":
                    buzz(pick)
            if cued is None:
                stats["t_free"] += a.hop
                if pick is not None:
                    stats["false"] += 1
            elif pick is None:
                stats["abstain"] += 1
            elif pick == cued:
                stats["hit"] += 1
            else:
                stats["miss"] += 1
            line = f"t={t:6.1f} cued={cued if cued is not None else '-'} " + " ".join(f"{s:.2f}" for s in scores) + f"  pick={pick if pick is not None else '-'}"
            if trca is not None:
                line += "   cca " + " ".join(f"{s:.2f}" for s in cca_scores)
            print(line, flush=True)
            if log:
                log.write(f"{t:.2f},{'' if cued is None else cued}," + ",".join(f"{s:.3f}" for s in scores) + f",{'' if pick is None else pick}"
                          + ("," + ",".join(f"{s:.3f}" for s in cca_scores) if trca is not None else "") + "\n")
    except KeyboardInterrupt:
        pass
    finally:
        if log:
            log.close()
        n = stats["hit"] + stats["miss"] + stats["abstain"]
        print("\n# windows during a cue:", n)
        if n:
            print(f"#   hit {stats['hit']}  miss {stats['miss']}  abstain {stats['abstain']}   accuracy of picks "
                  f"{stats['hit'] / max(1, stats['hit'] + stats['miss']):.0%}")
        if stats["t_free"] > 0:
            print(f"# false selections with no cue: {stats['false']}  ({stats['false'] / (stats['t_free'] / 60):.2f} per minute)")


if __name__ == "__main__":
    main()
