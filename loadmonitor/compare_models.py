"""Replay one recorded session through two load models side by side, plus a personal model and fatigue markers.

    .venv/bin/python loadmonitor/compare_models.py \
        --raw "recordings/andy_20261108_0130_raw_*.csv" --markers recordings/andy_20261108_0130_gauge_markers.csv
    defaults: --model-a models/readiness.joblib (the live model)  --model-b models/andy_load.joblib (andy_model.py)

Input: the two files run_all.sh writes. Raw = g.Pype CsvWriter (Time = sample index / 250 from the bridge
start, then the 8 slots in headset/montage.py order). Markers = the gauge's (t, condition) file, t in gauge
seconds. The gauge opens a few seconds after the bridge, so raw time = gauge time + --offset (default 0);
--trim s dropped at both ends of every segment absorb that small unknown offset.

For each model, exactly as the live gauge does it: a 4 s window every 1 s; the first 30 windows are the
baseline (ASR, if the model uses it, is fitted on them); features minus the baseline mean; model probability.
Windows where any of the model's channels is dead or over --max-uv after light filtering are skipped for both
models (the share skipped is printed: if it is high, nothing below is trustworthy).

Printed per model:
  median probability per condition
  AUC mental vs recovery     can it tell the task from rest AFTER the task? (the honest test; 0.5 = chance)
  AUC recovery vs baseline   drift control: both are rest, so this should be near 0.5. If it is as high as
                             the line above, the model is reading time/contact drift, not the task.
Personal model: logistic regression on THIS wearer's own windows (rest = baseline + recovery, task = mental),
trained on one time half and tested on the other, both ways. If even this is near 0.5, the recording does not
separate rest from task at all (contact or protocol) and no public model can fix it. If it is high but the
public models are not, the public data does not transfer (eyes closed, dark room) and a short personal
calibration is the fix.
Fatigue: rest-block markers (rest_markers.py). Outputs <raw>_compare.csv (per window) and <raw>_compare.png.
"""
import argparse
import os
import sys
import warnings

import joblib
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "headset"))
from montage import MONTAGE  # noqa: E402
import model_search as ms  # noqa: E402
import readiness_model as rm  # noqa: E402
import rest_markers as rmk  # noqa: E402

warnings.filterwarnings("ignore")


def auc(pos, neg):
    from sklearn.metrics import roc_auc_score
    pos, neg = np.asarray(pos), np.asarray(neg)
    if len(pos) < 3 or len(neg) < 3:
        return np.nan
    return float(roc_auc_score(np.r_[np.ones(len(pos)), np.zeros(len(neg))], np.r_[pos, neg]))


def replay(m, x, fs, ends_idx, base_idx):
    """Model probability for windows ending at sample indices ends_idx, baseline = windows ending at base_idx."""
    chans = list(m.get("channels", rm.CH))
    ms.CH[:] = chans
    rm.CH[:] = chans
    idx = [MONTAGE.index(c) for c in chans]
    cfg, rich, fmask = m.get("feat_cfg"), bool(m.get("rich", False)), m.get("feature_mask")
    n = int(m["epoch_s"] * fs)
    asr = None
    if cfg and cfg.get("asr"):
        asr = ms.ASR(cfg["asr"])
        asr.fit([ms.clean_window(x[idx, e - n:e], fs, cfg) for e in base_idx])
    if m.get("riem"):
        print("# stacked model: only its band-power half is replayed here", flush=True)

    def feat(e):
        w = x[idx, e - n:e]
        f = ms.feats(w, fs, True, cfg, asr) if rich else rm.features(w, fs)
        f = np.nan_to_num(f, nan=0.0, posinf=0.0, neginf=0.0)
        return f[fmask] if fmask is not None else f
    base = np.mean([feat(e) for e in base_idx], axis=0)
    F = np.array([feat(e) for e in ends_idx]) - base
    return m["model"].predict_proba(F)[:, 1], F, idx


