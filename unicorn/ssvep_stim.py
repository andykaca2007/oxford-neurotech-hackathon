# /// script
# requires-python = ">=3.10"
# dependencies = ["pygame"]
# ///
"""SSVEP cue remote: four flickering tiles. Look at one, the decoder picks it.

    uv run unicorn/ssvep_stim.py                 # free mode: tiles flicker, decoder highlights its pick
    uv run unicorn/ssvep_stim.py --trials 12     # trial mode: cues a tile (white border) for --on s,
                                                 # rests --off s, repeats; the decoder logs cued vs picked

Lock the MacBook display to 60 Hz first (System Settings > Displays > Refresh rate),
or the flicker frequencies are wrong. Press F for fullscreen, Esc to quit.

Frequencies are frame-locked: 60 / period_frames. 8 frames = 7.5 Hz, 7 = 8.57 Hz,
6 = 10 Hz, 5 = 12 Hz. Half-periods are rounded (7 frames -> 4 on, 3 off), which is
the usual approximation and still peaks at 8.57 Hz.

Talks to ssvep_decode.py over UDP on localhost:
    5005 (decoder -> stim): "pick <i>" or "pick none"
    5006 (stim -> decoder): "cue <i>" at every cue onset, "rest" at every cue end
"""
import argparse
import random
import socket
import time

import pygame

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
    a = ap.parse_args()

    pygame.init()
    screen = pygame.display.set_mode((1280, 800), pygame.RESIZABLE, vsync=1)
    pygame.display.set_caption("SSVEP cue remote")
    font = pygame.font.SysFont("Avenir Next", 40)
    small = pygame.font.SysFont("Menlo", 20)
    clock = pygame.time.Clock()

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
        except BlockingIOError:
            pass

        now = time.monotonic()
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
        tw, th = w // 2 - 60, h // 2 - 60
        for i, (label, period, col) in enumerate(TILES):
            on = (frame % period) < (period + 1) // 2
            x = 40 + (i % 2) * (tw + 40)
            y = 40 + (i // 2) * (th + 40)
            rect = pygame.Rect(x, y, tw, th)
            pygame.draw.rect(screen, col if on else (20, 20, 20), rect, border_radius=24)
            if cued == i:
                pygame.draw.rect(screen, (255, 255, 255), rect, width=12, border_radius=24)
            if pick == i and now - pick_t < 1.5:
                pygame.draw.rect(screen, (255, 255, 0), rect.inflate(-30, -30), width=8, border_radius=18)
            txt = font.render(f"{label}  {FREQS[i]:.2f} Hz", True, (255, 255, 255) if on else (90, 90, 90))
            screen.blit(txt, txt.get_rect(center=rect.center))
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
