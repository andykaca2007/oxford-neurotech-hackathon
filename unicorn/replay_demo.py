"""REPLAY demo: decode held-out public-data trials one by one, light the tile, buzz the wrist.

For when there is no headset in the room. Says REPLAY on screen; never pass it off as live.

    .venv/bin/python unicorn/ssvep_stim.py --banner REPLAY          (in another terminal)
    .venv/bin/python unicorn/replay_demo.py --subject 3 [--cue-port /dev/cu.usbserial-XXXX]

Trains TRCA on blocks 1 to 5 of one Nakanishi 2015 subject for the 4 targets mapped to our
tiles, then walks through blocks 9 to 15 (held out) in random order: shows the cued tile
(white border), waits the window length, decodes, lights the pick (yellow), buzzes.
"""
import argparse
import os
import random
import socket
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from calibration_curve import FREQS, FS, TEST_BLOCKS, load  # noqa: E402
from trca import CCA, TRCA  # noqa: E402

TILE_CLASSES = [0, 6, 1, 7]  # 9.25, 10.25, 11.25, 12.25 Hz -> tiles WATER, SWALLOW, STAND, HELP


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", type=int, default=3)
    ap.add_argument("--win", type=float, default=1.0)
    ap.add_argument("--trials", type=int, default=12)
    ap.add_argument("--cue-port")
    ap.add_argument("--pace", type=float, default=2.0, help="s between trials")
    a = ap.parse_args()

    X, y, blk = load(f"data/nakanishi2015/s{a.subject}.mat", a.win, TILE_CLASSES)
    train = blk < 5
    test = np.isin(blk, TEST_BLOCKS)
    trca = TRCA().fit(X[train], y[train])
    cca = CCA([FREQS[c] for c in TILE_CLASSES], FS)

    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ser = None
    if a.cue_port:
        import serial
        ser = serial.Serial(a.cue_port, 115200, timeout=0.1)
        time.sleep(2)

    idx = list(np.where(test)[0])
    random.shuffle(idx)
    hits_t = hits_c = 0
    for n, i in enumerate(idx[:a.trials]):
        tile = TILE_CLASSES.index(y[i])
        tx.sendto(f"cue {tile}".encode(), ("127.0.0.1", 5006))
        print(f"trial {n + 1}: looking at tile {tile} ...", end=" ", flush=True)
        time.sleep(a.win + 0.5)
        lab_t, _ = trca.predict(X[i:i + 1])
        lab_c, _ = cca.predict(X[i:i + 1])
        pick_t = TILE_CLASSES.index(lab_t[0])
        pick_c = int(lab_c[0])
        hits_t += pick_t == tile
        hits_c += pick_c == tile
        tx.sendto("rest".encode(), ("127.0.0.1", 5006))
        tx.sendto(f"pick {pick_t}".encode(), ("127.0.0.1", 5005))
        if ser:
            for _ in range(pick_t + 1):
                ser.write(b"b\n")
                time.sleep(0.6)
        print(f"personal -> {pick_t} {'OK' if pick_t == tile else 'X'}   generic -> {pick_c} {'OK' if pick_c == tile else 'X'}", flush=True)
        time.sleep(a.pace)
    k = min(a.trials, len(idx))
    print(f"\nREPLAY subject {a.subject}, {a.win:g} s window, {k} held-out trials: personal {hits_t}/{k}, generic {hits_c}/{k}")


if __name__ == "__main__":
    main()