def personal(F, rest, task, p_public):
    """Two-fold by time halves within each class, a 4-window gap at the split. Returns (personal AUC, hybrid AUC)."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    r, t = np.where(rest)[0], np.where(task)[0]
    if len(r) < 16 or len(t) < 16:
        return np.nan, np.nan
    halves = []
    for idx in (r, t):
        h = len(idx) // 2
        halves.append((idx[:h - 2], idx[h + 2:]))
    aucs, hyb = [], []
    for k in (0, 1):
        tr = np.r_[halves[0][k], halves[1][k]]
        te_r, te_t = halves[0][1 - k], halves[1][1 - k]
        y = np.r_[np.zeros(len(halves[0][k])), np.ones(len(halves[1][k]))]
        clf = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=5000)).fit(F[tr], y)
        pr, pt = clf.predict_proba(F[te_r])[:, 1], clf.predict_proba(F[te_t])[:, 1]
        aucs.append(auc(pt, pr))
        hyb.append(auc(0.5 * (pt + p_public[te_t]), 0.5 * (pr + p_public[te_r])))
    return float(np.nanmean(aucs)), float(np.nanmean(hyb))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True, help="raw CSV from the bridge (a glob is fine)")
    ap.add_argument("--markers", help="the gauge's <log>_markers.csv")
    ap.add_argument("--model-a", default="models/readiness.joblib")
    ap.add_argument("--model-b", default="models/andy_load.joblib")
    ap.add_argument("--offset", type=float, default=0.0, help="raw time = gauge time + offset (s)")
    ap.add_argument("--trim", type=float, default=10.0, help="s dropped at both ends of every segment")
    ap.add_argument("--max-uv", type=float, default=100.0, help="skip windows where a model channel is above this RMS (uV)")
    ap.add_argument("--baseline", type=float, default=30.0, help="baseline windows, as in the gauge")
    a = ap.parse_args()

    raw = rmk.resolve_raw(a.raw)
    x, fs = rmk.read_raw(raw)
    dur = x.shape[1] / fs
    print(f"session {os.path.basename(raw)}: {dur:.0f} s at {fs:.0f} Hz, offset {a.offset:+.1f} s")
    dead = rmk.dead_channels(x)
    if dead.any():
        print(f"# dead or railed for the whole session: {' '.join(c for c, d in zip(MONTAGE, dead) if d)}")
    models = {"A " + os.path.basename(a.model_a): joblib.load(a.model_a), "B " + os.path.basename(a.model_b): joblib.load(a.model_b)}
    win_s = 4.0
    n = int(win_s * fs)

    # the gauge's clock: windows end every 1 s from 4 s; the first --baseline of them are the baseline
    ends_g = np.arange(win_s, dur - a.offset, 1.0)
    ends_idx = np.round((ends_g + a.offset) * fs).astype(int)
    keep = (ends_idx >= n) & (ends_idx <= x.shape[1])
    ends_g, ends_idx = ends_g[keep], ends_idx[keep]
    nb = int(a.baseline)
    base_idx = ends_idx[:nb]
    segs = rmk.segments(rmk.read_markers(a.markers), dur - a.offset)
    lab = rmk.label_windows(ends_g, win_s, segs, a.trim)
    lab[:nb] = "gauge baseline"
    print("segments: " + (", ".join(f"{c} {s:.0f}-{e:.0f} s" for s, e, c in segs) if segs else "no markers file: only the baseline is labelled"))

    # bad windows, judged on the light chain so both models skip the same ones
    model_slots = sorted({MONTAGE.index(c) for m in models.values() for c in m.get("channels", rm.CH)})
    bad = np.zeros(len(ends_idx), bool)
    for i, e in enumerate(ends_idx):
        xc = ms.clean_window(x[model_slots, e - n:e], fs, rmk.LIGHT_CFG)
        bad[i] = bool(dead[model_slots].any() or (xc.std(1) > a.max_uv).any())
    # 'none' = windows near a segment edge (trimmed) or before the first marker: kept in the CSV, not in the table
    conds = [c for c in ("gauge baseline", "baseline", "mental", "recovery", "physical", "rest") if (lab == c).any()]
    print("windows skipped as bad contact (any model channel > %.0f uV): " % a.max_uv +
          ", ".join(f"{c} {100 * bad[lab == c].mean():.0f}%" for c in conds))
    good = ~bad

    rest_mask = good & np.isin(lab, ["gauge baseline", "baseline", "recovery"])
    task_mask = good & (lab == "mental")
    out = {"t": ends_g, "condition": lab, "bad": bad}
    feats_b, p_b = None, None
    print(f"\n{'':34s}" + "".join(f"{c[:10]:>11s}" for c in conds) + "   AUC mental/recovery   AUC recovery/baseline (drift)")
    for name, m in models.items():
        p, F, _ = replay(m, x, fs, ends_idx, base_idx)
        out["p_" + name[0]] = p
        med = "".join(f"{np.median(p[good & (lab == c)]) if (good & (lab == c)).any() else np.nan:11.2f}" for c in conds)
        a1 = auc(p[good & (lab == "mental")], p[good & (lab == "recovery")])
        a2 = auc(p[good & (lab == "recovery")], p[good & (lab == "gauge baseline")])
        print(f"{name[:34]:34s}{med}   {a1:19.2f}   {a2:24.2f}")
        if name.startswith("B"):
            feats_b, p_b = F, p
    pa, ph = personal(feats_b, rest_mask, task_mask, p_b)
    print(f"\npersonal model on this wearer's own windows (model B's features), time halves: AUC {pa:.2f}; "
          f"averaged with model B: AUC {ph:.2f}")
    if np.isfinite(pa) and pa < 0.65:
        print("  -> even the wearer's own data barely separates rest from the task: fix contact/protocol before models.")

    print("\nfatigue markers, rest blocks only (rest_markers.py):")
    rmk.print_blocks(rmk.session_blocks(raw, a.markers, a.offset, a.trim, a.max_uv, a.baseline))

    stem = os.path.splitext(raw)[0]
    with open(stem + "_compare.csv", "w") as fh:
        keys = list(out)
        fh.write(",".join(keys) + "\n")
        for i in range(len(ends_g)):
            fh.write(",".join(str(out[k][i]) if k in ("condition", "bad") else f"{out[k][i]:.4f}" for k in keys) + "\n")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(11, 3.6))
        colours = {"baseline": "#d9e7f5", "mental": "#f8d9c9", "recovery": "#dcefd9", "physical": "#efe3f7", "rest": "#e8e8e8"}
        for s, e, c in segs:
            ax.axvspan(s, e, color=colours.get(c, "#f2f2f2"), lw=0)
            ax.text((s + e) / 2, 1.02, c, ha="center", va="bottom", fontsize=8, transform=ax.get_xaxis_transform())
        k = 8
        for key, col in (("p_A", "#555555"), ("p_B", "#1a7fb5")):
            v = np.where(good, out[key], np.nan)
            sm = np.array([np.nanmean(v[max(0, i - k + 1):i + 1]) if np.isfinite(v[max(0, i - k + 1):i + 1]).any() else np.nan for i in range(len(v))])
            ax.plot(ends_g, sm, color=col, lw=1.6, label=[nm for nm in models if nm.startswith(key[-1])][0])
        ax.set_ylim(0, 1); ax.set_xlabel("gauge time, s"); ax.set_ylabel("P(load), 8 s mean")
        ax.legend(frameon=False, fontsize=8, loc="upper left")
        for s_ in ("top", "right"):
            ax.spines[s_].set_visible(False)
        fig.tight_layout(); fig.savefig(stem + "_compare.png", dpi=130)
        print(f"\nsaved {stem}_compare.csv and {stem}_compare.png")
    except Exception as e:  # plotting is optional
        print(f"\nsaved {stem}_compare.csv (no plot: {e!r})")


if __name__ == "__main__":
    main()
