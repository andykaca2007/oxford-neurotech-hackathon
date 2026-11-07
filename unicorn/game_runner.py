"""Head Runner: a side-scrolling runner you play with your face.

    .venv/bin/python unicorn/game_runner.py            # then cmd_switch.py --lsl or --fake in another terminal

Clench your jaw to JUMP over the low blocks. Long blink to DUCK under the high bars.
Keys fake the commands for a demo without a headset: UP or SPACE = clench, DOWN = blink.
Listens on UDP 5007 for "cmd clench" / "cmd blink". Esc quits, R restarts, F fullscreen.

Speed rises slowly with distance. --speed sets the start. The score is distance; the game
also counts obstacles cleared and hits, printed at the end for the slide.
"""
import argparse
import random
import socket
import time

import pygame

W, H = 1280, 720
GROUND = 560


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--speed", type=float, default=6.0, help="start speed, pixels per frame at 60 fps")
    ap.add_argument("--banner", default="")
    a = ap.parse_args()

    pygame.init()
    screen = pygame.display.set_mode((W, H), pygame.RESIZABLE, vsync=1)
    pygame.display.set_caption("Head Runner")
    font = pygame.font.SysFont("Avenir Next", 36)
    big = pygame.font.SysFont("Avenir Next", 72, bold=True)
    small = pygame.font.SysFont("Menlo", 18)
    clock = pygame.time.Clock()

    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.bind(("127.0.0.1", 5007))
    rx.setblocking(False)

    def reset():
        return dict(x=160, y=GROUND, vy=0.0, duck_until=0.0, dist=0.0, speed=a.speed,
                    obstacles=[], next_ob=W + 200, cleared=0, hits=0, alive=True, flash=0.0,
                    last_cmd="", last_cmd_t=0.0, started=time.monotonic())

    g = reset()
    full = False
    running = True
    while running:
        now = time.monotonic()
        cmd = None
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                elif e.key == pygame.K_r:
                    g = reset()
                elif e.key == pygame.K_f:
                    full = not full
                    screen = pygame.display.set_mode((0, 0) if full else (W, H),
                                                     (pygame.FULLSCREEN if full else pygame.RESIZABLE), vsync=1)
                elif e.key in (pygame.K_UP, pygame.K_SPACE):
                    cmd = "clench"
                elif e.key == pygame.K_DOWN:
                    cmd = "blink"
        try:
            while True:
                msg, _ = rx.recvfrom(64)
                p = msg.decode().split()
                if p[0] == "cmd":
                    cmd = p[1]
        except BlockingIOError:
            pass

        if cmd and g["alive"]:
            g["last_cmd"], g["last_cmd_t"] = cmd, now
            if cmd == "clench" and g["y"] >= GROUND:
                g["vy"] = -19.0
            elif cmd == "blink":
                g["duck_until"] = now + 0.9

        if g["alive"]:
            # physics
            g["vy"] += 0.9
            g["y"] = min(GROUND, g["y"] + g["vy"])
            if g["y"] >= GROUND:
                g["vy"] = 0.0
            g["dist"] += g["speed"]
            g["speed"] = a.speed + g["dist"] / 6000
            # obstacles
            g["next_ob"] -= g["speed"]
            if g["next_ob"] <= 0:
                kind = random.choice(["low", "low", "high"])
                g["obstacles"].append(dict(x=W + 60, kind=kind, passed=False))
                g["next_ob"] = random.uniform(2.2, 3.4) * 60 * g["speed"] / 6.0
            ducking = now < g["duck_until"]
            ph = 50 if ducking else 100
            player = pygame.Rect(g["x"] - 25, g["y"] - ph, 50, ph)
            for ob in g["obstacles"]:
                ob["x"] -= g["speed"]
                if ob["kind"] == "low":
                    r = pygame.Rect(ob["x"], GROUND - 55, 45, 55)
                else:
                    r = pygame.Rect(ob["x"], GROUND - 140, 45, 60)   # bar you must duck under
                if not ob["passed"] and ob["x"] + 45 < g["x"] - 25:
                    ob["passed"] = True
                    g["cleared"] += 1
                if player.colliderect(r):
                    g["hits"] += 1
                    g["flash"] = now + 0.4
                    ob["passed"] = True
                    ob["x"] = -999
                    if g["hits"] >= 3:
                        g["alive"] = False
            g["obstacles"] = [o for o in g["obstacles"] if o["x"] > -100]

        # draw
        w, h = screen.get_size()
        screen.fill((12, 12, 16) if now > g["flash"] else (90, 20, 20))
        pygame.draw.rect(screen, (40, 40, 48), (0, GROUND, w, h - GROUND))
        for i in range(0, w, 80):
            xx = (i - int(g["dist"]) % 80)
            pygame.draw.rect(screen, (60, 60, 70), (xx, GROUND, 40, 6))
        ducking = now < g["duck_until"]
        ph = 50 if ducking else 100
        pygame.draw.rect(screen, (80, 200, 120), (g["x"] - 25, g["y"] - ph, 50, ph), border_radius=10)
        pygame.draw.circle(screen, (255, 255, 255), (g["x"] + 8, int(g["y"] - ph + 22)), 6)
        for ob in g["obstacles"]:
            if ob["kind"] == "low":
                pygame.draw.rect(screen, (240, 80, 80), (ob["x"], GROUND - 55, 45, 55), border_radius=6)
            else:
                pygame.draw.rect(screen, (250, 180, 60), (ob["x"], GROUND - 140, 45, 60), border_radius=6)
                pygame.draw.rect(screen, (120, 90, 30), (ob["x"] + 18, GROUND - 80, 9, 80))
        hud = font.render(f"distance {int(g['dist'] / 10)} m   cleared {g['cleared']}   hits {g['hits']}/3", True, (230, 230, 230))
        screen.blit(hud, (30, 24))
        if now - g["last_cmd_t"] < 0.6 and g["last_cmd"]:
            c = big.render("JUMP" if g["last_cmd"] == "clench" else "DUCK", True, (255, 230, 0))
            screen.blit(c, c.get_rect(center=(w // 2, 120)))
        legend = small.render("clench jaw = jump    long blink = duck    (keys: up/space, down)   R restart", True, (130, 130, 130))
        screen.blit(legend, (30, h - 34))
        if a.banner:
            b = font.render(a.banner, True, (255, 60, 60))
            screen.blit(b, b.get_rect(midtop=(w // 2, 60)))
        if not g["alive"]:
            over = big.render(f"run over: {int(g['dist'] / 10)} m, {g['cleared']} cleared", True, (255, 255, 255))
            screen.blit(over, over.get_rect(center=(w // 2, h // 2 - 40)))
            again = font.render("press R to run again", True, (200, 200, 200))
            screen.blit(again, again.get_rect(center=(w // 2, h // 2 + 30)))
        pygame.display.flip()
        clock.tick(60)
    print(f"# distance {int(g['dist'] / 10)} m, cleared {g['cleared']}, hits {g['hits']}, {time.monotonic() - g['started']:.0f} s")
    pygame.quit()


if __name__ == "__main__":
    main()
