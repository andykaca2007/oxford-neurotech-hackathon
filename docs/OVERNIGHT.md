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

### Iteration 4, 02:30 to 02:40

- Hypothesis: is ASR over-cleaning (the 5 uV residual)? Test: ASR calibrated on 0 to 28 s of rest, then count components removed and amplitude kept, on lab rest, lab task and his labelled segments.
  - Lab, 36 people: 0 percent of windows touched, rest and mental arithmetic alike; amplitude kept 100 percent.
  - His 01:15 run: Zetamac 100 percent of windows touched (1.0 component each, 95 percent amplitude kept); recovery 51 percent (0.6).
  - His 01:03 run: Zetamac 100 percent (3.3 components, 87 percent kept); physical 100 percent (2.9); rest 23 percent (0.5).
- Reading: ASR is not over-cleaning; it never touches clean EEG and keeps 87 to 100 percent of his amplitude. But it fires on every Zetamac window: typing and looking between screen and keys add task-locked eye and muscle artefact. The model was trained on silent mental subtraction, so Zetamac confounds effort with movement.
- Decision: no code change. docs/PROTOCOL.md changed: the mental segment is now silent serial subtraction with eyes on a fixed point, no typing; Alpha check added as step 0. The ASR component count is NOT used as a load signal (it measures movement).
- Checks: smoke ALL PASS, 16 replays 0 failed.

### Iteration 5, 02:45 to 03:05

- Hypothesis A: channels flipping live/dead mid-session move the load. Test: per-second live set from the raw files against the replay gauge logs. Load change per second 0.71 when a channel flipped in the window (n 649) versus 1.08 when stable (n 2287). Rejected.
- Usable channels, share of seconds live over all 16 recordings: Fz 0.81, C3 0.79, Cz 0.81, Pz 0.83, O1 0.83; C4 slot 0.55, P3 slot 0.55, P4 slot 0.42.
- Hypothesis B: a model on only the five reliable channels loses nothing. Lab LOSO, same robust chain: 5 channels AUC 0.762, bal acc 0.681, train 0.816, 29 features; live 8-channel model AUC 0.762, bal acc 0.671, train 0.836, 44 features. Supported: same accuracy, less overfitting, never reads the flaky slots.
- Decision: live model is now the 5-channel one (`models/readiness.joblib`; 8-channel backup `models/readiness_8ch_robust.joblib`). Page clean count uses the model's channel count.
- Replays with the 5-channel model, labelled runs (8-channel in brackets): 01:03 mental 8 (8), rest 3 (1), physical 13 (4); 01:15 mental 4 (10), recovery 7 (23). Neither model separates his Zetamac from rest (iterations 2 and 4 explain why); the 5-channel one reads lower during recovery.
- Bugs found by the replays and fixed: a recording with no live channels at all (23:03) wrote no CSV rows because the header was only written after a scored window (the 8-channel model had been scoring rail data there); held seconds are now logged, and fatigue shows its start value of 50 instead of 0 before the first scored window. Held message says N of 5, not N of 8.
- Checks on the final code: smoke ALL PASS, 16 replays 0 failed (23:03 now logs 85 held rows).

### Iteration 6, 03:10 to 03:25

- Fixed: `tests/replay_all.py` ran the gauge with default settings (alarm 70, smoothing 8), not the ones `run_all.sh` launches (alarm 50, hold 20, smoothing 12). Replays now use the live settings and report alarm seconds per condition.
- Live settings over all 16 recordings: 0 alarm seconds out of about 3,100 scored seconds (no false alarms at rest; also none during his Zetamac).
- Hypothesis: the fatigue ratio tracks artefact. Test: per-window Spearman correlation, within each of 11 recordings over 90 s, between the gauge's fatigue ratio (computed exactly as the gauge does) and raw amplitude, ASR removals and muscle share (30 to 45 Hz over 4 to 30 Hz).
  - Median rho: muscle share -0.43, raw amplitude +0.22, ASR removals +0.04. Supported: muscle leaks into the 13 to 30 Hz beta denominator, so tensing reads as "recovering"; larger raw amplitude reads as "tiring".
  - Candidate fixes on the same data: beta 13 to 20 Hz gives muscle -0.38, amplitude +0.19, per-window sd 0.33 (current 0.40); a muscle gate (skip windows with 30 to 45 Hz over half of 4 to 30 Hz) keeps 80 percent of windows and makes the amplitude coupling worse (+0.37).
- Decision: no change. The 13 to 20 Hz gain is small and would leave the published (theta+alpha)/beta definition the page cites; the gate is worse. Fatigue on this cap carries artefact under every variant tested; the honest fix is contact. Checks: smoke ALL PASS, 16 replays 0 failed.

### Iteration 7, 03:30 to 03:50

- Problem: every labelled recording is a block design (all mental, then all rest), so any slow drift looks like a condition difference; that is what fooled the 01:50 personal model. No existing recording can test load separation without this confound.
- Built: **Calibrate** button. 8 blocks of 20 s, rest and silent subtraction alternating (spoken prompts, a new start number each task block), first 5 s of each block skipped for the 4 s window lag. Leave-one-pair-out: train on three rest/task pairs, score the held-out pair, average over the four pairs. The personal model (shrinkage LDA on the live features) replaces the generic one only if that held-out AUC clears the bar; the page shows the score either way. Rebaseline clears it.
- Null test, as for the alpha check: the identical calibration run at every possible start on his recordings, where he never alternated (81 positions): median AUC 0.46, 95th percentile 0.70, 99th 0.75, none at 0.80 or above. The first single null run (01:03 recording from 40 s) gave 0.69, which is why the bar is not 0.75. Bar set to 0.80.
- Mechanics: fake data completes and reports OFF (0.40); null replay reports OFF (0.69).
- Protocol: Calibrate added as optional step 1b after a passing Alpha check.
- Checks: smoke ALL PASS, 16 replays 0 failed.

### Iteration 8, 03:55 to 04:10

- Hypothesis: the 0.80 calibration bar is so strict that a real effect cannot pass it. Positive control: interleaved sessions built from the lab data, alternating each subject's real rest (20 s blocks from 30 s on) with their real mental arithmetic (20 s blocks), 3 pairs, the same leave-one-pair-out LDA on the live 5-channel features, baseline from the first 25 s of rest.
  - 35 subjects (1 skipped, arithmetic recording under 60 s): median held-out AUC 0.95, 25th to 75th percentile 0.88 to 0.99; 91 percent reach 0.80.
  - Against the null from iteration 7 (his non-alternating recordings: 0 of 81 reach 0.80), the bar separates real effects from chance well.
  - Caveat: rest and arithmetic come from two separate recordings of one session, so recording-to-recording differences may add to the separation; treat 91 percent as optimistic.
