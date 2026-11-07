# /// script
# requires-python = ">=3.10"
# dependencies = ["pygame"]
# ///
"""SSVEP cue remote: four flickering tiles. Look at one, the decoder picks it.

    uv run unicorn/ssvep_stim.py                 # free mode: tiles flicker, decoder highlights its pick
    uv run unicorn/ssvep_stim.py --trials 12     # trial mode: cues a tile (white border) for --on s,
                                                 # rests --off s, repeats; the decoder logs cued vs picked
    uv run unicorn/ssvep_stim.py --tree          # phrase mode: look 1 opens a group, look 2 says a
                                                 # phrase (phrase_tree.py); the carer bar shows it
        --phrase-log NAME_phrases.csv            # logs every open / say / timeout / ignored pick
    In phrase mode run the decoder with --refractory at least window + 1 s (e.g. 4 for a 3 s
    window) so the second look is decoded from fresh EEG, not the tail of the first look.
    The stim also ignores picks that arrive within --settle s of a group opening.

Lock the MacBook display to 60 Hz first (System Settings > Displays > Refresh rate),
or the flicker frequencies are wrong. Press F for fullscreen, Esc to quit.

Frequencies are frame-locked: 60 / period_frames. 8 frames = 7.5 Hz, 7 = 8.57 Hz,
6 = 10 Hz, 5 = 12 Hz. Half-periods are rounded (7 frames -> 4 on, 3 off), which is
the usual approximation and still peaks at 8.57 Hz.

Talks to ssvep_decode.py over UDP on localhost:
    5005 (decoder -> stim): "pick <i>" or "pick none"
    5006 (stim -> decoder): "cue <i>" at every cue onset, "rest" at every cue end,
                            "phrase <group> <i>" when phrase mode completes a phrase
                            (ssvep_decode.py --buzz-on phrase buzzes the wristband on it)
"""
import argparse
import os
import random
import socket
import subprocess
import sys
import time

import pygame

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phrase_tree import PhraseTree  # noqa: E402

