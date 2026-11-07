# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["numpy", "scipy", "pyserial", "brainflow"]
# ///
"""SwallowCue, live: chin EMG in, swallow count out, wristband buzz when swallowing stops.

Same pipeline as warmup/swallow.py, but streaming, so it runs on the event's kit:
    band-pass -> mains notch -> rectify -> 5 Hz envelope -> bursts -> is_swallow() -> cue timer

Run (from the hackathon folder):
    uv run live_emg/swallowcue_live.py --board fake                      # no hardware: replays a fake session
    uv run live_emg/swallowcue_live.py --board cyton --port /dev/cu.usbserial-XXXX --channel 1
    uv run live_emg/swallowcue_live.py --board ganglion --port ...       (BrainFlow board ids)
Add --cue-port /dev/cu.usbserial-YYYY to make the ESP32 wristband buzz (planb_imu firmware, any mode).
Add --log session.csv to save everything for tools/eval_session.py and tools/live_plot.py.

While it runs: press Enter each time you swallow (ground truth for the score).

The swallow rule is YOURS: it imports is_swallow() from warmup/swallow.py.
Until you write it, nothing counts and the cue fires every T seconds.
"""
from __future__ import annotations

import argparse
import importlib.util
import math
import sys
import threading
import time
from pathlib import Path

import numpy as np
from scipy import signal

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

ON_FACTOR = 3.0          # same as warmup/swallow.py
MIN_BURST_S = 0.05       # same blip limit as find_bursts()
DECIDE_AFTER_S = 2.0     # wait this long after a burst to measure gap_after (so gap_after <= 2 s)
CALIB_S = 3.0
BASE_TAU_S = 10.0
CHUNK_S = 0.05


# ---------------------------------------------------------------------------
# Signal sources
# ---------------------------------------------------------------------------

class FakeSource:
    """Replays warmup/swallow.py's fake session in real time (or faster).
    Adds 50 Hz mains hum so the notch filter is exercised too."""

    def __init__(self, fs: float, seconds: float, seed: int, speed: float, swallow_mod):
        x, truth = swallow_mod.make_session(
            seconds=seconds, fs=int(fs), swallows=8,
            talk_s=[(20, 25)], chew_s=[(70, 25)], rng=seed)
        t = np.arange(len(x)) / fs
        self.x = x + 1.5 * np.sin(2 * np.pi * 50 * t)
        self.truth = truth
        self.fs = fs
        self.speed = speed
        self.i = 0
        self.t0 = None

    def start(self):
        self.t0 = time.time()

    def read(self) -> np.ndarray | None:
        if self.i >= len(self.x):
            return None
        due = int((time.time() - self.t0) * self.speed * self.fs)
        due = min(due, len(self.x))
        out = self.x[self.i:due]
        self.i = due
        return out

    def stop(self):
        pass


class BrainFlowSource:
    def __init__(self, board: str, port: str | None, channel: int, bipolar: bool = False):
        from brainflow.board_shim import BoardIds, BoardShim, BrainFlowInputParams

        ids = {
            "cyton": BoardIds.CYTON_BOARD,
            "cyton_daisy": BoardIds.CYTON_DAISY_BOARD,
            "ganglion": BoardIds.GANGLION_BOARD,
            "synthetic": BoardIds.SYNTHETIC_BOARD,
        }
        self.board_id = ids[board].value
        params = BrainFlowInputParams()
        if port:
            params.serial_port = port
        BoardShim.disable_board_logger()
        self.shim = BoardShim(self.board_id, params)
        self.fs = BoardShim.get_sampling_rate(self.board_id)
        exg = BoardShim.get_exg_channels(self.board_id)
        if not 1 <= channel <= len(exg):
            sys.exit(f"--channel must be 1 to {len(exg)} for this board")
        self.row = exg[channel - 1]
        self.truth = None
        self.channel = channel
        self.bipolar = bipolar and board in ("cyton", "cyton_daisy") and channel <= 8

    def start(self):
        self.shim.prepare_session()
        if self.bipolar:
            # Cyton channel settings: x CH POWER GAIN INPUT BIAS SRB2 SRB1 X
            # on, gain 24, normal input, in bias, SRB2 OFF (so N_P minus N_N), SRB1 off
            cmd = f"x{self.channel}060100X"
            self.shim.config_board(cmd)
            print(f"# bipolar: sent {cmd} (electrodes on N{self.channel}P and N{self.channel}N)", flush=True)
        self.shim.start_stream()

    def read(self) -> np.ndarray:
        data = self.shim.get_board_data()
        return data[self.row] if data.size else np.empty(0)

    def stop(self):
        try:
            self.shim.stop_stream()
            self.shim.release_session()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Streaming filters (state carried between chunks, so it is causal like the device)
