"""Fatigue markers measured only in REST blocks, comparable between blocks and between sessions.

Why rest blocks, not the live dial: frontal theta also rises with mental effort, so measured during a task it
cannot tell effort from tiredness. Fatigue shows better in resting recordings than during the task, and
relative power is more sensitive than absolute power there (Li et al. 2020, BMC Neuroscience, fatigue induced
by repeated mental arithmetic).

Markers, per clean 4 s window (light chain: detrend, notch, 3 to 30 Hz, no common reference, no masking),
then the median over the block:
  theta_mid   theta (4-8 Hz) as a share of 3-30 Hz power, mean over Fz, Cz, Pz. Theta is the strongest EEG
              marker of mental fatigue, rising at frontal, central and posterior sites (Tran et al. 2020,
              Psychophysiology, meta-analysis of 21 studies).
  alpha_post  alpha (8-13 Hz) share, mean over Pz, P3, P4, O1. Second-line marker: it varies more between people.
  tab         log10((theta + alpha) / beta), median over clean channels: the live gauge's ratio, for continuity.
Shares, not absolute power, so electrode contact changes move them less. No smoothing and no lopsided scale:
the numbers, and their change from a reference block. Up = more theta/alpha = the direction of fatigue.

Compare sessions (e.g. tired tonight vs fresh tomorrow), same person, same cap fit method:
    .venv/bin/python loadmonitor/rest_markers.py \
        --session recordings/andy_A_raw_*.csv recordings/andy_A_gauge_markers.csv tonight \
        --session recordings/andy_B_raw_*.csv recordings/andy_B_gauge_markers.csv tomorrow
"""
import argparse
import glob
import io
import os
import sys

import numpy as np
from scipy.signal import welch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "headset"))
from montage import MONTAGE  # noqa: E402
import model_search as ms  # noqa: E402

# Same light chain as andy_model.LIGHT_CFG (kept here too so this file needs no model or sklearn)
LIGHT_CFG = dict(lo=3.0, hi=30.0, notch=True, order=4, drop_delta=True, drop_gamma=True, median=True,
                 detrend=3, car=False, burst=False)
MID = ("Fz", "Cz", "Pz")
POST = ("Pz", "P3", "P4", "O1")
REST_CONDITIONS = ("baseline", "recovery", "physical", "rest")


# ---------- reading a session ----------

def resolve_raw(pattern):
    """A path or a glob (g.Pype appends a timestamp to the name); the newest match, never our own outputs."""
    hits = sorted(p for p in glob.glob(pattern) if not p.endswith("_compare.csv"))
    return hits[-1] if hits else pattern


def read_raw(path):
    """g.Pype CsvWriter file: optional '# ...' lines, a 'Time, Ch01, ...' header, then rows of time + 8 slots.
    Returns (x: (8, n) in microvolts, fs)."""
    with open(path) as fh:
        lines = [ln for ln in fh if not ln.startswith("#")]
    data = np.loadtxt(io.StringIO("".join(lines[1:])), delimiter=",", ndmin=2)
    t, x = data[:, 0], data[:, 1:9].T.astype(float)
    fs = 1.0 / float(np.median(np.diff(t))) if len(t) > 1 else 250.0
    fs = float(np.round(fs))
    if np.nanmedian(np.abs(x - np.median(x, axis=1, keepdims=True))) < 1e-3:
        print("# raw values look like volts: converting to microvolts", flush=True)
        x = x * 1e6
    return x, fs


def read_markers(path):
    """The gauge's <log>_markers.csv: rows 't,condition', t in gauge seconds. Missing file -> no markers."""
    out = []
    if not path or not os.path.exists(path):
        return out
    with open(path) as fh:
        for ln in fh.read().splitlines()[1:]:
            if "," in ln:
                t, c = ln.split(",", 1)
                try:
                    out.append((float(t), c.strip()))
                except ValueError:
                    pass
    return sorted(out)


def segments(markers, t_end):
    """[(start, end, condition)] in gauge seconds, each marker running until the next one."""
    segs = []
    for i, (t, c) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else t_end
        if end > t:
            segs.append((t, end, c))
    return segs


def label_windows(ends, win_s, segs, trim):
    """Condition of each window [end - win_s, end] (gauge seconds): the segment that holds the whole window
    after dropping `trim` s at both ends of the segment (absorbs the small bridge/gauge clock offset)."""
    lab = np.array(["none"] * len(ends), dtype=object)
    for i, e in enumerate(ends):
        s = e - win_s
        for a, b, c in segs:
            if a + trim <= s and e <= b - trim:
                lab[i] = c
                break
    return lab


def dead_channels(x):
    """Flat, or pinned near the +/-200 mV rail (open input)."""
    return (x.std(1) < 1e-6) | (np.median(np.abs(x), axis=1) > 100000)


# ---------- the markers ----------