- Decision: no change. Bar stays at 0.80.
- Checks: smoke ALL PASS, 16 replays 0 failed.

### Iteration 9, 04:15 to 04:30

- Hypothesis: the load mapping tuned on the old 8-channel model still works with the live 5-channel model and the launched settings (gain 40, smoothing 12, median of 5, alarm 50 held 20 s). Test: 36 lab subjects, leave-one-subject-out, exact live mapping.
  - Gain 40 (live): rest median load 0, 0.1 percent of rest seconds in alarm; arithmetic median 31, 18 percent of task seconds in alarm, 44 percent of people get an alarm, 64 percent read 20 or more above their rest.
  - Gain 30: task median 23, 33 percent alarm. Gain 50: task 39, still 44 percent alarm, rest false alarms 0.6 percent. Gain 60: task 46, 50 percent alarm, rest false alarms 1.2 percent.
- Decision: keep gain 40. 50 adds no people and six times the false alarms.
- Checks: smoke ALL PASS, 16 replays 0 failed.
- The offline hypotheses are exhausted (alpha, ASR, channels, fatigue, interleaving, calibration bar, mapping). From iteration 10 the loop only re-runs the checks and fixes what fails; no new code without new data.

## Morning summary for Paing

1. (Corrected 8 Nov, CRITIQUE fatigue-adv2: three of these 'passing' replays had load and fatigue stuck at 0 with every feature zeroed; replay_all now fails such sessions, and the strict channel gate of 6b5deb6 holds them instead.) Nothing on the software side is blocking a session. Every check passes; all 16 of last night's recordings replay through the live gauge with no crash and no NaN. On these recordings, which the chain was tuned on, it never alarms, at rest or during his task: that shows it no longer drifts upward, not that it detects load. False-alarm rates will be reported only from sessions recorded after the chain is frozen (CRITIQUE claims-5).
2. The blocker is the signal. Last night's recordings contain no detectable alpha (Pz 0.0 dB, O1 -0.3 dB above background; lab eyes closed +6 to +7 dB), and the spectrum is noise-like. Zetamac adds typing and gaze artefact on top (ASR fires on every Zetamac window).
3. Session order, all on the page: Rebaseline when settled, then **Alpha check**. FAIL means fix contact (mastoid stickers on wiped skin, amplifier pressed and strapped, hair parted, 2 min still), not code. PASS means the electrodes see brain.
4. After a PASS: **Calibrate** (160 s, spoken prompts). The personal model switches on only at held-out AUC 0.80 or above. Corrected 8 Nov (CRITIQUE stats-2): with independent runs, chance reaches 0.80 about 1 time in 10 (1 of 8 runs on his recordings, 2 of 35 lab rest-only), and a real rest/arithmetic difference about 8 times in 10 (29 of 35 lab subjects, optimistic). A pass means his rest and task blocks were separable, not that load is measured. Re-run with tests/calib_null.py.
5. Then the demo task is **silent** counting down in sevens with eyes on one point, not Zetamac. Lab numbers for the live mapping: rest reads 0, arithmetic median 31, about 4 in 10 people trigger the alarm.
6. Fatigue is a published ratio, not a trained model, and on this cap it follows muscle artefact (rho -0.43); present it as "slow trend this session", never as a measurement of tiredness.
7. Fallback if the cap will not pass: `./run_all.sh replay recordings/<file>_raw_<stamp>.csv` (or the VS Code task RUN REPLAY) streams a recorded session through the full live pipeline; the page shows REPLAY and a banner with the file name (added 8 Nov after CRITIQUE claims-2). Last night's recordings show no clear task effect, so say that when using it.

### Iteration 10, 02:58: checks only. No new recordings (latest 01:21, 32 s; that live run is still open in his Terminal, untouched). Smoke ALL PASS, 16 replays 0 failed. No code change.

### Iteration 11, 03:08: checks only. No new recordings. Smoke ALL PASS, 16 replays 0 failed. No code change.

### Iteration 12, 03:18: checks only. No new recordings. Smoke ALL PASS, 16 replays 0 failed. No code change.

### Iteration 13, 03:28: checks only. No new recordings. Smoke ALL PASS, 16 replays 0 failed. No code change.

### Iteration 14, 03:38: checks only. No new recordings. Smoke ALL PASS, 16 replays 0 failed. No code change.

### Iteration 15, 03:48: checks only. No new recordings. Smoke ALL PASS, 16 replays 0 failed. No code change.

### Iteration 16, 03:57: checks only. No new recordings. Smoke ALL PASS, 16 replays 0 failed. No code change.

### Iteration 17, 04:07: checks only. No new recordings. Smoke ALL PASS, 16 replays 0 failed. No code change.

### Iteration 18, 04:17: checks only. No new recordings. Smoke ALL PASS, 16 replays 0 failed. No code change.

### Iteration 19, 04:27: checks only. No new recordings. Smoke ALL PASS, 16 replays 0 failed. No code change.

### Iteration 20, 04:37: checks only. No new recordings. Smoke ALL PASS, 16 replays 0 failed. No code change.

### Iteration 21, 04:47: checks only. No new recordings. Smoke ALL PASS, 16 replays 0 failed. No code change.

### Iteration 22, 04:57: checks only. No new recordings. Smoke ALL PASS, 16 replays 0 failed. No code change.

### Iteration 23, 05:08: checks only. No new recordings. Smoke ALL PASS, 16 replays 0 failed. No code change.

### Iteration 24, 05:18: checks only. No new recordings. Smoke ALL PASS, 16 replays 0 failed. No code change.

### Iteration 25, 05:27: checks only. No new recordings. Smoke ALL PASS, 16 replays 0 failed. No code change.

### Iteration 26, 05:38: checks only. No new recordings. Smoke ALL PASS, 16 replays 0 failed. No code change.

### Iteration 27, 05:47: checks only. No new recordings. Smoke ALL PASS, 16 replays 0 failed. No code change.

### Iteration 28, 05:58: checks only. No new recordings. Smoke ALL PASS, 16 replays 0 failed. No code change.

### Critique round, 06:41: 20 agents, then the first fix

