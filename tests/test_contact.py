"""Contact view numbers and the Alpha check's layout line (load_gauge.contact_metrics, layout_note)."""
import os
import sys
import warnings

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "loadmonitor"))
warnings.filterwarnings("ignore")
import load_gauge as lg  # noqa: E402

FS = lg.FS


def test_contact_metrics_separates_hum_from_signal():
    t = np.arange(4 * FS) / FS
    x = np.zeros((2, t.size))
    x[0] = 1000 * np.sin(2 * np.pi * 50 * t)          # pure mains hum
    x[1] = 20 * np.sin(2 * np.pi * 10 * t)            # 10 Hz, 20 uV peak = 14 uV RMS
    hum, bb, al = lg.contact_metrics(x)
    assert hum[0] > 600 and bb[0] < 40                 # the notch removes hum from the broadband number
    assert abs(bb[1] - 14.1) < 2 and abs(al[1] - 14.1) < 2 and hum[1] < 1


def test_layout_note():
    assert lg.layout_note({}) == ""
    assert "as layout A expects" in lg.layout_note({"Pz": dict(rise=5.0, margin=4.0, ok=True)})
    front = lg.layout_note({"Fz": dict(rise=5.0, margin=4.0, ok=True), "Pz": dict(rise=0.5, margin=0.0, ok=False)})
    assert "not at the back" in front and "Fz" in front
    none = lg.layout_note({"Pz": dict(rise=1.2, margin=0.0, ok=False), "Fz": dict(rise=-0.5, margin=0.0, ok=False)})
    assert "no electrode passed" in none and "Pz" in none
