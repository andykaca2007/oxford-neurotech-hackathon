"""REPLAY demo: decode held-out public-data trials one by one, light the tile, buzz the wrist.

For when there is no headset in the room. Says REPLAY on screen; never pass it off as live.

    .venv/bin/python explored/ssvep/ssvep_stim.py --banner REPLAY          (in another terminal)
    .venv/bin/python explored/ssvep/replay_demo.py --subject 3 [--cue-port /dev/cu.usbserial-XXXX]

Trains TRCA on blocks 1 to 5 of one Nakanishi 2015 subject for the 4 targets mapped to our
tiles, then walks through blocks 9 to 15 (held out) in random order: shows the cued tile
(white border), waits the window length, decodes, lights the pick (yellow), buzzes.

Phrase replay: compose phrases from held-out trials, two looks each.

    .venv/bin/python explored/ssvep/ssvep_stim.py --tree --banner REPLAY
    .venv/bin/python explored/ssvep/replay_demo.py --subject 3 --say "Water, please;Call the nurse"

For each phrase it takes the two tiles that say it (phrase_tree.py), and for each tile replays an
unused held-out trial of that tile's class. Whatever the personal decoder picks is what the
stim's tree receives, so a decoding error really does open the wrong group or say the wrong
phrase: the run is honest, not scripted. The wristband buzzes once per finished phrase.
"""
import argparse
import os
import random
import socket
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'communication'))
from calibration_curve import FREQS, FS, TEST_BLOCKS, load  # noqa: E402
from phrase_tree import PhraseTree  # noqa: E402
from trca import CCA, TRCA  # noqa: E402

TILE_CLASSES = [0, 6, 1, 7]  # 9.25, 10.25, 11.25, 12.25 Hz -> tiles WATER, SWALLOW, STAND, HELP


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", type=int, default=3)
    ap.add_argument("--win", type=float, default=1.0)
    ap.add_argument("--trials", type=int, default=12)
    ap.add_argument("--cue-port")
    ap.add_argument("--pace", type=float, default=2.0, help="s between trials")
    ap.add_argument("--say", help='phrases to compose, separated by ";" (run the stim with --tree)')
    a = ap.parse_args()
    tree = PhraseTree()
    phrases = [p.strip() for p in a.say.split(";") if p.strip()] if a.say else []
    for p in phrases:  # check every phrase before any EEG is loaded
        try:
            tree.path(p)
        except KeyError:
            sys.exit(f"{p!r} is not in the tree; phrases are: " + "; ".join(tree.all_phrases()))
    if phrases and a.win + 0.5 + a.pace < 3.2:
        sys.exit("--say needs win + 0.5 + pace of at least 3.2 s, or the stim ignores the second look (--settle 3)")

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
    if phrases:
        # two held-out trials per phrase: one of the group tile's class, one of the phrase tile's
        pool = {tile: [i for i in idx if y[i] == TILE_CLASSES[tile]] for tile in range(4)}
        idx = []
        for p in phrases:
            for tile in tree.path(p):
                if not pool[tile]:
                    sys.exit(f"ran out of held-out trials for tile {tile}; say fewer phrases")
                idx.append(pool[tile].pop())
        a.trials = len(idx)
        print(f"composing {len(phrases)} phrase(s) from {len(idx)} held-out trials: {'; '.join(phrases)}")
    hits_t = hits_c = said_ok = 0
    for n, i in enumerate(idx[:a.trials]):
        if phrases and n % 2 == 0:
            print(f"\n--- phrase {n // 2 + 1}: {phrases[n // 2]!r}")
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
        print(f"personal -> {pick_t} {'OK' if pick_t == tile else 'X'}   generic -> {pick_c} {'OK' if pick_c == tile else 'X'}", flush=True)
        # phrase mode mirrors the stim's tree (same picks, same order) so it knows when a phrase ends
        said = tree.select(pick_t, time.monotonic()) if phrases else None
        if said:
            wanted = phrases[n // 2]
            said_ok += said == wanted
            print(f"    SAID {said!r}  ({'as intended' if said == wanted else 'WRONG, wanted ' + repr(wanted)})", flush=True)
        n_pulses = (tree.group_of(said) + 1 if said else 0) if phrases else pick_t + 1
        if ser:
            for _ in range(n_pulses):
                ser.write(b"b\n")
                time.sleep(0.6)
        time.sleep(a.pace)
    k = min(a.trials, len(idx))
    print(f"\nREPLAY subject {a.subject}, {a.win:g} s window, {k} held-out trials: personal {hits_t}/{k}, generic {hits_c}/{k}")
    if phrases:
        print(f"phrases said as intended: {said_ok}/{len(phrases)}")


if __name__ == "__main__":
    main()