- 10 critics (one area each) and 10 adversaries (each tried to refute one critic, re-reading code and re-running checks): 66 critic findings, 60 confirmed, 6 refuted; 24 more added by adversaries. Ranked list with full evidence in docs/CRITIQUE.md.
- Fixed the top cluster, one root cause behind CRITIQUE fatigue-1, dsp-1, dsp-2, dsp-3, fatigue-adv1, gauge-1, gauge-adv1, model-adv1, gauge-adv2: dead or partly railed channels were detected from the window mean (never fired after mean removal), turned into minus the reference (a plausible fake trace that the model scored: losing Fz moved p by +0.29, about 70 to 86 load points), and allowed into the baseline and the ASR fit.
  - Now: rails detected per sample on the raw window; dead channels zeroed after referencing; the load is held (CHANNEL LOST) whenever any model channel is dead; baseline and ASR fit skip such windows; --strict compares with the model's 5 channels (it could never pass before); a channel zeroed by ASR is not counted clean; ASR has a reference floor.
  - Evidence: lab features unchanged (max difference 0.0, so no retrain); scored seconds with a dead model channel in the window: 154 windows before, 1 of 1826 after (window-edge alignment); 571 seconds now held. Four recordings never get 30 clean baseline seconds and are now held throughout instead of scored on invented channels; replay_all counts that as correct.
  - Checks: smoke ALL PASS, 16 replays 0 failed.

### Critique iteration 2, 06:48

- CRITIQUE #3 claims-1: PLAN.md's claim line ("75%, AUC 0.84, and shows it live") described an older model and a live result we do not have. Replaced with the live model's lab numbers (AUC 0.76, balanced accuracy 68%, at chance for about 1 in 6 people) and the honest limits (no alpha on the cap, no reliable task separation on his recordings); HANDOFF.md and RESULTS.md carry a superseded note.
- CRITIQUE #4 claims-2, #17 serverpage-1, #15 ops-4, ops-adv2: the replay fallback was shown as "live". The page now shows a REPLAY pill and a fixed banner with the recording's file name (checked in the browser on port 8799); the debrief and coach get replay and are told to say it is a recording; `./run_all.sh replay <file>` and a VS Code task start it at real time with the live alarm settings. The alarm label in the load panel now follows the gauge (it said 70 while the gauge alarms at 50). The LLM context number for arithmetic was 45 (old model), now 31.
- Checks: smoke ALL PASS, 16 replays 0 failed; the replay launcher refuses a missing file before touching any running process.

### Critique iteration 3, 07:00

- CRITIQUE #8 fatigue-2: with fewer than 5 clean baseline windows fatigue fell back to the lab-cap mean (0.593) or a 1 to 4 window median with an invented sd of 0.1, which produced false 'Tiring' (22:36 recording, 47 of 212 rows at 70 or above) and 'Recovering'. Now fatigue needs 15 clean baseline windows, else it is off and the page says "no fatigue baseline, press Rebaseline". Replays: 22:36 now OFF (6 windows); 00:52 and 01:15 pass (28 windows).
- CRITIQUE #9 fatigue-3: with 180 s smoothing and baseline-spread scoring, nothing physiological moves the index in a 3-minute demo (lab rest stays 45 to 55; his sessions step 0.2 to 0.4 log10 between baseline and first minute with no task). The number is now hidden until 20 minutes of monitoring; the card says "trend needs 20 min of monitoring, N min to go". Rebaseline resets it.
- Checks: smoke ALL PASS, 16 replays 0 failed.
- Correction, 07:06: commit 9deb14d was pushed with two smoke failures (my commit command did not stop on them): the page server crashed when the gauge posted fatigue=None, so condition markers and the debrief failed. Fixed in the next commit; smoke ALL PASS, 16 replays 0 failed. From now on commits are gated on the smoke test's exit code.

### Critique iteration 4, 07:15

- CRITIQUE #13 ops-1 and #14 ops-2: when the headset stopped sending (gPype logs show 3 fatal and 4 transient dropouts last evening), the gauge blocked forever in an LSL read with no timeout, the page kept the last number, Ctrl-C could not reach Python, and a forgotten gauge would wake up on the next session's stream.
  - Now: the read times out after 1 s; after 2 s without data the gauge posts, prints and speaks NO DATA; the server reports the age of the last update and the page shows a red NO DATA overlay and blanks the number when the age is over 3 s or the server does not answer; run_all.sh stops leftover gauges and launchers (not itself or its parent shell) before starting and cleans up on exit.
  - Tested with a test-only --stall-after on the fake source (his stale bridge still owns the Unicorn stream name, so the live path was not used): NO DATA after 2 s, Ctrl-C stops the gauge within 2.5 s with no traceback, page age passes 3 s once the gauge stops. Added as a smoke step.
  - Note for the morning: run_all.sh will now stop the 01:21 processes still running in his Terminal when he next launches; closing that Terminal first is still cleaner.
- Checks: smoke ALL PASS (new stall step included), 16 replays 0 failed; commit gated on both exit codes.

### Critique iteration 5, 07:21

- CRITIQUE #18 serverpage-2: the debrief's only quality evidence was the clean-channel count, which is high (4.8 of 5 on the 01:15 run) on a recording that FAILS the Alpha check; the Alpha check, calibration and personal-model results never reached it. Now the summary carries them as evidence (brain_signal_shown is true only after a passed Alpha check), the LLM context says the clean count is amplitude only, and both templates open with "Unverified: the Alpha check has not passed" until it does. Unit-checked with a FAIL and a PASS.
- CRITIQUE #45 serverpage-4 (same lines): the debrief counted and quoted 70 while the gauge alarms at 50; now it uses the gauge's alarm level. The page's held subtitle said "of 8 channels" and "3 or more"; it now says N of 5 and when load resumes. A replay is named in the template.
- Checks: page JavaScript parses; smoke ALL PASS; 16 replays 0 failed; commit gated on both.

### Critique iteration 6, 07:30

- CRITIQUE #19 alpha-1: the +3/+3 rule was set from the null only. Injection tests by the critic and the adversary (real lab eyes-closed alpha, about 7 uV, added to his closed phase) pass about 19 percent of checks at eyes-open 8 to 13 Hz noise over 30 uV, about 31 percent at 8 to 30 uV, about half at 2 to 8 uV, 73 percent under 2 uV. So a FAIL at high noise cannot tell "no brain" from "too noisy".
  - Now the check measures eyes-open 8 to 13 Hz RMS at the quietest live posterior channel. Over 15 uV the result is TOO NOISY TO TEST, with the measured noise and the target. Under it, PASS and FAIL as before with the noise shown, and FAIL says a real brain passes only about half the time at that noise, so repeat once.
  - My noise measure across all 16 recordings: median 10.9 uV per window (48 percent under 10, 24 percent over 50), in line with the critic's buckets. The 01:15 recording is a quiet one (median 3.8 uV): its FAIL (rise +1.6) is a real no-alpha result at low noise. The synthetic case still PASSes (noise 4 uV).
  - Thresholds unchanged: per the adversary no noise level reaches 80 percent sensitivity under the +3/+3 rule, so that needs a longer check or a different rule, not a gate.
- claims-adv2 (same lines): the spoken result said "Brain signal confirmed"; now "Alpha rhythm found".
- Checks: smoke ALL PASS; 16 replays 0 failed; commit gated.

