"""Live view of the Unicorn LSL stream with typed amplitude and window, per-channel toggles.

    .venv/bin/python headset/live_view.py            # 1 to 40 Hz
    .venv/bin/python headset/live_view.py --raw      # unfiltered, shows DC drift

Boxes at the bottom: Amplitude in uV (blank or 0 = auto, each row fits its whole
trace), Window in seconds. Keys: 1 to 8 hide/show a channel, 0 shows all, a = auto.
Row label: name and band RMS in uV, green under 40 (good), amber under 100, red above.
A dead-flat row at 0 uV is an open input.
"""
import argparse
import time
from collections import deque

import matplotlib
matplotlib.use("MacOSX")
import matplotlib.pyplot as plt
from matplotlib.widgets import TextBox
import numpy as np
from pylsl import StreamInlet, resolve_byprop
from scipy.signal import butter, sosfilt, sosfilt_zi

FS = 250
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from montage import MONTAGE as CH  # noqa: E402
MAX_S = 30


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("--window", type=float, default=6.0)
    ap.add_argument("--amp", type=float, default=0.0, help="uV, 0 = auto")
    a = ap.parse_args()

    streams = resolve_byprop("name", "Unicorn", timeout=10)
    if not streams:
        raise SystemExit("no LSL stream named Unicorn: start unicorn_gpype.py first")
    inlet = StreamInlet(streams[0])
    sos = butter(4, [1, 40], btype="band", fs=FS, output="sos")
    zi = [sosfilt_zi(sos) * 0 for _ in range(8)]
    buf = [deque(maxlen=FS * MAX_S) for _ in range(8)]
    state = dict(win=a.window, amp=a.amp, shown=[True] * 8)

    for k in list(plt.rcParams):
        if k.startswith("keymap."):
            plt.rcParams[k] = []
    plt.ion()
    fig = plt.figure(figsize=(13, 9))
    fig.canvas.manager.set_window_title("Core-8 live")
    axes = [fig.add_axes([0.08, 0.1, 0.9, 0.1]) for _ in range(8)]
    lines, labels, ranges = [], [], []
    for i, ax in enumerate(axes):
        (ln,) = ax.plot([], [], lw=0.8, color="k")
        lines.append(ln)
        ax.set_yticks([])
        ax.axhline(0, color="#bbb", lw=0.5)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        labels.append(ax.text(-0.012, 0.5, CH[i], transform=ax.transAxes, ha="right", va="center", fontsize=12))
        ranges.append(ax.text(1.0, 0.97, "", transform=ax.transAxes, ha="right", va="top", fontsize=8, color="#666"))
    title = fig.text(0.5, 0.985, "", ha="center", va="top", fontsize=11)

    box_amp = TextBox(fig.add_axes([0.16, 0.015, 0.1, 0.035]), "Amplitude uV (0 = auto) ", initial=str(int(a.amp)))
    box_win = TextBox(fig.add_axes([0.42, 0.015, 0.08, 0.035]), "Window s ", initial=str(a.window))
    hint = fig.text(0.55, 0.03, "keys: 1 to 8 hide/show, 0 all, a auto", fontsize=9, color="#666")

    def relayout():
        vis = [i for i in range(8) if state["shown"][i]]
        for i, ax in enumerate(axes):
            ax.set_visible(state["shown"][i])
        h = 0.9 / max(1, len(vis))
        for k, i in enumerate(vis):
            axes[i].set_position([0.08, 0.075 + (len(vis) - 1 - k) * h, 0.9, h * 0.9])
            axes[i].tick_params(labelbottom=(k == len(vis) - 1))
        fig.canvas.draw_idle()

    def on_amp(text):
        try:
            state["amp"] = max(0.0, float(text or 0))
        except ValueError:
            box_amp.set_val("0")

    def on_win(text):
        try:
            state["win"] = min(MAX_S, max(1.0, float(text)))
        except ValueError:
            box_win.set_val(str(state["win"]))

    def on_key(ev):
        if ev.inaxes in (box_amp.ax, box_win.ax):
            return
        if ev.key in "12345678":
            i = int(ev.key) - 1
            state["shown"][i] = not state["shown"][i]
            relayout()
        elif ev.key == "0":
            state["shown"] = [True] * 8
            relayout()
        elif ev.key == "a":
            state["amp"] = 0.0
            box_amp.set_val("0")

    box_amp.on_submit(on_amp)
    box_win.on_submit(on_win)
    fig.canvas.mpl_connect("key_press_event", on_key)
    relayout()

    last_draw = 0.0
    while plt.fignum_exists(fig.number):
        chunk, _ = inlet.pull_chunk(timeout=0.05, max_samples=FS)
        if chunk:
            x = np.array(chunk)[:, :8]
            for i in range(8):
                y = x[:, i]
                if not a.raw:
                    y, zi[i] = sosfilt(sos, y, zi=zi[i])
                buf[i].extend(y)
        now = time.monotonic()
        if now - last_draw > 0.12 and len(buf[0]) > FS:
            last_draw = now
            n = int(state["win"] * FS)
            t = np.arange(n) / FS - state["win"]
            for i in range(8):
                if not state["shown"][i]:
                    continue
                y = np.array(buf[i])[-n:]
                y = y - y.mean()
                rms = float(np.sqrt((y ** 2).mean()))
                lim = state["amp"] if state["amp"] > 0 else max(2.0, 1.1 * float(np.abs(y).max()))
                yy = np.full(n, np.nan)
                yy[-len(y):] = y
                lines[i].set_data(t, yy)
                axes[i].set_xlim(t[0], 0)
                axes[i].set_ylim(-lim, lim)
                col = "#1a9c3a" if rms < 40 else ("#d08a00" if rms < 100 else "#c0202a")
                labels[i].set_text(f"{CH[i]}  {rms:5.0f} uV")
                labels[i].set_color(col)
                ranges[i].set_text(f"+/- {lim:.0f} uV")
                axes[i].set_facecolor("#f3fff3" if rms < 40 else ("#fff8e6" if rms < 100 else "#ffecec"))
            mode = "auto fit" if state["amp"] == 0 else f"fixed +/- {state['amp']:.0f} uV"
            title.set_text(f"Core-8 live, {'raw' if a.raw else '1 to 40 Hz'}, window {state['win']:.0f} s, {mode}")
            fig.canvas.draw_idle()
        fig.canvas.flush_events()
        plt.pause(0.001)


if __name__ == "__main__":
    main()
