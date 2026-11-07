"""Unicorn BCI Core-8 (default) or Hybrid Black (--hybrid) -> LSL stream "Unicorn" (+ CSV), via g.Pype.

Paing's unit is a BCI Core-8, serial U8-2025.10.14 (BLE, 8 ch, 250 Hz, montage
Fz C3 Cz C4 Pz PO7 POz PO8). Run:  .venv/bin/python headset/unicorn_gpype.py --serial U8-2025.10.14

Route C from GTEC_TRACK_RESEARCH.md. Official, macOS supported, no dongle:
"macOS and Linux open a discoverable Unicorn paired or not" (g.Pype S3E2).

Run from the hackathon folder with the project venv (VS Code picks it up):
    .venv/bin/python headset/unicorn_gpype.py            # real headset, opens a scope window
    .venv/bin/python headset/unicorn_gpype.py --sim      # no headset: 8-ch generator, headless
    .venv/bin/python headset/unicorn_gpype.py --serial UN-2024.01.01
Then in another terminal:
    .venv/bin/python explored/ssvep/ssvep_decode.py --lsl ...

macOS gotchas (g.Pype platform notes):
  - The app running Python (Terminal, or VS Code) needs the Bluetooth permission in
    System Settings > Privacy & Security > Bluetooth. Without it discovery returns []
    with no error. Quit and reopen the app after granting it.
  - The main thread must run the Qt event loop while acquiring, so the real-device
    path keeps a window open (MainApp.run()). Closing the window stops everything.
  - The S3E2 page also says "Activate a Unicorn Python Hybrid Black licence". If the
    node refuses to open the device, that is the first thing to ask g.tec about.
"""
import argparse

import gpype as gp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", action="store_true", help="generator instead of the headset, headless")
    ap.add_argument("--serial", help='e.g. "UN-2024.01.01"; default = first Unicorn found')
    ap.add_argument("--stream", default="Unicorn", help="LSL stream name (ssvep_decode.py expects Unicorn)")
    ap.add_argument("--csv", default="unicorn_rec.csv", help="CSV base name; g.Pype appends a timestamp")
    ap.add_argument("--list", action="store_true", help="list Hybrid Blacks and exit (Core-8s cannot be listed)")
    ap.add_argument("--hybrid", action="store_true", help="Hybrid Black (UN-...) instead of the default BCI Core-8 (U8-...)")
    a = ap.parse_args()

    if a.list:
        print(gp.HybridBlack.get_available_devices())
        return

    p = gp.Pipeline()
    if a.sim:
        source = gp.Generator(sampling_rate=250, channel_count=8,
                              signal_frequency=10, signal_amplitude=10, noise_amplitude=10)
    elif a.hybrid:
        source = gp.HybridBlack(serial=a.serial)  # 8 EEG channels, aux off
    else:
        # BCI Core-8 over BLE: Fz C3 Cz C4 Pz PO7 POz PO8 at 250 Hz. No discovery
        # call exists; serial=None opens the first Core found.
        source = gp.BCICore(serial=a.serial)
    sender = gp.LSLSender(stream_name=a.stream)
    writer = gp.CsvWriter(file_name=a.csv)
    p.connect(source, sender)
    p.connect(source, writer)

    if a.sim:
        p.start()
        input("Streaming generator as LSL. Press Enter to stop.")
        p.stop()
        p.close()
        return

    app = gp.MainApp()
    scope = gp.TimeSeriesScope(name="eeg", amplitude_limit=100, time_window=10)
    bandpass = gp.Bandpass(f_lo=1, f_hi=40)
    p.connect(source, bandpass)
    p.connect(bandpass, scope)
    app.add_widget(scope)
    p.start()
    app.run()  # blocks; the Bluetooth callbacks need this loop on macOS
    p.stop()
    p.close()


if __name__ == "__main__":
    main()