### Critique iteration 7, 07:40

- CRITIQUE #20 calib-1: once a calibration passed, load was 100 x the LDA probability with no rest anchor; shrinkage-LDA probabilities are near 0 or 1, and the alarm at 50 sat on the decision boundary. Now the rest anchor is the mean and spread of the out-of-fold rest scores from the calibration itself, on the LDA decision value (log-odds), mapped with the same gain per spread as the generic model; and the personal model only scores when every model channel is clean (it is linear, one noisy channel moves it a lot), otherwise the load holds.
  - Test, the critic's own setup: lab subjects, 3 interleaved rest/arithmetic pairs, personal model run over 82 s of held-out rest. 28 pass 0.80. Borderline passes (AUC 0.80 to 0.90, n 9): rest median 17.2 to 2.0, seconds at 50 or above 11 to 0 percent, people with a false alarm 2 to 0. All 28: median 7.3 to 4.8, false alarms 2 to 0.
- CRITIQUE #21 calib-2, calib-adv1, serverpage-adv1: a failed second calibration left the first personal model running while the text said "keeping the generic model", and after Rebaseline the page kept showing the old result. Now a new calibration drops any personal model first, and the page row says "personal model ON" or "generic model" from the gauge's own flag, plus the last calibration result.
- Checks: page JavaScript parses; smoke ALL PASS; 16 replays 0 failed; commit gated.

### Critique iteration 8, 07:49

- CRITIQUE #24 claims-3 (with fatigue-4, serverpage-8): fatigue words were 'Tiring' / 'Recovering' although the ratio follows muscle artefact; now 'above start' / 'near start' / 'below start'. The alarm said 'High mental load, take a break' on screen and aloud, advice from an unvalidated number; now 'Load held above the alarm line' / 'Load above the line'. The model tile read like live accuracy; now 'lab AUC 0.76 (36 people), not validated on this cap'. The alpha reference said 'lab eyes closed', which readiness_model.py contradicts; now 'lab rest'. (The alarm label and 'of 8 channels' parts were already fixed in iterations 2 and 5.)
- CRITIQUE #25 claims-4: the LLM context said '8-electrode' and asked for a supervisor recommendation; now 'the model uses 5 of its 8 electrodes' and one next step for the session, no health or work advice, confidence from the evidence first. Every Claude text was credited to claude-opus-5-5, and a refusal returned template text under that label; now the source names the model actually used (Opus for the debrief, Sonnet for the live line) and a refusal says 'template (model refused)' (checked with a stub client). The live coach prompt now also receives the evidence and replay flag. The --gain help had the old 8-channel numbers (stats-adv3); updated to the 5-channel sweep.
- Checks: page JavaScript parses; smoke ALL PASS; 16 replays 0 failed; commit gated.

### Critique iteration 9, 07:59

- CRITIQUE #26 claims-5: the morning summary's "no false alarm on 16 recordings" read as specificity, but the chain was tuned on those same recordings and never alarms on them during his task either. Reworded: it shows the gauge no longer drifts upward, not that it detects load; false-alarm rates only from sessions after the chain is frozen.
- CRITIQUE #27 claims-7: PROTOCOL.md said it was written at 21:30 before any session; git shows it was committed at 20:35, before the first protocol recording (20:51), which is the stronger and true statement. The 8 Nov amendments (task, Alpha check, Calibrate, alarm 50) are now marked as made after seeing the data. Stale lines fixed (alarm 70, "peak during Zetamac"); the claim line now reports N honestly (0 of 1 as of 8 Nov). PLAN.md's demo used spoken answers typed by a teammate and claimed "strain shows before the mistakes"; now silent subtraction, claim removed.
- CRITIQUE #28 claims-8: the README described the explored SSVEP aid, linked HANDOFF.md and RESULTS.md at the wrong path, and named a unicorn/ folder that does not exist. Rewritten for the load monitor with the lab-only numbers and limits, links fixed, provenance line names the real folders.
- Checks: smoke ALL PASS, 16 replays 0 failed.

### Critique iteration 10, 08:11

- CRITIQUE #30 dsp-4: the order-8 band-pass leaves transients in the first and last 0.5 s of each 4 s window; on his data the Hilbert burst mask flagged 30 and 24 percent of those edges (5.8 percent mid-window; lab EEG under 1 percent), zeroing real signal. Now the mask does not flag the first and last 0.5 s.
  - Effect on his live windows (n 584): fully zeroed samples 9.4 to 3.2 percent; alpha power lost through the mask -2.15 to -1.71 dB (the rest is the mask working on mid-window artefact).
  - The change moves some lab features (up to 1.7 within-subject sd; model output up to 0.12 at the 99th percentile), so the 5-channel model was retrained on the corrected chain: LOSO AUC 0.760, balanced accuracy 0.679 (was 0.762, 0.681; same within noise). Previous model kept as models/readiness_5ch_pre_edgefix.joblib (models/ is local, not in git).
- Checks: smoke ALL PASS; 16 replays 0 failed; commit gated.

### Critique iteration 11, 08:19

- CRITIQUE #35 gauge-2: the head map's per-channel baseline averaged dead seconds as log10(0) = -12, so a channel that was dead for part of the baseline later read +100 to +200 dB as a "change from baseline" (critic: top channel median +147 dB on 01:03, +119 dB on 01:15). Now each channel's baseline uses only its live seconds, and a channel with fewer than 10 live baseline seconds shows "no base". Sampled live on replay: the top channel now reads -24 to +13 dB on 01:03 and -14 to +13 dB on 01:15. Display only; load, fatigue and alarm never used it.
- CRITIQUE #36 gauge-3: already fixed by iteration 3 (no lab-mean fallback, 15 clean windows) and the dead-channel fix (ASR on a dead baseline); marked done with those commits.
- Checks: page JavaScript parses; smoke ALL PASS; 16 replays 0 failed; commit gated.

### Critique iteration 12, 08:30

- CRITIQUE #38 model-3: the live 5-channel model had been built from inline scripts; no committed command rebuilt it, models/ is not in git, and the documented commands (--fit-best, --fit-best --invariant) silently overwrote models/readiness.joblib with a different model. Now --fit-best takes --channels, --out (default models/readiness_candidate.joblib, so the live model is only replaced on purpose) and --skip-loso, and stores the command line in the joblib. Rebuild of the live model: `.venv/bin/python loadmonitor/model_search.py --fit-best --robust --invariant --channels Fz,C3,Cz,Pz,O1 --out models/readiness.joblib`. Checked: the rebuild matches the live model exactly (max probability difference 0 over 2,083 lab windows). OPTIMIZE.md, RESULTS.md and the smoke hint give this command; the live model file is stamped with it.
- Checks: smoke ALL PASS; 16 replays 0 failed; commit gated.

