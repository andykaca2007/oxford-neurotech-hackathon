"""One table of tiles shared by the stim, the decoder and the calibrator.

Each set is tied to a display refresh rate: flicker must be an integer number of frames.
Lock the MacBook to that rate in System Settings > Displays (ProMotion is variable; pick the
fixed value).

    4 tiles  at  60 Hz: periods 8, 7, 6, 5 frames  -> 7.5, 8.57, 10, 12 Hz
    12 tiles at 120 Hz: periods 19..8 frames        -> 6.3 to 15 Hz, about 0.5 to 1.7 Hz apart

A 12-class, 1 s decoder is exactly what the public evaluation (calibration_curve.py) tests.
"""

TILE_SETS = {
    4: dict(refresh=60, periods=[8, 7, 6, 5], cols=2,
            colours=[(70, 130, 255), (80, 200, 120), (250, 180, 60), (240, 80, 80)]),
    12: dict(refresh=120, periods=[19, 18, 17, 16, 15, 14, 13, 12, 11, 10, 9, 8], cols=4,
             colours=[(70, 130, 255), (80, 200, 120), (250, 180, 60), (240, 80, 80)] * 3),
}


def tile_set(n: int):
    s = TILE_SETS[n]
    freqs = [s["refresh"] / p for p in s["periods"]]
    return dict(n=n, refresh=s["refresh"], periods=s["periods"], freqs=freqs, cols=s["cols"],
                rows=n // s["cols"], colours=s["colours"])


if __name__ == "__main__":
    for n in TILE_SETS:
        t = tile_set(n)
        print(f"{n} tiles at {t['refresh']} Hz:", " ".join(f"{f:.2f}" for f in t["freqs"]))
