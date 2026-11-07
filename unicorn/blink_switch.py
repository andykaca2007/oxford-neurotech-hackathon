"""Blink switch: a deliberate blink on Fz selects the highlighted tile. No flicker anywhere.

    .venv/bin/python unicorn/ssvep_stim.py --spell --tiles 12 --scan 1.0 --speak   (screen)
    .venv/bin/python unicorn/blink_switch.py --lsl [--uv 150] [--log blinks.csv]      (this)
    .venv/bin/python unicorn/blink_switch.py --fake                                   (no headset)

Fz is band-passed 0.5 to 8 Hz and read signed (blinks are positive at Fz). A blink is a deflection beyond --uv that lasts between
--min-ms and --max-ms (spontaneous blinks are short and small; a deliberate one is longer
and bigger). Each accepted blink sends "sel" to the screen (UDP 5005). Every blink,
accepted or not, is logged with its size and length: that log is the training set for the
deliberate-vs-spontaneous classifier.

The rule below is a threshold; the ML version (tonight) fits a small classifier on the
logged (amplitude, duration, time-since-last) features with held-out people.
"""
import argparse
import socket
import sys
import time

import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi

FS = 250


def src_fake():
    rng = np.random.default_rng(0)
    n = 0
    while True:
        t = n / FS
        v = rng.normal(0, 15)
        local = t % 3.0
        if 1.0 <= local < 1.35:            # a deliberate blink every 3 s, 350 ms
            v += 350 * np.sin(np.pi * (local - 1.0) / 0.35)
        if 2.2 <= local < 2.32:            # a spontaneous one: short and small
            v += 90 * np.sin(np.pi * (local - 2.2) / 0.12)
        yield t, v
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
        yield ts - t0, smp[0]   # Fz


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--lsl", action="store_true")
    g.add_argument("--fake", action="store_true")
    ap.add_argument("--uv", type=float, default=150.0, help="deflection that starts a blink")
    ap.add_argument("--min-ms", type=float, default=180, help="shorter than this = spontaneous, ignored")
    ap.add_argument("--max-ms", type=float, default=700, help="longer than this = eye closure, ignored")
    ap.add_argument("--refractory", type=float, default=1.0, help="s after an accepted blink before the next")
    ap.add_argument("--polarity", type=int, default=1, choices=[1, -1], help="-1 if blinks come out negative on this montage")
    ap.add_argument("--log")
    a = ap.parse_args()

    sos = butter(2, [0.5, 8], btype="band", fs=FS, output="sos")  # 0.5 Hz keeps a 300 ms blink as one positive lobe
    zi = sosfilt_zi(sos) * 0
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    log = open(a.log, "w") if a.log else None
    if log:
        log.write("t,peak_uv,dur_ms,since_last_s,accepted\n")

    inside, start, peak = False, 0.0, 0.0
    armed = False   # above half threshold: where the duration clock starts
    last_sel, last_blink = -1e9, -1e9
    n_acc = n_rej = 0
    print("# blink switch running; blink deliberately to select", flush=True)
    try:
        for t, raw in (src_fake() if a.fake else src_lsl()):
            y, zi = sosfilt(sos, [raw], zi=zi)
            v = float(y[0]) * a.polarity   # blinks are positive at Fz against the mastoids
            if not inside and not armed and v > a.uv * 0.5:
                armed, start = True, t
            if armed and not inside and v > a.uv:
                inside, peak = True, v
            if armed and v < a.uv * 0.5:
                armed = False
                if not inside:
                    continue          # never reached the full threshold: not a blink
                inside = False
                if True:
                    dur = (t - start) * 1000
                    ok = a.min_ms <= dur <= a.max_ms and t - last_sel > a.refractory
                    if log:
                        log.write(f"{t:.2f},{peak:.0f},{dur:.0f},{t - last_blink:.2f},{int(ok)}\n")
                        log.flush()
                    last_blink = t
                    if ok:
                        last_sel = t
                        n_acc += 1
                        tx.sendto(b"sel", ("127.0.0.1", 5005))
                        print(f"t={t:6.1f} BLINK {peak:4.0f} uV {dur:3.0f} ms -> select", flush=True)
                    else:
                        n_rej += 1
                        print(f"t={t:6.1f} blink {peak:4.0f} uV {dur:3.0f} ms ignored", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        print(f"\n# accepted {n_acc}, ignored {n_rej}")
        if log:
            log.close()


if __name__ == "__main__":
    main()