### Critique iteration 13, 08:39

- CRITIQUE #40 ops-3: SERIAL="${1:-U8-2025.10.14}" turned the "whichever amplifier answers" task's empty argument into 10.14, so it was a duplicate, and 5 of 25 launches last night died with "heard the other serial" and took the page down. Now an empty argument passes no serial (gPype takes the first found), and when a launch dies because the scan heard our other amplifier, run_all switches to it once and prints that the Alpha check must confirm it is the unit on the head (both units were advertising in the same room). Unknown serials are never picked. Tested the parsing on a real failed log (bridge_20261107_205226: 11.14 asked, 10.14 heard, switch chosen) without running run_all itself, which would now stop his 01:21 processes.
- CRITIQUE #41 ops-5: the manual VS Code tasks ran the gauge with default alarm 70 and smoothing 8 and wrote unpairable file names; they now use run_all's alarm settings and manual_<stamp>_raw / _gauge names. The adversary's extra find is fixed too: replay of a raw file without "_raw" in its name parsed the raw file as markers and crashed; it now replays without markers (checked on unicorn_rec_20261107_200725_250.csv).
- Checks: smoke ALL PASS; 16 replays 0 failed; commit gated.

### Critique iteration 14, 08:49

- CRITIQUE #46 serverpage-5 (and ops-adv3): the debrief counted every posted second as a measurement, including held seconds that re-post a frozen number (33 percent of his windows have fewer than 2 of 5 clean channels), never reset on Rebaseline, and a gauge restarted against a running page server took the server's old counters as new requests (unrequested Alpha check or Calibrate). Now held seconds (load held, noisy, channel or contact lost, no data, personal model held) are tagged and excluded and reported as held_seconds; Rebaseline and a new gauge session (time going backwards) clear the statistics; the gauge adopts the server's counters on its first reply. Unit-tested (2 scored, 2 held, peak from scored only; cleared on rebaseline and new session) and checked live: a fresh gauge against a server with pending counters started 0 checks.
- CRITIQUE #44 serverpage-3: the context numbers were fixed earlier (31, 5 of 8 electrodes); now it also explains the personal model when it is on, what held seconds are, and that fatigue moves with muscle tension and must not be called tiredness.
- Checks: smoke ALL PASS; 16 replays 0 failed; commit gated.

### Critique iteration 15, 09:02

- CRITIQUE #48 stats-2, #59 calib-6, claims-6: the 0.80 calibration bar was set on a null of 81 overlapping positions (about 12 independent runs) and then reported as proof that chance never reaches it, and the null code was not in the repo. Now the leave-one-pair-out is one function (loadmonitor/calibration.py) used by the gauge and by tests/calib_null.py, and the bar was re-measured with independent runs only:

  | test | runs | median AUC | at or above 0.80 | 95 percent upper bound |
  |---|---|---|---|---|
  | his recordings, no real alternation (null) | 8 | 0.59 | 1 (12 percent) | 47 percent |
  | lab rest only, fake blocks (null) | 35 | 0.47 | 2 (6 percent) | 17 percent |
  | lab rest vs arithmetic (positive, optimistic) | 35 | 0.93 | 29 (83 percent) | |

  So my earlier "chance never reached 0.80" was wrong: chance passes about 1 time in 10. The bar stays at 0.80 (choosing a new one from these same numbers would repeat the circularity; at 0.85 the lab null still passes 6 percent and the positive control drops to 77 percent). The gauge comment, the pass text on the page, and the morning summary now say what a pass means: rest and task blocks were separable for this person, not that load is measured. Counterbalanced block order and an artefact-control block are still open ideas.
- Also: the pygame window's alarm still said "HIGH LOAD: take a break"; now "load held above the alarm line".
- Checks: smoke ALL PASS; 16 replays 0 failed; commit gated.

### Critique iteration 16, 09:10

- CRITIQUE #49 stats-4 and #52 alpha-3: the Alpha check's sensitivity rested on one synthetic sine replay, and the best-of-4-channel rule was a multiple comparison. tests/alpha_check_eval.py now measures both sides with the gauge's own rule at every 10 s position of his recordings (245 positions, about 61 non-overlapping): chance (no eyes closing) passes 1.3 percent of testable checks; real lab rest EEG injected into the closed phase passes about 30 percent of testable checks at his noise; 38 percent of checks are too noisy to test. Best of Pz/O1/P3/P4 and best of Pz/O1 give the same numbers (P3/P4 are rarely live), so the rule is unchanged. Open: sensitivity on a real eyes-open vs eyes-closed dataset (PhysioNet EEGMMIDB runs 1 and 2) was not run offline.
- CRITIQUE #51 alpha-2: the check's clock sat inside "a posterior channel is live", so with the back row dead it never started and later fired by itself, possibly during Calibrate. Now it runs regardless and ends with "NO LIVE BACK ELECTRODE ... fix the back of the cap" (checked on the all-dead 23:03 recording).
- Checks: smoke ALL PASS; 16 replays 0 failed; commit gated.

### Critique iteration 17, 09:22

- CRITIQUE #2 alpha-adv1 (added by an adversary, high): the alpha check measured 8 to 13 Hz against a line fitted on 3 to 7 and 15 to 30 Hz, so a drop in blink or muscle power at eye closure lowered the line and passed with no alpha. Reproduced: cutting the closed phase's flanks by 6 dB with no alpha added passed the old rule in 90 to 93 percent of testable checks.
  - Five rule variants compared on his recordings (testable checks only, about 152 each):

    | rule | chance | real lab alpha injected | flank-only attack |
    |---|---|---|---|
    | old height rule | 1.3% | 32% | 93% |
    | alpha +3 dB and 3 dB above both flanks | 4.6% | 30% | 30% |
    | old AND previous | 0.0% | 17% | 28% |
    | alpha +6 dB and 3 dB above both flanks | 3.9% | 26% | 23% |
    | **alpha +3, 3 above both flanks, 80% of closed windows above the open 90th percentile (live)** | **1.3%** | **17%** | **10%** |

  - Chosen for specificity, since the check gates whether any number is trusted. Honest cost: at last night's noise, real lab-level alpha passes only 17 percent of testable checks. The variant was picked on these same recordings, so it needs validation on new data (an eyes-open vs eyes-closed dataset or a good-contact session).
  - One shared function (alpha_rule) is used by the gauge and tests/alpha_check_eval.py, which now runs the null, real-alpha and flank-attack scenarios. The result text shows the alpha and both flank changes.
- Checks: smoke ALL PASS; 16 replays 0 failed; commit gated.

### Critique iteration 18, 09:29

