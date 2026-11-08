"""Editorial figure style (Economist / FT / Nature rules, Tufte data-ink), one module every figure uses.

Rules, from the sources read on 8 Nov (research-figure-guide.nature.com, ftplottools ft_theme.R, ggthemes economist.R,
Rougier et al. 2014):
  white page; ink text; one accent colour for the important data, everything else grey
  title = a statement, left-aligned at the figure edge; subtitle carries the units; source line bottom-left
  bottom spine only, horizontal hairline gridlines, no y-axis line, y tick length 0, x ticks outward
  direct labels at line ends, no legend boxes; context series thin grey
  no rounded cards, gradients, shadows, coloured titles, boxed axes or vertical grid on line charts
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "figures", "slides")
os.makedirs(OUT, exist_ok=True)

# dark variant of the same rules (Paing's call: the page is black, so are the slides). Still one accent, ink-only titles.
PAGE = "#000000"
INK = "#EDEDED"
INK2 = "#8A8A8A"          # subtitle, ticks, source, de-emphasised text
GRID = "#1E1E1E"
GREY = "#4A4A4A"          # context series
ACCENT = "#2FBF71"        # the one important thing (the page's green)
LEAD = "#EDEDED"          # lead series: ink, so colour is spent only on the accent
BAND = "#141414"          # shaded spans (task phase, brain bands)

_names = {f.name for f in font_manager.fontManager.ttflist}
FONT = next((f for f in ("Avenir Next", "Helvetica Neue", "Helvetica", "Arial") if f in _names), "DejaVu Sans")
T_TITLE, T_SUB, T_AX, T_TICK, T_LABEL, T_SRC = 28, 18, 15, 15, 15, 12

plt.rcParams.update({
    "font.family": FONT, "font.size": T_TICK, "text.color": INK,
    "figure.facecolor": PAGE, "axes.facecolor": PAGE, "savefig.facecolor": PAGE,
    "axes.edgecolor": INK, "axes.linewidth": 1.0, "axes.labelcolor": INK2,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.75, "axes.axisbelow": True,
    "xtick.color": INK2, "ytick.color": INK2, "xtick.direction": "out", "xtick.major.size": 5, "xtick.major.width": 0.75,
    "ytick.major.size": 0, "ytick.major.pad": 6, "xtick.labelsize": T_TICK, "ytick.labelsize": T_TICK,
    "axes.titlesize": T_AX, "axes.labelsize": T_AX, "legend.frameon": False, "pdf.fonttype": 42,
})

LEFT, RIGHT = 0.06, 0.94


def page(title, subtitle):
    """A 1920 x 1080 figure with the title block: thin accent rule, statement title, subtitle with the units."""
    fig = plt.figure(figsize=(16, 9), dpi=120)
    fig.add_artist(plt.Line2D([LEFT, RIGHT], [0.955, 0.955], color=ACCENT, lw=0.75, transform=fig.transFigure))
    fig.add_artist(plt.Rectangle((LEFT, 0.955 - 0.012), 0.022, 0.012, color=ACCENT, transform=fig.transFigure))
    fig.text(LEFT, 0.885, title, fontsize=T_TITLE, color=INK, weight="medium", va="baseline")
    fig.text(LEFT, 0.845, subtitle, fontsize=T_SUB, color=INK2, va="baseline")
    return fig


def axes(fig, rect=(LEFT, 0.16, RIGHT - LEFT, 0.62)):
    a = fig.add_axes(rect)
    a.tick_params(axis="y", length=0)
    a.spines["bottom"].set_color(INK2)
    return a


def ylabel_top(a, text):
    """Unit label sitting above the top of the y axis, Economist style, instead of a rotated axis title."""
    a.text(0, 1.02, text, transform=a.transAxes, ha="left", va="bottom", fontsize=T_AX, color=INK2)


def end_label(a, x, y, text, color, dy=0, weight="normal", size=T_LABEL):
    a.annotate(text, (x, y), xytext=(8, dy), textcoords="offset points", color=color, fontsize=size, va="center", weight=weight,
               annotation_clip=False)


def source(fig, text):
    fig.text(LEFT, 0.04, text, fontsize=T_SRC, color=INK2, va="bottom", linespacing=1.45)


def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path)
    plt.close(fig)
    print("wrote", os.path.relpath(path, ROOT))
    return path
