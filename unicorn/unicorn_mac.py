# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "pyserial"]
# ///
"""Unicorn Hybrid Black on a Mac, no dongle, no Windows: plain Bluetooth serial.

Pair the headset first: System Settings > Bluetooth, it appears as UN-YYYYMMDD.
Then:
    uv run unicorn/unicorn_mac.py --list
    uv run unicorn/unicorn_mac.py --port /dev/cu.UN-20240101 --log s0.csv
    uv run unicorn/unicorn_mac.py --port ... --lsl        (needs: uv pip install pylsl)

Prints one quality line per second: battery, and RMS in uV per channel.
Under ~30 uV at rest = good contact. Hundreds = not touching. Ctrl-C stops.

Protocol (Oostenveld gist + docs.rs gtec crate, both from g.tec's BT protocol doc):
115200 baud; start 61 7C 87 (reply 00 00 00); stop 63 5C C5;
45-byte frames C0 00 | battery nibble | 8x int24 BE EEG | 3x int16 LE accel |
3x int16 LE gyro | uint32 LE counter | 0D 0A, at 250 Hz.
UNVERIFIED on real hardware as of 7 Nov 2026. If the first frame is not C0 00, stop.
"""
import argparse
import struct
import sys
import time

import numpy as np
import serial
import serial.tools.list_ports

FS = 250
CH_NAMES = ["Fz", "C3", "Cz", "C4", "Pz", "PO7", "Oz", "PO8"]
START = bytes([0x61, 0x7C, 0x87])
STOP = bytes([0x63, 0x5C, 0xC5])
FRAME = 45
EEG_SCALE = 4500000.0 / 50331642.0


def parse(frame: bytes):
    """One 45-byte frame -> (battery %, eeg[8] uV, accel[3] g, gyro[3] dps, counter)."""
    if frame[0:2] != b"\xC0\x00" or frame[43:45] != b"\x0D\x0A":
        return None
    battery = 100.0 * (frame[2] & 0x0F) / 15.0
    eeg = np.empty(8)
    for ch in range(8):
        raw = int.from_bytes(frame[3 + 3 * ch:6 + 3 * ch], "big", signed=True)  # correct sign extension
        eeg[ch] = raw * EEG_SCALE
    accel = np.array(struct.unpack("<hhh", frame[27:33])) / 4096.0
    gyro = np.array(struct.unpack("<hhh", frame[33:39])) / 32.8  # 33..38, not the accel bytes
    counter = struct.unpack("<I", frame[39:43])[0]
    return battery, eeg, accel, gyro, counter


def resync(s: serial.Serial) -> bytes:
    """Slide until a frame boundary is found; returns the first good frame."""
    buf = s.read(FRAME)
    for _ in range(FRAME * 4):
        if parse(buf) is not None:
            return buf
        buf = buf[1:] + s.read(1)
    raise RuntimeError("no C0 00 ... 0D 0A frame found: wrong device, or the protocol differs")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="show serial ports and exit")
    ap.add_argument("--port")
    ap.add_argument("--log", help="CSV out: t,counter,batt,Fz..PO8,ax,ay,az,gx,gy,gz")
    ap.add_argument("--lsl", action="store_true", help="push a 17-channel LSL stream named Unicorn")
    a = ap.parse_args()

    if a.list or not a.port:
        for p in serial.tools.list_ports.comports():
            print(p.device, "|", p.description)
        if not a.port:
            return

    outlet = None
    if a.lsl:
        from pylsl import StreamInfo, StreamOutlet  # optional dependency
        info = StreamInfo("Unicorn", "EEG", 17, FS, "float32", "unicorn_mac")
        chs = info.desc().append_child("channels")
        for n in CH_NAMES + ["ax", "ay", "az", "gx", "gy", "gz", "batt", "counter", "t"]:
            chs.append_child("channel").append_child_value("label", n)
        outlet = StreamOutlet(info)

    log = open(a.log, "w") if a.log else None
    if log:
        log.write("t,counter," + ",".join(["batt"] + CH_NAMES + ["ax", "ay", "az", "gx", "gy", "gz"]) + "\n")

    s = serial.Serial(a.port, 115200, timeout=5)
    s.reset_input_buffer()
    s.write(START)
    ack = s.read(3)
    print(f"# start ack: {ack.hex()} (expect 000000)", flush=True)
    frame = resync(s)
    t0 = time.monotonic()
    win = []
    n = 0
    last_counter = None
    try:
        while True:
            r = parse(frame)
            if r is None:
                frame = resync(s)
                continue
            batt, eeg, accel, gyro, counter = r
            if last_counter is not None and counter != last_counter + 1:
                print(f"# dropped {counter - last_counter - 1} frames", flush=True)
            last_counter = counter
            t = time.monotonic() - t0
            row = np.concatenate([[batt], eeg, accel, gyro])
            if log:
                log.write(f"{t:.4f},{counter}," + ",".join(f"{v:.3f}" for v in row) + "\n")
            if outlet:
                outlet.push_sample(np.concatenate([eeg, accel, gyro, [batt, counter, t]]).astype("float32"))
            win.append(eeg)
            n += 1
            if n % FS == 0:
                w = np.array(win)
                w = w - w.mean(axis=0)
                rms = np.sqrt((w ** 2).mean(axis=0))
                print(f"t={t:6.1f}s batt={batt:3.0f}% " + " ".join(f"{c}={v:5.0f}" for c, v in zip(CH_NAMES, rms)), flush=True)
                win = []
            frame = s.read(FRAME)
    except KeyboardInterrupt:
        pass
    finally:
        s.write(STOP)
        time.sleep(0.1)
        s.close()
        if log:
            log.close()
            print(f"# saved {a.log}")


if __name__ == "__main__":
    sys.exit(main())