- CRITIQUE #16 ops-adv1 (and ops-8): every bridge published the LSL name "Unicorn" and the gauge took the first one on the network, so a teammate's or another team's stream on the same Wi-Fi, or an old session, could be read. Now run_all.sh gives each session its own name (Unicorn_<stamp>) for the bridge, the connect check and the gauge, and the gauge prefers a stream from this laptop. Checked with the simulated bridge: a uniquely named stream is found (hostname PAINGs-MacBook-Pro.local) and a missing name stops with a clear message.
- Checks: smoke ALL PASS; 16 replays 0 failed; commit gated.

### Morning fix, "alpha is not showing" (8 Nov)

- He asked to fix the missing alpha. The causes are mostly physical (no eyes-closed test ever run, mains hum and drift far above the brain signal, back electrodes often disconnected, possibly a different cap layout), so software cannot make alpha appear. Added what software can do:
  - Contact view on the head map (automatic before the baseline, while load is held and during an Alpha check; toggle in the map's label): per electrode, 1 to 40 Hz RMS after the notch, median of 5 s. Thresholds measured on data: lab gel-cap rest EEG 7 to 17 uV (10th to 90th percentile); his dry cap, live channels, median 140 to 290 uV, best tenth 16 to 52 uV. Green under 40, red over 100 (the model's clean limit). The line under the map lists not-connected and noisy electrodes with hum, and whether a back electrode is quiet enough in 8 to 13 Hz for the Alpha check (the 15 uV gate).
  - Layout check inside the Alpha check: the same band-specific rule on each of the 8 electrodes alone; the verdict adds where alpha passed. Chance on his recordings (67 non-overlapping 40 s checks, no eye closure): any of 8 passed in 1 (1.5 percent), front or centre alone in 0. The official PASS still uses the back four only.
  - Checked on a replay (port 8797): contact colours and fix line correct (C3 and O1 about 35 uV green, Fz and Cz red with 3 to 4k hum); Alpha check on the replay FAILs as it should (no eye closure) and prints the per-electrode rises.

### Critique iteration 19 (8 Nov, morning)

- Gates: smoke ALL PASS and 16 replays 0 failed on 253d059 (run minutes before this iteration); no gauge code changed here.
- CRITIQUE #23 calib-adv2 REJECTED with evidence. Its failure (channel sets mixing inside calibration blocks) was removed by 0c25f19, which holds the load and collects no calibration windows while any model channel is dead. With that gate, an effect injected into the task blocks passes the 0.80 bar in 97 percent (0.5 SD) and 99 percent (1.0 SD) of 115 overlapping starts (about 12 independent runs); the null passes 0. The proposed all-5-clean gate leaves 103 of 115 starts untestable on this dry cap; a 4-fold minimum leaves 33 untestable; neither changed null or power here. Script kept as tests/calib_inject.py (its base features now drop infinities, which crashed the critic's version).
- Honest scope: injected effects are a fixed shift in feature space, not real brain data; Calibrate is still untested on a head.

### Test ports (8 Nov, morning)

- Paing is letting a second agent (Antigravity) review the repo while this loop keeps running (his call). Both would have run the tests on port 8799 and the same /tmp log names. tests/free_port.py now claims a free port from 8799 upward (lock directory plus a bind check, never 8765); smoke.sh and replay_all.py use it and per-port log names, and release the claim on exit. Checked by running both at once: smoke on 8799 ALL PASS, replays on 8800 0 failed, no lock left behind. docs/REVIEW_BRIEF.md updated.

### Critique iteration 20 (8 Nov, morning)

- Gates: gauge code unchanged since 253d059; smoke ALL PASS (port 8799) and 16 replays 0 failed (port 8800) ran side by side on the current test scripts this morning (e73f8e0).
- CRITIQUE #29 claims-adv1 DONE. Measured per whole second over every recording of 60 s or more (3,644 s, tests/exclusion_report.py): the protocol's written rule (any of 8 channels on the rail or above 150 uV RMS) excludes 93 percent; on the 5 model channels it still excludes 72 percent. The gauge's own hold rule is looser (any model channel railed, or fewer than 2 clean after the cleaning chain) and scored 67 percent of its post-baseline rows. PROTOCOL.md now carries a dated amendment saying every load number from 7 and 8 Nov falls outside the original rule, makes the gauge's rule the exclusion rule from 8 Nov, and asks for both shares per session. (The critic's 83 percent counted rail only; adding the 150 uV condition gives 93.)

### Demo fallback: lab EEG replay (8 Nov, morning, at Paing's request "make it work for demo")
- The dry cap has not given a clean signal, so the demo now has an honest fallback that shows the system working on real EEG: `./run_all.sh lab` replays one held-out person from the public eegmat dataset (rest, mental arithmetic, rest) through the exact live gauge and page, with a banner "LAB EEG REPLAY, not this headset".
- loadmonitor/lab_demo.py: leave-one-subject-out with the live settings on all 36 people (median per-person AUC 0.81; 23 of 36 at 0.7 or more; 5 below 0.5; every value in models/lab_demo_loso.json). Demo person chosen by a rule fixed before any replay: closest to the 75th percentile (person 09, AUC 0.89, rank 10 of 36). Model retrained without that person: models/readiness_demo.joblib (live model untouched).
- Replayed through the gauge: rest load 0 throughout; mental median 57, peak 88, alarm at 139 s; recovery median 23, back to 0 by 190 s. Page checked in the browser (port 8797): load 88 during mental, trace over the 50 line, contact view green (8 to 14 uV), model row now comes from the gauge ("this copy trained without person 09").
- Checks: smoke ALL PASS and 16 replays 0 failed, run side by side.

### Critique iteration 21 (8 Nov, late morning)

- CRITIQUE #31 dsp-adv1 and #32 dsp-adv2 DONE, with evidence.
  - Rail part already fixed: in the replays, 0 of 1,610 scored windows had a railed sample on a model channel (the critic counted 255 before 0c25f19).
  - Effect measured (tests/noisy_channel_shift.py): clean lab EEG with ONE model channel given a real noise segment from Paing's recordings (live, over 100 uV before the mask) moved p by a median 0.19 (over 0.10 in 67 percent of 168 windows). The old gate (RMS after the chain) called that channel clean in 30 percent, and those moved p by a median 0.31. A 0.10 shift can be 40 load points.
  - Fix: a channel counts as clean only when it is under 100 uV both before the reference and burst mask (4 to 30 Hz, notched) and after the full chain; the load is held unless all 5 model channels are clean (--load-min-clean now defaults to all model channels).
