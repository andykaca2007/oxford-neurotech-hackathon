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

### Iteration 1, 01:35 to 01:50

- New `tests/replay_all.py`: replays every recording over 60 s (16 files, about 65 min of signal) through the live gauge on port 8799. Result: 0 crashes, 0 NaN rows.
- Bug found and fixed: in a replay the condition carried over from the previous recording (most runs showed "baseline" or "recovery" for their whole length). The gauge now uses the recording's own markers and "none" before the first one; the replay script starts a fresh page server per file.
- `tests/smoke.sh` moved to port 8799, no longer kills processes it did not start, skips the simulated bridge while a live headset session runs, and gained a replay step. ALL PASS. (Paing's 01:21 live run was still running on 8765 and was not touched.)
- True numbers with the live generic model, correct labels: 01:03 run mental 8, physical 4, unlabelled rest 1; 01:15 run mental 10, recovery 23. The generic model does not separate his Zetamac from rest on the 01:15 run.
- Next hypothesis: is there an alpha peak at Pz/O1 at all in his recordings (the only cheap proof that the cleaned signal contains brain).

### Iteration 2, 01:55 to 02:05

- Checks: smoke test ALL PASS; replays of all recordings rerun (see below).
- Hypothesis tested: is there an alpha peak at Pz/O1 in his recordings (evidence that the cleaned signal contains brain)?
  Method: per channel, only windows where that channel is live and under 200 uV after detrend, notch and 2 to 40 Hz; Welch PSD; fit a 1/f line on 3 to 7 and 15 to 30 Hz; report the mean height of 8 to 13 Hz above the line, and a control band 31 to 36 Hz.
  - Lab cap reference (eegmat rest, 36 people, eyes closed): Pz +5.9 dB, O1 +7.4 dB, control band at O1 -5.1 dB.
  - His 16 recordings pooled: Pz 0.0 dB (432 windows), O1 -0.3 dB (365), Cz -0.3, C3 -0.2; control band +0.6 to +2.0 dB, i.e. above the alpha band. Best single runs: 21:17 Pz +2.2 / Cz +2.4; 01:15 O1 +1.3.
  - Reading: no detectable alpha anywhere tonight and a flat spectrum with high-frequency excess (muscle or electrode noise). He had his eyes open, which weakens alpha, so this does not prove there is no brain signal; it means nothing recorded so far proves there is one.
- Decision: no code change from this. It explains why no model (generic or personal) separates Zetamac from rest on these recordings. Next iteration: add a live alpha check to the gauge and page (eyes-closed test with a pass/fail), so a session can prove brain signal in 40 s before any number is trusted.

### Iteration 3, 02:10 to 02:25

- Built from iteration 2's finding: a live **Alpha check** (page button, spoken prompts). 20 s eyes open, then 20 s eyes closed; alpha height above 1/f measured each second on the live posterior channels (Pz, O1, P3, P4); result on the page and in the Terminal. The page also shows the live alpha height.
- Detector validation: lab EEG resampled to 250 Hz reads +5.9 dB at Pz and +6.7 dB at O1 (12 people).
- Pass rule set from data, not guessed. Null test: every possible 40 s check position on his 16 recordings (531 positions, eyes never closed). A 2 dB rise alone passes noise 15 to 20 percent of the time; rise >= 3 dB AND eyes-closed peak >= +3 dB passes noise 0.9 percent of the time. That rule is live.
- End-to-end tests through the live gauge: synthetic replay (his 01:15 noise plus 15 uV of 10.2 Hz at Pz and O1 from 60 s) gives PASS, Pz -0.8 to +6.0 dB; the unmodified 01:15 recording gives FAIL, rise +1.7.
- Checks: smoke ALL PASS, 16 replays 0 failed.
- Decision: keep. First thing on a head tomorrow: baseline, then Alpha check. If it FAILS, no load or fatigue number is trustworthy and the fix is contact, not code.
