# Andy's load model (v2), and how to compare it with the live one

Written Sun 8 Nov 2026, 02:00, on branch `andy/load-model-v2` (from `paing/readiness` at e80b348).
Nothing in the live gauge changed: the new model is a separate file that `load_gauge.py` already loads with `--model`.

## What is different, and why

| | live model (`model_search.py --fit-best --robust --invariant`) | v2 (`andy_model.py`) |
|---|---|---|
| Cleaning | detrend, notch, 4-30 Hz order 8, **median common reference**, **burst masking**, **artefact subspace reconstruction** | detrend, notch, 3-30 Hz order 4. Nothing else |
| Bad data | repaired (masked, reconstructed) | skipped (compare_models.py `--max-uv`; the gauge already holds on noisy channels) |
| Features | 44 amplitude-invariant, minus the wearer's baseline | the same 44 |
| Classifier | gradient boosting | gradient boosting (chosen over logistic regression on subjects 0-17 only) |
| Personal data | none | tested: ~30 s of the wearer's own rest + ~30 s of their own task |
| Fatigue | live dial, (theta+alpha)/beta drift within the session | rest blocks only, theta and alpha shares, comparable across sessions (`rest_markers.py`) |

Why drop the extra cleaning, checked on the 36 public subjects:
- The **median common reference** keeps only **18%** of resting alpha power at Pz (36% over Pz, P3, P4, O1; range 16-51%).
  It subtracts what most electrodes share, and alpha and theta are shared by most electrodes.
- **Burst masking** blanks high-amplitude alpha and theta bursts, which is what drowsiness looks like.
- Together they did not buy accuracy on the public data (table below).

Why fatigue moves to rest blocks:
- (theta+alpha)/beta **falls during the sums in 30 of 36 subjects** (x0.83 on average), so the live dial reads
  "Recovering" exactly when load is high.
- Frontal theta rises with effort as well as with fatigue; only at rest does a rise mean tiredness. Fatigue shows
  better in resting recordings, and relative power is more sensitive there (Li et al. 2020, BMC Neuroscience).
  Theta is the strongest EEG marker of mental fatigue (Tran et al. 2020, Psychophysiology, 21 studies).
- The live dial restarts at 50 every session, so it cannot compare tonight with tomorrow; the rest-block numbers can.

What neither model can fix: the public data is **eyes-closed rest in a dark soundproof room** and **silent sums**
(Seleznov et al. 2019, the same 36 people). Live use is eyes open at a screen, often answering aloud.
That is what the personal-calibration test is for.

## Results on the public data, same protocol for both

PhysioNet eegmat, 36 people, 4 s windows with 50% overlap, baseline-relative, leave one subject out.
"Reporting half" = subjects 18-35, never used to choose anything.

| | live chain + boosting | v2 light chain + boosting |
|---|---|---|
| AUC, all 36 left out in turn | 0.762 | 0.764 |
| balanced accuracy, all 36 | 0.671 | 0.684 |
| AUC, reporting half (18-35) | **0.786** | 0.765 |
| **Personal calibration** (later windows of each held-out person) | | |
| public model only | 0.751 | 0.736 |
| personal model only (~30 s rest + ~30 s task of that person) | **0.922** | 0.899 |
| average of the two | 0.912 | 0.883 |

Reading it honestly:
- **The two chains are level on lab data**: 0.762 vs 0.764 over all 36; the live chain is ahead on the reporting
  half (0.786 vs 0.765). So the extra cleaning neither helps nor hurts on clean gel-cap recordings. What it removes
  (alpha at the back, theta and alpha bursts) matters for live dry-cap use and for fatigue, which lab scores
  cannot show: that has to be judged on your own sessions with `compare_models.py`.
- **The big gain is personal calibration**, with either chain: about **+0.15 to +0.17 AUC from half a minute of
  each condition**, slightly more with the live chain (0.922).
Caveat: in this dataset rest and task are separate recordings, so part of what a personal model learns may be
recording differences. Your own continuous sessions are the real test, and `compare_models.py` runs exactly that,
with a drift control.

## How to compare (Paing's Mac, from the repo root)

1. Build the model (about 3 minutes; needs data/eegmat, scikit-learn, pyedflib, joblib, like model_search.py):
   `.venv/bin/python loadmonitor/andy_model.py` -> `models/andy_load.joblib`
2. Replay any recorded session through both models, plus a personal model and the fatigue blocks:
   `.venv/bin/python loadmonitor/compare_models.py --raw "recordings/NAME_STAMP_raw_*.csv" --markers recordings/NAME_STAMP_gauge_markers.csv`
   Writes `..._compare.csv` (per window) and `..._compare.png` (both models over time, segments shaded).
3. Same recording through the real gauge, once per model (the overnight replay mode):
   `.venv/bin/python loadmonitor/load_gauge.py --replay "recordings/NAME_STAMP_raw_*.csv" --speed 8 --no-ui --model models/andy_load.joblib`
   then again with the default model. Live: add `--model models/andy_load.joblib` to the usual command.
4. Fatigue, tonight vs tomorrow (same person, same cap fit method):
   `.venv/bin/python loadmonitor/rest_markers.py --session "RAW1" MARKERS1 tonight --session "RAW2" MARKERS2 tomorrow`

## Reading compare_models.py

| line | good | bad, and what it means |
|---|---|---|
| windows skipped as bad contact | under 20% per condition | high: fix contact (gel) before reading anything else |
| AUC mental vs recovery | 0.7 or more | near 0.5: the model cannot tell the task from rest after it |
| AUC recovery vs baseline (drift) | near 0.5 | as high as the line above: it reads time and contact drift, not the task |
| personal model AUC | high | near 0.5: the recording itself does not separate rest from task (contact or protocol); no model fixes that |
| personal high, public low | | the public data does not transfer (eyes closed, dark room): add a short personal calibration to the live flow |

## What the overnight log (docs/OVERNIGHT.md) changes

- **No alpha peak in any recording so far** (Pz 0.0 dB, O1 -0.3 dB above 1/f, against +5.9 and +7.4 dB in the lab
  data), with excess high-frequency power. Until a session shows an alpha peak (eyes closed for 30 s), no model,
  this one included, has brain signal to work with. Fix contact first: gel, `--strict`, under 100 uV.
- **Personal calibration learned drift on Paing's session** (baseline, then Zetamac: recovery then read 77).
  That design has rest only BEFORE the task, so "later" and "load" look the same. `compare_models.py` puts rest on
  both sides of the task (baseline and recovery) in its personal test, so drift alone cannot score high there,
  and it prints the recovery-vs-baseline drift control. For a live calibration step, use rest, task, rest.

## Limits
- Every number above is lab data (gel cap, eyes closed). Nothing here is validated on the Unicorn yet.
- The fatigue markers are measured contrasts, not a trained model: there is no labelled fatigue data.
- 36 public subjects; the person-to-person spread is large (personal AUC +/- 0.11, public +/- 0.19).

Code written with Claude (AI assistant) during the event, directed by Andy. Data: Zyma et al. 2019, PhysioNet eegmat.