- Alternatives measured at Paing's question ("if one electrode fails there are others"): rebuilding a bad electrode from its layout-A neighbours (tests/interp_shift.py, lab EEG, 840 cases) still moves p by a median 0.085 with steady biases (Pz rebuilt +0.07 on average), so it is not used. Per-electrode backup models would rescue only the windows with exactly one noisy electrode: 130 of 587 noisy scored windows; 205 had all 5 noisy at once. Not built.
- Consequence, stated plainly: on the 7 and 8 Nov recordings the gauge now scores 24 percent of post-baseline seconds (was 67), 0 to 72 percent per session, and their load means drop toward 0 (01:03 session, mental: 16 to 5). The lab demo is unchanged (0 held; rest 0, mental peak 88, recovery back to 0). PROTOCOL.md amendment updated with these numbers.
- Checks: smoke ALL PASS and 16 replays 0 failed, run side by side.

### Critique iteration 22 (8 Nov, late morning) and the noise-limit sweep

- CRITIQUE #34 fatigue-adv2 DONE. tests/replay_all.py now fails a session whose scored rows are all-zero features, frozen (same feature vector 60 s) or fatigue pinned at 0 or 100 for 30 s, and labels a session that is held throughout instead of calling it plainly ok (check_log, unit-tested in tests/test_replay_checks.py). None of these occur now: the critic's example 222646 has 0 scored rows under the strict gate (it had 78 rows of zeros). The morning summary's "nothing is blocking" line carries a correction.
- Paing asked to optimise the threshold. tests/threshold_sweep.py: clean lab windows (12 people) with ONE model channel given a real segment of his signal, binned by its 4 to 30 Hz level before the mask. Median shift in p: 0.12 for 0 to 20 uV, then flat at 0.18 to 0.21 for every bin from 20 uV to over 300 uV; adding another lab person's clean EEG instead gives 0.09. So the size of the error does not depend on the level above 20 uV: any foreign signal that dominates a channel throws the model by about the same amount, and no amplitude limit can be tuned on this error. Availability on his recordings (all 5 model channels connected and under the limit before the mask): 24 percent at 40 uV, 35 at 100, 42 at 200, 46 at 300.
- Decision: keep 100 uV, on physiology (lab gel-cap EEG 7 to 17 uV; over 100 uV in 4 to 30 Hz is not brain), not on the curve. Raising it would show the number more often with no evidence the extra seconds are brain.
- Correction: iteration 21 said "one noisy channel moves p by a median 0.19". The sweep shows that shift comes from replacing a channel with any foreign signal, not specifically from noise level; wording corrected in PROTOCOL.md, CRITIQUE.md and the gauge comments. The strict all-5 gate stays: a channel over 100 uV is not brain, and one such channel moves p about twice as much as the clean-EEG reference.

### Critique iteration 23 (8 Nov, late morning)

- No code changed; gates last passed on c9c8ee3 (smoke ALL PASS, 16 replays 0 failed).
- CRITIQUE #50 stats-adv1 PARTLY DONE. Checked the source: the PhysioNet eegmat page states serial subtraction, ICA-cleaned 60 s segments and a 50 Hz notch, but not the eye condition. The critic's spectra (lab alpha +7.5 dB at rest, +5.0 during arithmetic) point to eyes closed in both. PROTOCOL.md now has live tests run eyes closed for baseline, rest and subtraction, matching the likely training condition and removing blink and gaze artefact. Not done: re-running the Calibrate positive control on an eyes-open workload dataset.
- Paing chose to test live now; the loop will skip its heavy tests while a live headset session is running, so they do not steal CPU from the gauge.

### Critique iteration 24 (8 Nov, about 10:35)

- Paing is testing the headset live, so this round ran only the unit tests (12 passed) and a targeted gauge run; the long smoke and replay tests wait until no headset session is running, so they cannot slow the live gauge.
- Live test so far (10:25 to 10:33, from the raw files): every electrode reads exactly +200 mV with no noise (OPEN) for whole sessions: the amplifier is not connecting to the cap. Not a software fault; same as 7 Nov. Added headset/live_check.py (OPEN / SATURATED / noise per electrode every 2 s; says NOT RECORDING when run_all is stopped and follows new sessions). A 100 mV saturation rule was tried and dropped: quiet channels in his recordings sit at a median 80 mV offset, so only the last 4 mV before the limit count as SATURATED.
- CRITIQUE #53 alpha-4 DONE. A FAIL with noise under the gate already said "repeat once" (not "fix the contact"); it now also says the noise was low enough to test, so it is not a contact verdict, and that 3 of 36 lab people on a gel cap stay under +3 dB even with eyes closed. Checked by an Alpha check on the lab replay (FAIL as expected: no eye closure in that file; no crash).


### Iteration 25 (8 Nov, about 10:45): live test, 4-electrode mode

- Live session running (run_all ... 4ch), so no smoke or replay run this round; unit tests passed (12) at 5502c78.
- What the live test showed: on this cap C3, C4, P3 and P4 never connected (OPEN for whole sessions, every second amplifier input); Fz, Cz, Pz and O1 connect when the amplifier is pressed, start at 600 to 6,000 uV and settle while he holds still (Fz 1,928 to 387 uV in 14 s). The gauge kept saying "C3 not connected", so the 5-channel model could never score.
- Added a 4-electrode model without C3 (models/readiness_4ch.joblib, live recipe on Fz Cz Pz O1): lab leave-one-subject-out AUC 0.766 (5-channel 0.760), balanced accuracy 0.671. Started with `./run_all.sh "" paing 4ch`; headset/live_check.py --4ch matches. Checked on the lab replay (no crash).
- Result at 10:42: baseline done, page LIVE, but HELD NOISY with 0 of 4 clean (O1 5,100 uV, Cz 384, Fz 323, Pz 215; hum 800 to 1,200 on Fz and Cz = poor skin contact). The hold is correct: nothing scored. Fatigue OFF (no clean baseline seconds). Next is physical: skin contact, then Rebaseline.

### Iteration 26 (8 Nov, about 10:55)

- Paing is testing the headset live between sessions, so only unit tests ran (12 passed); no code changed.
- Layout question raised by the live test: the g.Pype scope labels inputs 6 to 8 PO7, POz and PO8, the Unicorn factory positions (headset/montage.py ORIGINAL), while the software assumes layout A (P3, O1, P4). Nobody has confirmed the electrodes were moved. If the cap is in the factory layout, the model's "O1" input is POz (back centre, low), and the Alpha check's per-electrode layout line names the wrong spots for inputs 6 to 8. For the 4-electrode model (Fz Cz Pz O1) the error is one posterior electrode about 3 cm from where the model expects it. To settle on the cap, not in code.
- Live state 10:51 to 10:52: 7 of 8 inputs OPEN (only input 7 live): the amplifier is not seated on the dock. Earlier (10:42) Fz, Cz, Pz and O1 connected but carried 7,700 to 13,500 uV of mains hum on every channel, which points to the reference and ground pads behind the ears not touching skin. All 8 electrodes are present in the cap (Paing checked).

