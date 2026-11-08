"""Compare electrode layouts for the load model (Andy's docs/ELECTRODE_LAYOUT.md), honestly.

    .venv/bin/python loadmonitor/layout_compare.py

Layouts (what sits in the 8 cap slots):
  now: Fz C3 Cz C4 Pz                 (PO7 POz PO8 unused: not in eegmat)
  A:   Fz C3 Cz C4 Pz P3 P4 O1        (move PO7->P3, PO8->P4, POz->O1)
  B:   Fz F3 F4 Cz Pz P3 P4 O1        (A, plus C3->F3, C4->F4)
Pipeline = the current winner (4 s, 50% overlap, rich features, gradient boosting).
Scores: leave-one-subject-out over all 36 (for the table), and the strict version: choose the
layout on subjects 0 to 17, report it on subjects 18 to 35.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import readiness_model  # noqa: E402
import model_search  # noqa: E402

LAYOUTS = {
    "now (5)": ["Fz", "C3", "Cz", "C4", "Pz"],
    "A (8)": ["Fz", "C3", "Cz", "C4", "Pz", "P3", "P4", "O1"],
    "B (8)": ["Fz", "F3", "F4", "Cz", "Pz", "P3", "P4", "O1"],
}


def main():
    import pyedflib
    f = pyedflib.EdfReader("data/eegmat/Subject00_1.edf")
    labels = [l.replace("EEG ", "").strip() for l in f.getSignalLabels()]
    f.close()
    print("EDF labels:", labels)
    results = {}
    for name, ch in LAYOUTS.items():
        missing = [c for c in ch if c not in labels]
        if missing:
            print(f"{name}: missing in eegmat {missing}, skipped")
            continue
        readiness_model.CH[:] = ch           # both modules read this list
        model_search.CH[:] = ch
        X, y, subj = model_search.build(4.0, True, True)
        clf = dict(model_search.models())["grad boosting"]
        acc, sd, auc, tr = model_search.loso(clf, X, y, subj)
        subs = np.unique(subj)
        half1, half2 = np.isin(subj, subs[:18]), np.isin(subj, subs[18:])
        a1, _, u1, _ = model_search.loso(clf, X[half1], y[half1], subj[half1])
        a2, _, u2, _ = model_search.loso(clf, X[half2], y[half2], subj[half2])
        results[name] = dict(acc=acc, sd=sd, auc=auc, train=tr, acc1=a1, auc1=u1, acc2=a2, auc2=u2, nf=X.shape[1])
        print(f"{name:8s} all-36 LOSO: bal acc {acc:.3f} +/- {sd:.3f}  AUC {auc:.3f}  (train {tr:.3f}) | "
              f"first half: acc {a1:.3f} AUC {u1:.3f} | second half: acc {a2:.3f} AUC {u2:.3f}  features {X.shape[1]}", flush=True)
    if results:
        pick = max(results, key=lambda k: results[k]["auc1"])
        r = results[pick]
        print(f"\nSTRICT: layout chosen on subjects 0-17 = {pick}; its score on subjects 18-35: bal acc {r['acc2']:.3f}, AUC {r['auc2']:.3f}")
        base = results.get("now (5)")
        if base:
            print(f"        'now' on the same held-out half: bal acc {base['acc2']:.3f}, AUC {base['auc2']:.3f}")


if __name__ == "__main__":
    main()
