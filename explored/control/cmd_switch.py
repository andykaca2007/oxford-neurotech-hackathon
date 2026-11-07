"""Head commands from the Unicorn stream: jaw CLENCH and deliberate BLINK -> UDP to a game.

    .venv/bin/python explored/control/cmd_switch.py --lsl [--log cmds.csv]
    .venv/bin/python explored/control/cmd_switch.py --fake            # synthetic clenches and blinks

Sends "cmd clench" / "cmd blink" to UDP 5007 (game_runner.py listens there), and with --keys
presses keys system-wide so Roblox (or any game) reacts: clench = Space (jump), blink = S.

Signals (both reliable on dry electrodes with poor contact):
  CLENCH: jaw muscle EMG, broadband 20 to 100 Hz, on every channel at once. Detected as the
          mean 20 to 100 Hz RMS over the live channels rising above --clench-x times its
          resting level for at least --clench-ms.
  BLINK:  Fz, 0.5 to 8 Hz, positive lobe above --blink-uv lasting --min-ms to --max-ms.
The first --calib seconds measure the resting EMG level: sit still, face relaxed.

Every event is logged with its features: that CSV trains the 3-class command classifier
(clench / blink / nothing) that replaces these thresholds.
"""
import argparse
import socket
import sys
import time

import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi

FS = 250
CH = ["Fz", "C3", "Cz", "C4", "Pz", "P3", "O1", "P4"]  # layout A


def src_fake():
    rng = np.random.default_rng(0)
    n = 0
    while True:
        t = n / FS
        x = rng.normal(0, 12, 8)
        local = t % 5.0
        if 1.0 <= local < 1.4:                      # clench: broadband burst everywhere
            x += rng.normal(0, 120, 8)
        if 3.0 <= local < 3.3:                      # deliberate blink on Fz
            x[0] += 350 * np.sin(np.pi * (local - 3.0) / 0.3)
        yield t, x
        n += 1
        if n % 25 == 0:
            time.sleep(0.1)


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
    ap.add_argument("--calib", type=float, default=5.0, help="s of rest to measure the EMG floor")
    ap.add_argument("--clench-x", type=float, default=4.0, help="EMG must rise this many times above rest")
    ap.add_argument("--clench-ms", type=float, default=150)
    ap.add_argument("--blink-uv", type=float, default=150.0)
    ap.add_argument("--min-ms", type=float, default=150)
    ap.add_argument("--max-ms", type=float, default=700)
    ap.add_argument("--refractory", type=float, default=0.8)
    ap.add_argument("--channels", default="", help="comma list for the EMG average; default = all channels that are not flat")
    ap.add_argument("--keys", action="store_true",
                    help="also press keys system-wide: clench = --clench-key, blink = --blink-key (for Roblox or any game; Terminal needs Accessibility permission)")
    ap.add_argument("--clench-key", default="space")
    ap.add_argument("--blink-key", default="s")
    ap.add_argument("--log")
    a = ap.parse_args()
    pag = None
    if a.keys:
        import pyautogui as pag
        pag.PAUSE = 0
        print(f"# key mode: clench -> {a.clench_key}, blink -> {a.blink_key}. Click the game window so it has focus.", flush=True)

    emg_sos = butter(4, [20, 100], btype="band", fs=FS, output="sos")
    emg_zi = [sosfilt_zi(emg_sos) * 0 for _ in range(8)]
    bl_sos = butter(2, [0.5, 8], btype="band", fs=FS, output="sos")
    bl_zi = sosfilt_zi(bl_sos) * 0
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    log = open(a.log, "w") if a.log else None
    if log:
        log.write("t,kind,peak,dur_ms,since_last_s\n")

    use = [CH.index(c.strip()) for c in a.channels.split(",")] if a.channels else None
    env = np.zeros(8)                 # per-channel EMG envelope (RMS, 50 ms)
    alpha = 1 - np.exp(-1 / (0.05 * FS))
    rest_vals, floor = [], None
    in_cl, cl_start, cl_peak = False, 0.0, 0.0
    armed, in_bl, bl_start, bl_peak = False, False, 0.0, 0.0
    last_cmd = -1e9
    n = {"clench": 0, "blink": 0}

    def emit(kind, t, peak, dur):
        nonlocal last_cmd
        if t - last_cmd < a.refractory:
            return
        last_cmd = t
        n[kind] += 1
        tx.sendto(f"cmd {kind}".encode(), ("127.0.0.1", 5007))
        if pag is not None:
            pag.press(a.clench_key if kind == "clench" else a.blink_key)
        print(f"t={t:6.1f} {kind.upper():6s} peak {peak:6.1f} dur {dur:4.0f} ms", flush=True)
        if log:
            log.write(f"{t:.2f},{kind},{peak:.1f},{dur:.0f},{t - last_cmd:.2f}\n")
            log.flush()

    print(f"# sit still and relax your face for {a.calib:.0f} s", flush=True)
    try:
        for t, x in (src_fake() if a.fake else src_lsl()):
            # EMG envelope
            for c in range(8):
                y, emg_zi[c] = sosfilt(emg_sos, [x[c]], zi=emg_zi[c])
                env[c] += alpha * (y[0] ** 2 - env[c])
            rms = np.sqrt(env)
            if use is None:
                live = rms > 1e-6
                level = rms[live].mean() if live.any() else 0.0
            else:
                level = rms[use].mean()
            if t < a.calib:
                rest_vals.append(level)
                continue
            if floor is None:
                floor = float(np.median(rest_vals)) + 1e-6
                print(f"# EMG rest floor {floor:.1f} uV; clench threshold {a.clench_x * floor:.1f} uV", flush=True)
            # clench
            if not in_cl and level > a.clench_x * floor:
                in_cl, cl_start, cl_peak = True, t, level
            elif in_cl:
                cl_peak = max(cl_peak, level)
                if level < 2.0 * floor:
                    in_cl = False
                    dur = (t - cl_start) * 1000
                    if dur >= a.clench_ms:
                        emit("clench", t, cl_peak / floor, dur)
            # blink on Fz (skipped while clenching: EMG leaks into Fz)
            y, bl_zi = sosfilt(bl_sos, [x[0]], zi=bl_zi)
            v = float(y[0])
            if not in_cl:
                if not in_bl and not armed and v > a.blink_uv * 0.5:
                    armed, bl_start = True, t
                if armed and not in_bl and v > a.blink_uv:
                    in_bl, bl_peak = True, v
                if armed and v < a.blink_uv * 0.5:
                    armed = False
                    if in_bl:
                        in_bl = False
                        dur = (t - bl_start) * 1000
                        if a.min_ms <= dur <= a.max_ms:
                            emit("blink", t, bl_peak, dur)
    except KeyboardInterrupt:
        pass
    finally:
        print(f"\n# clenches {n['clench']}, blinks {n['blink']}")
        if log:
            log.close()


if __name__ == "__main__":
    main()
