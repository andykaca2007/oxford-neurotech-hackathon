# /// script
# requires-python = ">=3.10"
# dependencies = ["pyserial", "matplotlib"]
# ///
"""Live demo screen for SwallowCue, for both signal paths.

Throat IMU board (planb_imu firmware) over USB serial:
    uv run tools/live_plot.py /dev/cu.usbserial-XXXX --log session1.csv
Chin EMG (live_emg/swallowcue_live.py running with --log emg1.csv):
    uv run tools/live_plot.py emg1.csv

Shows the last 20 s of the envelope and the burst threshold. Swallows get a
green band, other bursts grey, every buzz a red line; the title shows the
swallow count and time since the last one.

--log saves every line for tools/eval_session.py. While it runs, press Enter
in this terminal right after each swallow: that is the ground truth.
Typing a board command and Enter (b, t15, r, e, i) sends it to the ESP32.
On the EMG path press Enter in the swallowcue_live.py terminal instead.
Close the window to stop (the board keeps running).
"""
import os
import sys
import threading
import time
from collections import deque

import matplotlib.pyplot as plt
import serial

WINDOW_S = 20.0

args = sys.argv[1:]
log_path = None
if "--log" in args:
    i = args.index("--log")
    log_path = args[i + 1]
    del args[i:i + 2]
if not args:
    sys.exit("usage: uv run tools/live_plot.py <serial port | log file> [--log out.csv]")
source = args[0]
log = open(log_path, "w") if log_path else None
t_open = time.time()

if os.path.isfile(source):
    # Follow a growing log file (from swallowcue_live.py), like tail -f.
    class Tail:
        def __init__(self, path):
            self.f = open(path)
        def readline(self):
            line = self.f.readline()
            if not line:
                time.sleep(0.02)
            return line.encode()
    ser = Tail(source)
else:
    ser = serial.Serial(source, 115200, timeout=0.1)
samples = deque()          # (t, env, thr)
bursts = deque()           # (centre, dur, is_swallow)
cues = deque()             # t
state = {"swallows": 0, "last": None, "now": 0.0}
lock = threading.Lock()


def save(line):
    if log:
        log.write(line + "\n")
        log.flush()


def marks():
    # Empty Enter = "I just swallowed", stamped on the board's clock.
    # Anything else (b, t15, r, e, i) is passed to the board as a command.
    for typed in sys.stdin:
        cmd = typed.strip()
        if cmd and hasattr(ser, "write"):
            ser.write((cmd + "\n").encode())
            print(f"> sent {cmd!r} to the board", flush=True)
            continue
        with lock:
            t = state["now"] + 0.0
        save(f"M,{t:.2f}")
        print(f"M,{t:.2f}  (mark)", flush=True)


def reader():
    while True:
        line = ser.readline().decode(errors="ignore").strip()
        if not line:
            continue
        save(line)
        parts = line.split(",")
        with lock:
            try:
                if parts[0] == "S" and len(parts) == 4:
                    t = float(parts[1])
                    samples.append((t, float(parts[2]), float(parts[3])))
                    state["now"] = t
                elif parts[0] == "B" and len(parts) == 8:
                    sw = parts[7] == "SWALLOW"
                    bursts.append((float(parts[1]), float(parts[2]), sw))
                    if sw:
                        state["swallows"] += 1
                        state["last"] = float(parts[1])
                    print(line, flush=True)
                elif parts[0] == "C":
                    cues.append(float(parts[1]))
                    print(line, flush=True)
                elif line.startswith("#"):
                    print(line, flush=True)
            except ValueError:
                pass
            cut = state["now"] - WINDOW_S
            while samples and samples[0][0] < cut:
                samples.popleft()
            while bursts and bursts[0][0] < cut:
                bursts.popleft()
            while cues and cues[0] < cut:
                cues.popleft()


threading.Thread(target=reader, daemon=True).start()
threading.Thread(target=marks, daemon=True).start()

plt.ion()
fig, ax = plt.subplots(figsize=(11, 5))
(env_line,) = ax.plot([], [], lw=1.5, label="throat movement")
(thr_line,) = ax.plot([], [], lw=1, ls="--", color="0.4", label="burst threshold")
ax.set_xlabel("time (s)")
ax.set_ylabel("movement (g)")
ax.legend(loc="upper left")
title = ax.set_title("")

while plt.fignum_exists(fig.number):
    with lock:
        s = list(samples)
        b = list(bursts)
        c = list(cues)
        n, last, now = state["swallows"], state["last"], state["now"]
    if s:
        t = [x[0] for x in s]
        env_line.set_data(t, [x[1] for x in s])
        thr_line.set_data(t, [x[2] for x in s])
        ax.set_xlim(now - WINDOW_S, now)
        top = max(max(x[1] for x in s), max(x[2] for x in s)) * 1.3
        ax.set_ylim(0, max(top, 1e-3))
        for p in list(ax.patches) + [l for l in ax.lines if l not in (env_line, thr_line)]:
            p.remove()
        for centre, dur, sw in b:
            ax.axvspan(centre - dur / 2, centre + dur / 2, color="tab:green" if sw else "0.8", alpha=0.4)
        for tc in c:
            ax.axvline(tc, color="tab:red", lw=2)
        since = "none yet" if last is None else f"{now - last:.0f} s ago"
        title.set_text(f"swallows: {n}    last swallow: {since}")
    fig.canvas.draw_idle()
    plt.pause(0.05)
    time.sleep(0.01)