# ---------------------------------------------------------------------------

class Filters:
    def __init__(self, fs: float):
        nyq = fs / 2
        hi = min(120.0, 0.9 * nyq)
        lo = 20.0 if hi > 40 else 10.0
        self.band = (lo, hi)
        self.sos = [signal.butter(4, (lo, hi), btype="band", fs=fs, output="sos")]
        self.notches = []
        for f0 in (50.0, 100.0):  # UK mains and its harmonic
            if f0 < 0.95 * nyq and lo < f0 < hi:
                b, a = signal.iirnotch(f0, 30.0, fs)
                self.sos.append(signal.tf2sos(b, a))
                self.notches.append(f0)
        self.env_sos = signal.butter(2, 5.0, fs=fs, output="sos")
        self.zi = [signal.sosfilt_zi(s) * 0 for s in self.sos]
        self.env_zi = signal.sosfilt_zi(self.env_sos) * 0

    def __call__(self, x: np.ndarray) -> np.ndarray:
        y = x.astype(float)
        for k, s in enumerate(self.sos):
            y, self.zi[k] = signal.sosfilt(s, y, zi=self.zi[k])
        y = np.abs(y)
        env, self.env_zi = signal.sosfilt(self.env_sos, y, zi=self.env_zi)
        return env


# ---------------------------------------------------------------------------
# Burst finder: same burst dict as warmup/swallow.py find_bursts()
# ---------------------------------------------------------------------------

class Bursts:
    def __init__(self, fs: float):
        self.fs = fs
        self.base = None
        self.calib = []
        self.a_base = 1 - math.exp(-1 / (BASE_TAU_S * fs))
        self.active = False
        self.cur = None
        self.pending = None
        self.last_end = None

    def threshold(self):
        return ON_FACTOR * self.base if self.base else float("nan")

    def push(self, t: float, e: float):
        """One envelope sample. Returns a finished burst dict or None."""
        if self.base is None:
            self.calib.append(e)
            if len(self.calib) >= CALIB_S * self.fs:
                c = np.array(self.calib[int(len(self.calib) * 0.3):])  # skip filter start-up
                self.base = float(np.median(c)) or 1e-9
            return None
        done = None
        if not self.active:
            if e > ON_FACTOR * self.base:
                self.active = True
                self.cur = dict(start=t, peak=e)
                if self.pending:
                    self.pending["gap_after"] = t - self.pending["end"]
                    done, self.pending = self.pending, None
            else:
                self.base += self.a_base * (e - self.base)
                if self.pending and t - self.pending["end"] >= DECIDE_AFTER_S:
                    self.pending["gap_after"] = t - self.pending["end"]
                    done, self.pending = self.pending, None
        else:
            self.cur["peak"] = max(self.cur["peak"], e)
            if e <= ON_FACTOR * self.base:
                self.active = False
                b = self.cur
                b["end"] = t
                b["duration"] = b["end"] - b["start"]
                b["centre"] = (b["start"] + b["end"]) / 2
                if b["duration"] >= MIN_BURST_S:
                    b["gap_before"] = float("inf") if self.last_end is None else b["start"] - self.last_end
                    self.last_end = b["end"]
                    self.pending = b
        return done


class CueTimer:
    """Buzz T s after the last swallow, then every T s. Mirrors cue_times()."""

    def __init__(self, T: float, t0: float):
        self.T = T
        self.next = t0 + T

    def swallow(self, t: float):
        self.next = max(self.next, t + self.T)

    def due(self, t: float) -> bool:
        if t >= self.next:
            self.next += self.T
            return True
        return False


# ---------------------------------------------------------------------------