TILES = [  # label, period in frames at 60 Hz, colour
    ("WATER", 8, (70, 130, 255)),
    ("SWALLOW", 7, (80, 200, 120)),
    ("STAND", 6, (250, 180, 60)),
    ("HELP", 5, (240, 80, 80)),
]
FREQS = [60.0 / p for _, p, _ in TILES]  # 7.5, 8.571, 10, 12


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=0, help="number of cued trials (0 = free mode)")
    ap.add_argument("--on", type=float, default=5.0, help="seconds a cue stays on")
    ap.add_argument("--off", type=float, default=3.0, help="rest seconds between cues")
    ap.add_argument("--banner", default="", help='big text at the top, e.g. "REPLAY" when no headset is live')
    ap.add_argument("--tree", action="store_true", help="phrase mode: two looks per phrase (phrase_tree.py)")
    ap.add_argument("--tree-timeout", type=float, default=10.0, help="s to make the second look before going back to groups")
    ap.add_argument("--settle", type=float, default=3.0, help="phrase mode: ignore picks this soon after a group opens")
    ap.add_argument("--phrase-log", help="CSV of phrase-mode events, for looks-per-message and errors")
    ap.add_argument("--speak", action="store_true",
                    help="phrase mode: the Mac says each finished phrase aloud (macOS `say`); the output when there is no wristband")
    a = ap.parse_args()
    if a.tree and a.trials:
        sys.exit("--tree and --trials do not mix: calibrate and test with fixed tiles, then use --tree")
    if a.tree and a.tree_timeout < a.settle + 2:
        sys.exit(f"--tree-timeout ({a.tree_timeout:g} s) must be at least --settle + 2 s ({a.settle + 2:g} s), "
                 "or there is no time left to make the second look")

    tree = PhraseTree(timeout_s=a.tree_timeout) if a.tree else None
    said, said_t, history = None, -1e9, []   # last phrase, when, and the last few for the carer bar
    plog = None
    t_start = time.monotonic()
    if a.phrase_log:
        plog = open(a.phrase_log, "w")
        plog.write("t,event,tile,text\n")

    def log_event(event, tile, text=""):
        if plog:
            plog.write(f"{time.monotonic() - t_start:.2f},{event},{'' if tile is None else tile},\"{text}\"\n")
            plog.flush()

    pygame.init()
    screen = pygame.display.set_mode((1280, 800), pygame.RESIZABLE, vsync=1)
    pygame.display.set_caption("SSVEP cue remote")
    font = pygame.font.SysFont("Avenir Next", 40)
    mid = pygame.font.SysFont("Avenir Next", 30)
    big = pygame.font.SysFont("Avenir Next", 56, bold=True)
    small = pygame.font.SysFont("Menlo", 20)
    clock = pygame.time.Clock()

    def fit(text, width, colour):
        """Render text in the big tile font, or the smaller one if it would overflow the tile."""
        img = font.render(text, True, colour)
        return img if img.get_width() <= width else mid.render(text, True, colour)

    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.bind(("127.0.0.1", 5005))
    rx.setblocking(False)
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(msg):
        tx.sendto(msg.encode(), ("127.0.0.1", 5006))

    pick = None
    pick_t = 0.0
    frame = 0
    full = False
    # trial state
    order = [i % 4 for i in range(a.trials)]
    random.shuffle(order)
    cued = None
    next_change = time.monotonic() + a.off
    done = 0

    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                elif e.key == pygame.K_f:
                    full = not full
                    screen = pygame.display.set_mode((0, 0) if full else (1280, 800),
                                                     (pygame.FULLSCREEN if full else pygame.RESIZABLE), vsync=1)
        try:
            while True:
                msg, _ = rx.recvfrom(64)
                parts = msg.decode().split()
                if parts[0] == "pick":
                    pick = None if parts[1] == "none" else int(parts[1])
                    pick_t = time.monotonic()
                    if tree is not None and pick is not None:
                        if tree.group is not None and pick_t - tree.opened_t < a.settle:
                            # too soon after the first look: the decoder window still holds it
                            log_event("ignored", pick, "settle")
                            pick = None
                        else:
                            phrase = tree.select(pick, pick_t)
                            if phrase is None:  # this pick opened a group
                                log_event("open", pick, tree.tree[pick][0])
                            else:
                                g, p = tree.path(phrase)
                                said, said_t = phrase, pick_t
                                history = ([phrase] + history)[:3]
                                send(f"phrase {g} {p}")
                                log_event("say", pick, phrase)
                                print(f"SAID: {phrase}", flush=True)
                                if a.speak:
                                    subprocess.Popen(["say", phrase])
        except BlockingIOError:
            pass

        now = time.monotonic()
        if tree is not None and tree.tick(now):
            log_event("timeout", None)
        if a.trials and done < a.trials and now >= next_change:
            if cued is None:
                cued = order[done]
                send(f"cue {cued}")
                next_change = now + a.on
            else:
                send("rest")
                cued = None
                done += 1
                next_change = now + a.off

        w, h = screen.get_size()
        screen.fill((0, 0, 0))
        bar = 130 if tree is not None else 0     # carer bar at the bottom in phrase mode
        tw, th = w // 2 - 60, (h - bar) // 2 - 60
        labels = tree.labels() if tree is not None else [t[0] for t in TILES]
        for i, (_, period, col) in enumerate(TILES):
            on = (frame % period) < (period + 1) // 2
            x = 40 + (i % 2) * (tw + 40)
            y = 40 + (i // 2) * (th + 40)
            rect = pygame.Rect(x, y, tw, th)
            pygame.draw.rect(screen, col if on else (20, 20, 20), rect, border_radius=24)
            if cued == i:
                pygame.draw.rect(screen, (255, 255, 255), rect, width=12, border_radius=24)
            if pick == i and now - pick_t < 1.5:
                pygame.draw.rect(screen, (255, 255, 0), rect.inflate(-30, -30), width=8, border_radius=18)
            colour = (255, 255, 255) if on else (90, 90, 90)
            if tree is None:
                txt = font.render(f"{labels[i]}  {FREQS[i]:.2f} Hz", True, colour)
                screen.blit(txt, txt.get_rect(center=rect.center))
            else:
                txt = fit(labels[i], tw - 40, colour)
                screen.blit(txt, txt.get_rect(center=rect.center))
                hz = small.render(f"{FREQS[i]:.2f} Hz", True, colour)
                screen.blit(hz, hz.get_rect(midtop=(rect.centerx, rect.centery + 34)))
        if tree is not None:
            top = h - bar - 10
            screen.blit(small.render(tree.prompt(now), True, (160, 160, 160)), (40, top))
            if now - said_t < 15:
                msg = big.render(said, True, (255, 230, 0))
                screen.blit(msg, (40, top + 30))
            if history[1:]:
                old = small.render("before: " + "  |  ".join(history[1:]), True, (110, 110, 110))
                screen.blit(old, (40, h - 56))
        info = f"frame {frame}  fps {clock.get_fps():4.1f}  " + (f"trial {done + 1}/{a.trials}" if a.trials else "free mode")
        screen.blit(small.render(info, True, (120, 120, 120)), (10, h - 28))
        if a.banner:
            b = font.render(a.banner, True, (255, 60, 60))
            screen.blit(b, b.get_rect(midtop=(w // 2, 4)))
        pygame.display.flip()
        frame += 1
        clock.tick(60)
    pygame.quit()


if __name__ == "__main__":
    main()
