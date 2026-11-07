"""Brain-steered robot arena: four dim pulsing patches at the screen edges, a robot in the middle.

    .venv/bin/python explored/control/arena.py                 # then ssvep_decode.py --lsl ... (picks arrive on UDP 5005)
    .venv/bin/python explored/control/arena.py --banner REPLAY  # with replay_demo.py

Patches flicker at the 4-tile rates (7.5, 8.57, 10, 12 Hz at a locked 60 Hz display), but
gently: a dim grey pulse, not full on/off, and only around the edges, so the arena in the
middle stays calm. Looking at a patch sends the robot that way:
    top = forward 1 step    bottom = reverse    left / right = turn 90 degrees then step
A "cand i" from the decoder (blink-confirm mode) draws an orange ring on that patch; the
robot only moves on "pick i". Keys fake looks for a demo without a headset: arrows.

The course: reach the green goal. Each run logs picks, hits and time; press R to restart.
"""
import argparse
import math
import random
import socket
import sys
import os
import time

import pygame

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tiles import tile_set  # noqa: E402

W, H = 1280, 800
CELL = 70
GRID_W, GRID_H = 11, 7
DIRS = [(0, -1), (0, 1), (-1, 0), (1, 0)]      # tile 0 top, 1 bottom, 2 left, 3 right


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--banner", default="")
    ap.add_argument("--contrast", type=float, default=0.45, help="0 to 1: how strongly the patches pulse (gentle = 0.45)")
    a = ap.parse_args()

    ts = tile_set(4)
    periods = ts["periods"]
    pygame.init()
    screen = pygame.display.set_mode((W, H), pygame.RESIZABLE, vsync=1)
    pygame.display.set_caption("Brain-steered robot")
    font = pygame.font.SysFont("Avenir Next", 30)
    big = pygame.font.SysFont("Avenir Next", 60, bold=True)
    small = pygame.font.SysFont("Menlo", 18)
    clock = pygame.time.Clock()
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.bind(("127.0.0.1", 5005))
    rx.setblocking(False)

    def new_run():
        walls = set()
        for _ in range(10):
            walls.add((random.randrange(1, GRID_W - 1), random.randrange(0, GRID_H)))
        walls.discard((0, GRID_H // 2))
        walls.discard((GRID_W - 1, GRID_H // 2))
        return dict(rx=0, ry=GRID_H // 2, heading=3, walls=walls, goal=(GRID_W - 1, GRID_H // 2),
                    picks=0, bumps=0, t0=time.monotonic(), done_t=None, last="", last_t=0.0)

    g = new_run()
    cand = None
    frame = 0
    full = False
    running = True

    def move(tile):
        nonlocal g
        g["picks"] += 1
        g["last"], g["last_t"] = ["FORWARD", "BACK", "LEFT", "RIGHT"][tile], time.monotonic()
        if tile in (2, 3):
            turn = -1 if tile == 2 else 1
            order = [0, 3, 1, 2]                      # up, right, down, left (clockwise)
            g["heading"] = order[(order.index(g["heading"]) + turn) % 4]
            dx, dy = DIRS[g["heading"]]
        else:
            dx, dy = DIRS[g["heading"]]
            if tile == 1:
                dx, dy = -dx, -dy
        nx, ny = g["rx"] + dx, g["ry"] + dy
        if 0 <= nx < GRID_W and 0 <= ny < GRID_H and (nx, ny) not in g["walls"]:
            g["rx"], g["ry"] = nx, ny
        else:
            g["bumps"] += 1
        if (g["rx"], g["ry"]) == g["goal"] and g["done_t"] is None:
            g["done_t"] = time.monotonic()

    while running:
        now = time.monotonic()
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                elif e.key == pygame.K_r:
                    g = new_run()
                elif e.key == pygame.K_f:
                    full = not full
                    screen = pygame.display.set_mode((0, 0) if full else (W, H),
                                                     (pygame.FULLSCREEN if full else pygame.RESIZABLE), vsync=1)
                elif e.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT):
                    move([pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT].index(e.key))
        try:
            while True:
                msg, _ = rx.recvfrom(64)
                p = msg.decode().split()
                if p[0] == "cand":
                    cand = None if p[1] == "none" else int(p[1])
                elif p[0] == "pick":
                    cand = None
                    if p[1] != "none":
                        move(int(p[1]))
        except BlockingIOError:
            pass

        w, h = screen.get_size()
        screen.fill((10, 10, 14))
        # patches: top, bottom, left, right
        pad, thick = 40, 90
        rects = [pygame.Rect(w // 2 - 220, pad, 440, thick), pygame.Rect(w // 2 - 220, h - pad - thick, 440, thick),
                 pygame.Rect(pad, h // 2 - 140, thick, 280), pygame.Rect(w - pad - thick, h // 2 - 140, thick, 280)]
        names = ["FORWARD", "BACK", "LEFT", "RIGHT"]
        for i, r in enumerate(rects):
            on = (frame % periods[i]) < (periods[i] + 1) // 2
            lo, hi = 35, int(35 + 200 * a.contrast)
            v = hi if on else lo
            pygame.draw.rect(screen, (v, v, v), r, border_radius=18)
            if cand == i:
                pygame.draw.rect(screen, (255, 140, 0), r.inflate(14, 14), width=6, border_radius=22)
            if now - g["last_t"] < 0.8 and g["last"] == names[i]:
                pygame.draw.rect(screen, (255, 230, 0), r.inflate(14, 14), width=6, border_radius=22)
            lbl = small.render(names[i], True, (140, 140, 140))
            screen.blit(lbl, lbl.get_rect(center=r.center))
        # arena
        ox, oy = (w - GRID_W * CELL) // 2, (h - GRID_H * CELL) // 2
        for gx in range(GRID_W):
            for gy in range(GRID_H):
                r = pygame.Rect(ox + gx * CELL, oy + gy * CELL, CELL - 2, CELL - 2)
                colour = (60, 60, 70) if (gx, gy) in g["walls"] else (22, 22, 28)
                pygame.draw.rect(screen, colour, r, border_radius=6)
        gxg, gyg = g["goal"]
        pygame.draw.rect(screen, (40, 160, 90), (ox + gxg * CELL, oy + gyg * CELL, CELL - 2, CELL - 2), border_radius=6)
        cx, cy = ox + g["rx"] * CELL + CELL // 2, oy + g["ry"] * CELL + CELL // 2
        pygame.draw.circle(screen, (80, 160, 255), (cx, cy), 24)
        dx, dy = DIRS[g["heading"]]
        pygame.draw.line(screen, (255, 255, 255), (cx, cy), (cx + dx * 26, cy + dy * 26), 5)
        hud = font.render(f"looks {g['picks']}   bumps {g['bumps']}   {now - g['t0']:.0f} s", True, (220, 220, 220))
        screen.blit(hud, (pad, pad + thick + 10))
        if g["done_t"]:
            msg = big.render(f"GOAL in {g['picks']} looks, {g['done_t'] - g['t0']:.0f} s", True, (120, 255, 160))
            screen.blit(msg, msg.get_rect(center=(w // 2, h // 2)))
        legend = small.render("look at an edge patch to steer (keys: arrows)   R new course   F fullscreen", True, (110, 110, 110))
        screen.blit(legend, (pad, h - 26))
        if a.banner:
            b = font.render(a.banner, True, (255, 60, 60))
            screen.blit(b, b.get_rect(midtop=(w // 2, pad + thick + 10)))
        pygame.display.flip()
        frame += 1
        clock.tick(ts["refresh"])
    print(f"# run: {g['picks']} looks, {g['bumps']} bumps, goal {'reached' if g['done_t'] else 'not reached'}")
    pygame.quit()


if __name__ == "__main__":
    main()