def load_rule(path: Path):
    spec = importlib.util.spec_from_file_location("swallow_rule", path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--board", default="fake", choices=["fake", "synthetic", "cyton", "cyton_daisy", "ganglion"])
    ap.add_argument("--port", help="OpenBCI dongle serial port")
    ap.add_argument("--channel", type=int, default=1, help="which EXG channel the chin electrodes are on (1-based)")
    ap.add_argument("--bipolar", action="store_true",
                    help="Cyton: use the N1P/N1N pin pair for the two chin electrodes (turns SRB2 off for that channel)")
    ap.add_argument("--cue-port", help="ESP32 wristband serial port (sends 'b' to buzz)")
    ap.add_argument("--T", type=float, default=15.0, help="seconds without a swallow before a buzz")
    ap.add_argument("--log", help="CSV log for eval_session.py / live_plot.py")
    ap.add_argument("--rule", default=str(ROOT / "warmup" / "swallow.py"),
                    help="file that defines is_swallow(burst) (default: your warmup/swallow.py)")
    ap.add_argument("--seconds", type=float, default=120, help="fake board: session length")
    ap.add_argument("--seed", type=int, default=0, help="fake board: which fake session")
    ap.add_argument("--speed", type=float, default=1.0, help="fake board: replay speed (10 = 10x)")
    args = ap.parse_args()

    rule = load_rule(Path(args.rule))
    warned = {"rule": False}

    def is_swallow(b):
        try:
            return bool(rule.is_swallow(b))
        except NotImplementedError:
            if not warned["rule"]:
                print("! is_swallow() not written yet: nothing counts as a swallow", flush=True)
                warned["rule"] = True
            return False

    if args.board == "fake":
        src = FakeSource(250.0, args.seconds, args.seed, args.speed, load_rule(ROOT / "warmup" / "swallow.py"))
    else:
        src = BrainFlowSource(args.board, args.port, args.channel, args.bipolar)

    fs = src.fs
    filt = Filters(fs)
    bursts = Bursts(fs)
    print(f"# board={args.board} fs={fs:g} Hz band={filt.band[0]:g} to {filt.band[1]:g} Hz "
          f"notch={filt.notches or 'none'} T={args.T:g} s", flush=True)
    if fs < 200:
        print("# NOTE: low sample rate, EMG band is narrow. With Cyton+Daisy, unplug the Daisy for 250 Hz.", flush=True)

    cue_ser = None
    if args.cue_port:
        import serial
        cue_ser = serial.Serial(args.cue_port, 115200, timeout=0)
        time.sleep(2.0)  # ESP32 resets when the port opens

    log = open(args.log, "w") if args.log else None

    def emit(line: str, show: bool = False):
        if log:
            log.write(line + "\n")
            log.flush()
        if show:
            print(line, flush=True)

    # Ground-truth marks: press Enter when you swallow.
    t_start = time.time()
    def marks():
        for _ in sys.stdin:
            emit(f"M,{time.time() - t_start:.2f}", show=True)
    threading.Thread(target=marks, daemon=True).start()

    if src.truth is not None:
        for c in src.truth:
            emit(f"T,{c:.2f}")

    src.start()
    t_start = time.time()
    n = 0               # samples processed
    swallows = 0
    last_sw = None
    cue = None
    last_status = 0.0
    try:
        while True:
            x = src.read()
            if x is None:
                break
            if len(x) == 0:
                time.sleep(CHUNK_S)
                continue
            env = filt(x)
            for k, e in enumerate(env):
                t = (n + k) / fs          # signal clock (= wall clock on a real board)
                b = bursts.push(t, float(e))
                if bursts.base is not None and cue is None:
                    cue = CueTimer(args.T, t)
                    print("# calibrated: quiet level learnt, cueing is live", flush=True)
                if b:
                    sw = is_swallow(b)
                    ga = b["gap_before"]
                    emit(f"B,{b['centre']:.2f},{b['duration']:.2f},{b['peak']:.4g},0,"
                         f"{-1 if math.isinf(ga) else ga:.2f},{b['gap_after']:.2f},"
                         f"{'SWALLOW' if sw else 'other'}", show=True)
                    if sw:
                        swallows += 1
                        last_sw = b["centre"]
                        cue.swallow(last_sw)
                if cue and cue.due(t):
                    emit(f"C,{t:.2f}", show=True)
                    if cue_ser:
                        cue_ser.write(b"b\n")
                if (n + k) % max(1, int(fs / 50)) == 0 and bursts.base is not None:
                    emit(f"S,{t:.2f},{e:.5g},{bursts.threshold():.5g}")
            n += len(x)
            now = n / fs
            if time.time() - last_status >= 2.0:
                last_status = time.time()
                since = "none yet" if last_sw is None else f"{now - last_sw:.0f} s ago"
                print(f"  swallows {swallows}  last {since}", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        src.stop()
        if log:
            log.close()
        print(f"# done: {swallows} swallows", flush=True)


if __name__ == "__main__":
    main()