### Iteration 27 (8 Nov, about 11:30): demo options, low-confidence mode, fatigue in the lab demo

- Paing asked that the number always shows. New `--show-noisy` (on in run_all): when all model channels are connected but too few are clean, the window is scored as LOW CONFIDENCE (number greyed on the page, label "noisy signal, treat as a rough trend", alarm blocked, Calibrate skips it, CSV contact column 2). A disconnected channel still holds. On his 9 pm replay the load now moves 0 to 17 (rest session) instead of sitting held.
- Lab demo options: `./run_all.sh lab <speed> <baseline_s>`. Baseline sweep on the lab person: 30 s and 20 s keep the alarm (peaks 88 and 87); 15 s peaks 80; 10 s and 5 s never alarm, so 20 s is the shortest offered. The page's baseline label now shows the real length.
- Fatigue: `--fatigue-show-s` (default 1200 s, unchanged for live); the lab demo uses 0, and the page adds "slow trend, builds over 20+ min". On the lab replay it stays 48 to 52, as a slow measure should over 3.5 minutes. The old countdown "N min to go" is replaced by a static line.
- Fixes found by the tests: a time-limited gauge (--seconds) hung forever after its LSL stream died; it now stops after max(10 s, --seconds) without data. Smoke: the simulated bridge runs 25 s (startup took 6 s and starved the 12 s run), and the stall step waits for the NO DATA line instead of a fixed 12 s.
- Checks: 16 replays 0 failed; smoke ALL PASS.

### Critique iteration 28 (8 Nov, about 11:45)

- Andy merged his load model v2 work into the branch (PR 8: andy_model.py, compare_models.py, rest_markers.py, ANDY_MODEL.md); my commits were rebased on top, nothing of his changed; his files parse; the live gauge does not use them.
- CRITIQUE #54 alpha-6 DONE. The live "alpha at Pz/O1" readout was the max of up to four posterior heights in one 4 s window; on his eyes-open recordings (3,483 s) it read +3 dB or more in 14.6 percent of seconds and +5 dB in 3.5 percent. It is now the 8 s median of the mean of Pz and O1: +3 dB or more in 1.5 percent, +5 dB in 0.2 percent. On the lab replay at rest it reads +6.3 dB (lab expectation about +6). The Alpha check keeps its own rule. Page label says "8 s median".
- Checks: smoke ALL PASS and 16 replays 0 failed.

### Critique iteration 29 (8 Nov, about 11:55)

- CRITIQUE #55 alpha-adv2 DONE. The Alpha check's eyes-closed windows ran 24 to 40 s, so the first ones covered the spoken "Close your eyes" and the closing blink. Now 26 to 42 s (still 16 windows; the check ends at 42 s; page countdown and tests/alpha_check_eval.py updated together). On the same start positions: chance 1.8 percent both, injected lab alpha 12.0 (new) vs 13.3 (old), flank-only attack 10.1 vs 11.2: no measurable cost. The benefit (no closing blink in the closed phase) cannot show in this test, which injects lab alpha without a blink. Correction: the logged "17 percent" for injected alpha came from a different set of start positions; like for like it is 12 to 13 percent.
- Smoke: the simulated-headset gauge step now runs 12 s of data instead of 6 (its baseline finished at about 6 s, so it passed or failed by a fraction of a second).
- Checks: 16 replays 0 failed; smoke ALL PASS.

### Critique iteration 30 (8 Nov, about 12:10)

- CRITIQUE #56 calib-3 DONE. Since the strict gate (6b5deb6), Calibrate keeps only windows with every model channel clean, so thin blocks became likely on this cap (103 of 115 calibration starts on his recordings had a block under 5 clean windows, tests/calib_inject.py). A result now counts only if all 8 blocks keep at least 10 of their 15 windows and all 4 folds score; otherwise "calibration incomplete: clean windows per block [...]" and the generic model stays. Checked: on his 01:03 recording it reports incomplete ([7, 6, 6, 8, 0, 0, 0, 0]); on the lab replay all blocks complete and the 4 folds score (AUC 0.44, model OFF, as expected since that file does not alternate rest and task on Calibrate's schedule). Not done: prompts on a timer independent of window quality.
- Checks: smoke ALL PASS; 16 replays 0 failed.

### Iteration 31 (8 Nov, about 12:25): "why did it move" line, lab person's markers

- Paing asked for the LLM ideas that best help win; chosen: (2) a line explaining load changes and (1) a contact copilot. Built (2) first because it shows in the recorded video and must work without an API key.
- What the lab demo person's markers actually do (demo/lab_eegmat_s09, vs the 30 s baseline, 4 s Welch, medians): posterior alpha Pz +2.8 / -2.1 / +1.2 dB and O1 +2.7 / -2.8 / +2.1 dB for rest / arithmetic / recovery; frontal theta Fz +0.2 / -0.9 / +0.3 dB. So for this person alpha drops during arithmetic and theta does NOT rise; the video narration was corrected to say "posterior alpha drops".
- Page: under the load, after the baseline, "Rising/Steady/Falling · alongside it: posterior alpha X dB, frontal theta Y dB vs your rest" (trend = load change over 10 s; values = 5 s median of the gauge's own per-channel dB vs baseline). Tooltip says the load comes from the model and these are markers that moved alongside it. Seen in the browser on the lab replay: "Rising · posterior alpha -2.8 dB, frontal theta -0.3 dB". No LLM call, so it cannot fail on camera.
- Checks: page script parses (node --check); smoke ALL PASS; 16 replays 0 failed.

### Iteration 32 (8 Nov, about 12:45)

- Lab replays now get honest rule-based coach and debrief text ("lab EEG replay, held-out person, not this headset" instead of UNVERIFIED), and the no-key tag reads "rule-based summary" (8204225, 2f2f1df). No Anthropic key is set in Paing's shell, so the video will show the rule-based text unless he exports one.
- CRITIQUE #57 calib-4 REJECTED with evidence. Buffered leave-one-pair-out (neighbouring blocks also left out of training) re-run with tests/calib_null.py through the shared function: chance passes unchanged (his recordings 1 of 8, lab rest 2 of 35), but the lab positive control found fewer real effects (25 of 35 vs 29 of 35; median AUC 0.88). Kept as calibration.leave_one_pair_out(buffered=True), off by default; tests/test_calibration.py covers it. The positive control uses 3 pairs, where buffering removes half the training data; the live 8-block design may lose less, but nothing measured shows a gain.
- Checks: unit tests 14 passed; gauge code unchanged in behaviour (default path identical).
