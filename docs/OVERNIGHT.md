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

1. Nothing on the software side is blocking a session. Every check passes; all 16 of last night's recordings replay through the live gauge with no crash, no NaN, and no false alarm.
2. The blocker is the signal. Last night's recordings contain no detectable alpha (Pz 0.0 dB, O1 -0.3 dB above background; lab eyes closed +6 to +7 dB), and the spectrum is noise-like. Zetamac adds typing and gaze artefact on top (ASR fires on every Zetamac window).
3. Session order, all on the page: Rebaseline when settled, then **Alpha check**. FAIL means fix contact (mastoid stickers on wiped skin, amplifier pressed and strapped, hair parted, 2 min still), not code. PASS means the electrodes see brain.
4. After a PASS: **Calibrate** (160 s, spoken prompts). The personal model switches on only at held-out AUC 0.80 or above (chance on his data never reached 0.80; 91 percent of lab subjects do).
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
