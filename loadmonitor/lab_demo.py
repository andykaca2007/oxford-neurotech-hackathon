"""Lab EEG demo: one held-out person from the public eegmat dataset, replayed through the live gauge.

    .venv/bin/python loadmonitor/lab_demo.py          # about 5 minutes; then ./run_all.sh lab

Why: the dry cap has not yet given a clean signal, so the demo also shows the exact live pipeline on real EEG (gel cap,
PhysioNet "EEG during mental arithmetic tasks", 36 people) from a person the model never saw.

Steps, all with the live model's settings (5 channels Fz C3 Cz Pz O1, robust cleaning chain, invariant features,
gradient boosting):
  1. leave-one-subject-out: for each of the 36 people, train on the other 35 and score that person's rest windows
     (rest file 30 to 90 s) against their arithmetic windows (task file 0 to 60 s); AUC per person
  2. pick the demo person by a rule fixed before looking: the person at the 75th percentile of that AUC (a case where
     the model works, not the best case); every person's AUC is saved to models/lab_demo_loso.json
  3. train the same model on the other 35 people -> models/readiness_demo.joblib (the live model is not touched)
  4. write demo/lab_eegmat_s<ID>_raw.csv (8 channels, uV, 250 Hz, the format the gauge replays) and its markers:
       0 to 90 s    rest file 0 to 90 s       (the gauge's 30 s baseline, then rest)      condition "baseline"
       90 to 150 s  task file 0 to 60 s       (serial subtraction)                        condition "mental"
       150 to 210 s rest file 90 to 150 s     (the dataset has no rest after the task;    condition "recovery"
                                               this is the same person's earlier rest)
"""
import glob
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "headset"))
os.chdir(ROOT)

import warnings  # noqa: E402
warnings.filterwarnings("ignore")
import joblib  # noqa: E402
from scipy.signal import resample_poly  # noqa: E402
from sklearn.base import clone  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402

import model_search as ms  # noqa: E402
import readiness_model as rm  # noqa: E402
from montage import MONTAGE  # noqa: E402

LIVE = joblib.load("models/readiness.joblib")
CH5 = list(LIVE["channels"])
cfg = LIVE["feat_cfg"]


def main():
    rm.CH[:] = CH5                                   # model_search.CH is the same list object
    X, y, subj = ms.build(4.0, True, True, cfg)
    nb = 6 - int(bool(cfg.get("drop_delta"))) - int(bool(cfg.get("drop_gamma")))
    mask = np.ones(X.shape[1], bool); mask[:nb * len(CH5)] = False; mask[-1] = False      # as --fit-best --invariant
    X = X[:, mask]
    assert mask.sum() == int(np.sum(LIVE["feature_mask"])), "feature layout differs from the live model"
    gb = dict(ms.models())["grad boosting"]
    per = {}
    for s in sorted(set(subj)):
        tr, te = subj != s, subj == s
        p = clone(gb).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
        per[s] = round(float(roc_auc_score(y[te], p)), 3)
        print(f"  person {s}: held-out AUC {per[s]:.3f}", flush=True)
    a = np.array(list(per.values()))
    q75 = float(np.percentile(a, 75))
    pick = min(per, key=lambda s: (abs(per[s] - q75), s))
    rank = int(np.sum(a > per[pick])) + 1
    summary = dict(per_person_auc=per, median=float(np.median(a)), q75=q75, n=len(a), n_over_0_7=int(np.sum(a >= 0.7)),
                   n_under_0_5=int(np.sum(a < 0.5)), pick=pick, pick_auc=per[pick], pick_rank=rank,
                   rule="person closest to the 75th percentile of held-out AUC, chosen before replaying anyone")
    json.dump(summary, open("models/lab_demo_loso.json", "w"), indent=1)
    print(f"held-out AUC over {len(a)} people: median {np.median(a):.2f}, 75th percentile {q75:.2f}, "
          f"{summary['n_over_0_7']} at 0.7 or more, {summary['n_under_0_5']} below 0.5", flush=True)
    print(f"demo person {pick}: AUC {per[pick]:.2f}, rank {rank} of {len(a)}", flush=True)

    keep = subj != pick
    clf = clone(gb).fit(X[keep], y[keep])
    out = dict(LIVE)
    out.update(model=clf, n_subjects=len(set(subj[keep])), held_out=pick,
               rebuild="loadmonitor/lab_demo.py (live settings, person " + pick + " held out)",
               config=dict(LIVE.get("config", {}), model=LIVE.get("config", {}).get("model", "") + f", person {pick} held out"))
    joblib.dump(out, "models/readiness_demo.joblib")
    print("saved models/readiness_demo.joblib", flush=True)

    rm.CH[:] = MONTAGE
    xr, fs = rm.load_edf(f"data/eegmat/Subject{pick}_1.edf")
    xt, _ = rm.load_edf(f"data/eegmat/Subject{pick}_2.edf")
    rm.CH[:] = CH5
    if fs != 250:
        g = np.gcd(int(fs), 250)
        xr = resample_poly(xr, 250 // g, int(fs) // g, axis=1); xt = resample_poly(xt, 250 // g, int(fs) // g, axis=1)
    fs = 250
    assert xr.shape[1] >= 150 * fs and xt.shape[1] >= 60 * fs, (xr.shape, xt.shape)
    x = np.concatenate([xr[:, :90 * fs], xt[:, :60 * fs], xr[:, 90 * fs:150 * fs]], axis=1)
    os.makedirs("demo", exist_ok=True)
    raw = f"demo/lab_eegmat_s{pick}_raw.csv"
    with open(raw, "w") as f:
        f.write(f"# lab EEG demo: PhysioNet eegmat person {pick} (gel cap), held out of models/readiness_demo.joblib; "
                f"0-90 s rest, 90-150 s mental arithmetic, 150-210 s rest from the same person's earlier rest recording\n")
        f.write("t," + ",".join(MONTAGE) + "\n")
        for k in range(x.shape[1]):
            f.write(f"{k / fs:.3f}," + ",".join(f"{v:.2f}" for v in x[:, k]) + "\n")
    with open(re.sub(r"_raw\.csv$", "_gauge_markers.csv", raw), "w") as f:
        f.write("t,condition\n0.0,baseline\n90.0,mental\n150.0,recovery\n")
    print(f"wrote {raw} ({x.shape[1] / fs:.0f} s) and its markers", flush=True)


if __name__ == "__main__":
    main()
