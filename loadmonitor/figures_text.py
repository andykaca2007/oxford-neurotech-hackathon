"""The two text slides that open and close the 3-minute talk, in the figure style (figstyle.py).

    .venv/bin/python loadmonitor/figures_text.py        # writes figures/slides/best8/0_problem.png and 7_limits.png
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import figstyle as F  # noqa: E402

BEST = os.path.join(F.OUT, "best8")
os.makedirs(BEST, exist_ok=True)


def text_slide(title, subtitle, lines, name, source):
    fig = F.page(title, subtitle)
    y = 0.70
    for big, small in lines:
        fig.text(F.LEFT, y, big, fontsize=24, color=F.INK, va="top", weight="medium")
        fig.text(F.LEFT, y - 0.055, small, fontsize=16, color=F.INK2, va="top")
        y -= 0.165
    F.source(fig, source)
    path = F.save(fig, name)
    shutil.copy(path, os.path.join(BEST, name))


text_slide(
    "Mental overload is invisible until something goes wrong",
    "A live, personal load reading from a consumer EEG headset, cleaned well enough to be trusted",
    [
        ("Surgeons, pilots, controllers and shift workers all overload quietly.", "Mistakes follow the overload; the overload itself has no gauge."),
        ("EEG carries the signal: alpha falls and theta rises when the mind is working hard.", "Measured in 36 lab people, it shows up within seconds."),
        ("The problem is the hardware. Dry electrodes on hair give 6,000 µV of noise around 30 µV of brain.", "So the real work is cleaning the signal, and refusing to score it when it cannot be cleaned."),
    ],
    "0_problem.png",
    "Source: PhysioNet EEG during mental arithmetic (36 people); recordings on a g.tec Unicorn BCI Core-8, 7 and 8 Nov 2026.",
)

text_slide(
    "From one headset to a gauge anyone can wear",
    "Where this goes next",
    [
        ("A personal number, not a lab average.", "Zero is your own rest, so the same gauge fits a surgeon on a night shift and a pilot on approach."),
        ("Proven on people it had never seen.", "Held-out AUROC 0.74 across 36 people; the pipeline runs end to end in real time on an eight-electrode consumer headset."),
        ("Next: better electrodes, more people, longer sessions.", "Then slow fatigue, which builds over 20 minutes or more, joins the live load on the same page."),
    ],
    "7_next.png",
    "Source: docs/OVERNIGHT.md in the repository, every number traceable to a script.",
)
