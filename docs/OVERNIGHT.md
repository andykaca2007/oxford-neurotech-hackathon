# Overnight log, 8 Nov 2026

Goal from Paing (01:50): check every line, make logical and practical decisions toward a clean signal and true values, loop every 10 minutes until he is back. No head is available overnight, so all work runs on tonight's recordings in `recordings/` via the new replay mode:

```
.venv/bin/python loadmonitor/load_gauge.py --replay recordings/<stamp>_raw_<...>.csv --speed 8 --web --web-port 8799 --no-ui
```

Rules for every change: it must be tested on recorded data with a split that is not confounded by time (rest and task must not simply be "early" and "late"), the smoke test must pass, and the branch must never be left broken. No change is kept because a number looks nicer.

## State at the start (01:50)

- Signal chain: detrend, notch 50/100, median reference, 4 to 30 Hz, Hilbert burst mask, ASR, median Welch. Hum gone, cleaned amplitude 5 to 30 uV.
- Generic model (36 lab subjects, AUC 0.76 cross-subject) does NOT separate Paing's Zetamac from his rest: 01:15 run, mental p 0.54 vs recovery p 0.61.
- Personal model (his baseline vs his first 60 s of Zetamac, shrinkage LDA): looked like 0.98 within a session, but the replay showed recovery reading 77 load: it learned session drift (early vs late), not effort. Turned OFF by default (`--calib-s 0`).
- Labelled data available: 01:15 run (mental 77 to 155 s, recovery 155 to 232 s), 01:03 run (physical 291 to 413 s, mental 413 to 660 s, rest before that unlabelled).

## Iterations
