"""Live mental-load gauge with a personal baseline and an alarm.

    .venv/bin/python unicorn/load_gauge.py --lsl [--log shift.csv]      # headset via unicorn_gpype.py
    .venv/bin/python unicorn/load_gauge.py --fake                        # no headset: rest, then load after 45 s
    add --no-ui for a text readout only

Protocol: the first --baseline seconds (default 30) the person sits quietly: that is their
own calm, and every later reading is relative to it (readiness_model.py showed this lifts
held-out detection from 63 to 70 percent). Then a 4 s window every second goes through the
same features and the trained classifier (models/readiness.joblib); the gauge shows a
smoothed probability of "under load" as 0 to 100. When it stays above --alarm for --hold
seconds the screen goes red and the Mac speaks. Keys: B redo the baseline, Esc quit.

Output rows: t, load_pct, alarm, then the 17 features. Honest reading of the number: how much
this brain looks like the public "doing arithmetic" recordings versus its own rest; not sleepiness,
not risk. Needs Fz, C3, Cz, C4, Pz alive.
"""
import argparse
import os
import subprocess
import sys
import time
from collections import deque

import joblib
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from readiness_model import CH, features  # noqa: E402

FS = 250
IDX = [0, 1, 2, 3, 4]   # Fz C3 Cz C4 Pz in the Core-8 stream


def src_fake(seed=0):
    """Rest for 45 s (strong alpha at Pz/Cz), then load (frontal theta up, alpha down)."""
    rng = np.random.default_rng(seed)
    n = 0
    while True:
        t = n / FS
        x = rng.normal(0, 8, 8)
        load = t > 45
        a_amp = 6 if load else 14
        th_amp = 10 if load else 3
        x[4] += a_amp * np.sin(2 * np.pi * 10 * t)
        x[2] += 0.6 * a_amp * np.sin(2 * np.pi * 10 * t + 1)
        x[0] += th_amp * np.sin(2 * np.pi * 6 * t)
        yield t, x
        n += 1
        if n % 50 == 0:
            time.sleep(0.2 / 1.0 * 1.0 / 1.0 * 0.2)   # ~5x real time for a quick test


