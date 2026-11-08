"""Shared look for the slide figures: black ground, 16:9, page colours."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "figures", "slides")
os.makedirs(OUT, exist_ok=True)
BG, FG, DIM, LINE = "#000000", "#e5e5e5", "#767676", "#2b2b2b"
YEL, ORA, BLU, GRN = "#fab413", "#f05a24", "#4f8fe8", "#2fbf71"
_names = {f.name for f in font_manager.fontManager.ttflist}
FONT = next((f for f in ("Avenir Next", "Avenir", "Helvetica Neue", "Helvetica") if f in _names), "DejaVu Sans")
plt.rcParams.update({"font.family": FONT, "font.size": 15, "text.color": FG, "axes.labelcolor": FG, "axes.edgecolor": LINE,
                     "xtick.color": DIM, "ytick.color": DIM, "axes.facecolor": BG, "figure.facecolor": BG,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": "#161616",
                     "grid.linewidth": 0.8, "savefig.facecolor": BG})


def slide(title, sub):
    fig = plt.figure(figsize=(16, 9), dpi=120)
    fig.text(0.05, 0.92, title, fontsize=30, color=FG, weight="bold")
    fig.text(0.05, 0.875, sub, fontsize=15, color=DIM)
    return fig


def save(fig, name, note):
    fig.text(0.05, 0.015, note, fontsize=11, color=DIM, va="bottom", linespacing=1.4)
    fig.savefig(os.path.join(OUT, name))
    plt.close(fig)
    print("wrote", os.path.join("figures", "slides", name))