def window_markers(xw, fs, dead, max_uv):
    """xw: (8, n) raw window in MONTAGE slot order. Returns (theta_mid, alpha_post, tab, n_clean, clean mask)."""
    xc = ms.clean_window(xw, fs, LIGHT_CFG)
    clean = (~dead) & (xc.std(1) < max_uv)
    f, p = welch(xc, fs=fs, nperseg=int(fs), noverlap=int(fs // 2), average="median", axis=1)
    tot = p[:, (f >= 3) & (f < 30)].sum(1) + 1e-12
    th = p[:, (f >= 4) & (f < 8)].sum(1)
    al = p[:, (f >= 8) & (f < 13)].sum(1)
    be = p[:, (f >= 13) & (f < 30)].sum(1) + 1e-12

    def mean_over(names, v):
        k = [MONTAGE.index(c) for c in names if c in MONTAGE and clean[MONTAGE.index(c)]]
        return float(np.mean(v[k])) if len(k) >= 2 else np.nan
    theta_mid = mean_over(MID, th / tot)
    alpha_post = mean_over(POST, al / tot)
    tab = float(np.median(np.log10((th + al)[clean] / be[clean]))) if clean.sum() >= 3 else np.nan
    return theta_mid, alpha_post, tab, int(clean.sum()), clean


def block_markers(x, fs, a_raw, b_raw, max_uv, win_s=4.0, step_s=2.0):
    """Median markers over 4 s windows (2 s step) inside raw seconds [a_raw, b_raw)."""
    n, step = int(win_s * fs), int(step_s * fs)
    dead = dead_channels(x)
    rows = []
    for i in range(max(0, int(a_raw * fs)), min(x.shape[1], int(b_raw * fs)) - n + 1, step):
        th, al, tab, nc, _ = window_markers(x[:, i:i + n], fs, dead, max_uv)
        rows.append((th, al, tab, nc))
    if not rows:
        return dict(n=0, theta_mid=np.nan, alpha_post=np.nan, tab=np.nan, clean=0.0)
    r = np.array(rows, float)
    ok = ~np.isnan(r[:, 0])
    return dict(n=int(ok.sum()), of=len(r), theta_mid=float(np.nanmedian(r[:, 0])) if ok.any() else np.nan,
                alpha_post=float(np.nanmedian(r[:, 1])) if (~np.isnan(r[:, 1])).any() else np.nan,
                tab=float(np.nanmedian(r[:, 2])) if (~np.isnan(r[:, 2])).any() else np.nan,
                clean=float(np.mean(r[:, 3])))


def session_blocks(raw_path, markers_path, offset=0.0, trim=10.0, max_uv=100.0, baseline_s=30.0):
    """Rest blocks of one session (+ the task block, flagged), with their markers."""
    x, fs = read_raw(raw_path)
    t_end = x.shape[1] / fs - offset
    segs = segments(read_markers(markers_path), t_end)
    blocks = [("gauge baseline", 0.0, 4.0 + baseline_s)]                  # the gauge's own first 30 s window ends
    for a, b, c in segs:
        if c in REST_CONDITIONS or c == "mental":
            blocks.append((c, a + trim, b - trim))
    out = []
    for name, a, b in blocks:
        if b - a < 8:
            continue
        m = block_markers(x, fs, a + offset, b + offset, max_uv)
        m.update(block=name, start=a, end=b, task=(name == "mental"))
        out.append(m)
    return out


def print_blocks(rows, ref=None, label=""):
    if ref is None:
        ref = next((r for r in rows if not r["task"] and r["n"] > 0), None)
        if ref is not None:
            ref = dict(ref, block=(f"{label} " if label else "") + ref["block"])
    print(f"  {'block':24s} {'s':>9s} {'win':>7s} {'theta_mid':>10s} {'alpha_post':>11s} {'(t+a)/b':>8s}   change vs {ref['block'] if ref else '-'}")
    for r in rows:
        def ch(k):
            if ref is None or not np.isfinite(r[k]) or not np.isfinite(ref[k]) or ref[k] == 0:
                return "   -  "
            return f"{100 * (r[k] / ref[k] - 1):+5.0f}%" if k != "tab" else f"{r[k] - ref[k]:+.2f}"
        tag = " (task: not comparable)" if r["task"] else ""
        print(f"  {r['block'][:24]:24s} {r['start']:4.0f}-{r['end']:<4.0f} {r['n']:3d}/{r.get('of', 0):<3d} "
              f"{r['theta_mid']:10.3f} {r['alpha_post']:11.3f} {r['tab']:8.2f}   "
              f"theta {ch('theta_mid')} alpha {ch('alpha_post')} ratio {ch('tab')}{tag}")
    return ref


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", nargs=3, action="append", metavar=("RAW", "MARKERS", "LABEL"), required=True,
                    help="raw CSV (glob ok), the gauge's markers CSV, a label; repeat for each session")
    ap.add_argument("--offset", type=float, default=0.0, help="raw time = gauge time + offset (s)")
    ap.add_argument("--trim", type=float, default=10.0, help="s dropped at both ends of every block")
    ap.add_argument("--max-uv", type=float, default=100.0, help="a channel window counts as clean under this RMS (uV)")
    a = ap.parse_args()
    ref = None
    for raw, mk, label in a.session:
        raw = resolve_raw(raw)
        rows = session_blocks(raw, mk, a.offset, a.trim, a.max_uv)
        print(f"\n{label}: {os.path.basename(raw)}")
        ref = print_blocks(rows, ref, label)   # every session is compared with the FIRST session's first rest block
    print("\nUp = more theta/alpha = the direction of fatigue. Only compare rest blocks, same person, same cap fit.")


if __name__ == "__main__":
    main()