def src_lsl():
    from pylsl import StreamInlet, resolve_byprop
    s = resolve_byprop("name", "Unicorn", timeout=10)
    if not s:
        sys.exit("no LSL stream named Unicorn: start unicorn_gpype.py first")
    inlet = StreamInlet(s[0])
    t0 = None
    while True:
        smp, ts = inlet.pull_sample()
        if t0 is None:
            t0 = ts
        yield ts - t0, np.array(smp[:8])


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--lsl", action="store_true")
    g.add_argument("--fake", action="store_true")
    ap.add_argument("--model", default="models/readiness.joblib")
    ap.add_argument("--baseline", type=float, default=30.0)
    ap.add_argument("--alarm", type=float, default=70.0, help="load percent that triggers the alarm")
    ap.add_argument("--hold", type=float, default=20.0, help="s above --alarm before it fires")
    ap.add_argument("--smooth", type=float, default=8.0, help="s of smoothing on the gauge")
    ap.add_argument("--log")
    ap.add_argument("--no-ui", action="store_true")
    ap.add_argument("--web", action="store_true", help="post state to gauge_server.py (http://localhost:8765) every second")
    ap.add_argument("--web-port", type=int, default=8765)
    ap.add_argument("--seconds", type=float, default=0)
    a = ap.parse_args()

    m = joblib.load(a.model)
    clf = m["model"]
    win = int(m["epoch_s"] * FS)
    buf = deque(maxlen=win)
    base_feats, base = [], None
    ema, above_since, alarmed = None, None, False
    log = open(a.log, "w") if a.log else None
    if log:
        log.write("t,load_pct,alarm," + ",".join(f"f{i}" for i in range(17)) + "\n")

    ui = None
    if not a.no_ui:
        import pygame
        pygame.init()
        screen = pygame.display.set_mode((1100, 640), pygame.RESIZABLE, vsync=1)
        pygame.display.set_caption("Mental load")
        font = pygame.font.SysFont("Avenir Next", 34)
        huge = pygame.font.SysFont("Avenir Next", 150, bold=True)
        small = pygame.font.SysFont("Menlo", 18)
        ui = dict(pygame=pygame, screen=screen, font=font, huge=huge, small=small, hist=deque(maxlen=600))

    def speak(txt):
        subprocess.Popen(["say", txt])

    state = "BASELINE: sit still, eyes open, 30 s"
    hist = deque(maxlen=600)
    import json, urllib.request

    def post_state(t_now):
        if not a.web:
            return
        body = json.dumps(dict(t=round(t_now, 1), state=state, load=round(load_pct, 1), alarm=bool(alarmed),
                               baseline_done=base is not None, baseline_s=a.baseline,
                               baseline_progress=min(1.0, len(base_feats) / a.baseline) if base is None else 1.0,
                               hist=list(hist))).encode()
        try:
            urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{a.web_port}/state", data=body,
                                                          headers={"Content-Type": "application/json"}), timeout=0.3)
        except Exception:
            pass
    next_eval = 0.0
    load_pct = 0.0
    t = 0.0
    print(f"# {state}", flush=True)
    try:
        for t, x in (src_fake() if a.fake else src_lsl()):
            if a.seconds and t > a.seconds:
                break
            buf.append(x[IDX])
            if ui is not None:
                for e in ui["pygame"].event.get():
                    if e.type == ui["pygame"].QUIT:
                        raise KeyboardInterrupt
                    if e.type == ui["pygame"].KEYDOWN:
                        if e.key == ui["pygame"].K_ESCAPE:
                            raise KeyboardInterrupt
                        if e.key == ui["pygame"].K_b:
                            base_feats, base, ema, alarmed, above_since = [], None, None, False, None
                            state = "BASELINE: sit still, eyes open, 30 s"
                            print("# re-baselining", flush=True)
            if len(buf) < win or t < next_eval:
                if ui is not None and t >= next_eval - 0.9:
                    pass
                continue
            next_eval = t + 1.0
            f = features(np.array(buf).T, FS)
            if base is None:
                base_feats.append(f)
                if len(base_feats) * 1.0 >= a.baseline:
                    base = np.mean(base_feats, axis=0)
                    state = "monitoring"
                    print("# baseline done", flush=True)
                    speak("Baseline done")
                load_pct = 0.0
                post_state(t)
            else:
                p = float(clf.predict_proba((f - base)[None, :])[0, 1])
                ema = p if ema is None else ema + (p - ema) * (1.0 / a.smooth)
                load_pct = 100 * ema
                if load_pct >= a.alarm:
                    above_since = above_since or t
                    if not alarmed and t - above_since >= a.hold:
                        alarmed = True
                        print(f"t={t:6.1f} ALARM load {load_pct:.0f}", flush=True)
                        speak("High mental load. Take a break.")
                else:
                    above_since, alarmed = None, False
                if log:
                    log.write(f"{t:.1f},{load_pct:.1f},{int(alarmed)}," + ",".join(f"{v:.3f}" for v in f) + "\n")
                    log.flush()
                hist.append(round(load_pct, 1))
                post_state(t)
                if a.no_ui or int(t) % 5 == 0:
                    print(f"t={t:6.1f} load {load_pct:5.1f}  raw p {p:.2f}  {'ALARM' if alarmed else ''}", flush=True)
            if ui is not None:
                pg, sc = ui["pygame"], ui["screen"]
                ui["hist"].append(load_pct)
                w, h = sc.get_size()
                sc.fill((110, 20, 20) if alarmed else (12, 12, 16))
                title = ui["font"].render(state, True, (200, 200, 200))
                sc.blit(title, (40, 30))
                if base is not None:
                    col = (240, 80, 80) if load_pct >= a.alarm else ((250, 180, 60) if load_pct >= a.alarm - 20 else (80, 200, 120))
                    num = ui["huge"].render(f"{load_pct:.0f}", True, col)
                    sc.blit(num, num.get_rect(center=(w // 2, h // 2 - 60)))
                    lbl = ui["font"].render("mental load, 0 to 100, relative to your own baseline", True, (150, 150, 150))
                    sc.blit(lbl, lbl.get_rect(center=(w // 2, h // 2 + 50)))
                    pg.draw.rect(sc, (40, 40, 48), (40, h - 140, w - 80, 90), border_radius=8)
                    pts = [(40 + i * (w - 80) / 600, h - 50 - v * 0.9) for i, v in enumerate(ui["hist"])]
                    if len(pts) > 1:
                        pg.draw.lines(sc, (200, 200, 200), False, pts, 2)
                    ya = h - 50 - a.alarm * 0.9
                    pg.draw.line(sc, (240, 80, 80), (40, ya), (w - 40, ya), 1)
                    if alarmed:
                        al = ui["font"].render("HIGH LOAD: take a break", True, (255, 255, 255))
                        sc.blit(al, al.get_rect(center=(w // 2, h // 2 + 100)))
                else:
                    done = min(len(base_feats), a.baseline)
                    pg.draw.rect(sc, (60, 60, 70), (w // 2 - 250, h // 2, 500, 30), border_radius=8)
                    pg.draw.rect(sc, (80, 200, 120), (w // 2 - 250, h // 2, int(500 * done / a.baseline), 30), border_radius=8)
                foot = ui["small"].render("B = redo baseline   Esc = quit", True, (110, 110, 110))
                sc.blit(foot, (40, h - 28))
                pg.display.flip()
    except KeyboardInterrupt:
        pass
    finally:
        if log:
            log.close()
        if ui is not None:
            ui["pygame"].quit()
        print(f"# stopped at t={t:.0f} s, last load {load_pct:.0f}")


if __name__ == "__main__":
    main()
