# Recording protocol: mental load vs physical fatigue, one person, one cap

Written Sat 7 Nov 2026 and committed at 20:35 (git 44c919d), before the first protocol recording (20:51).
Change it only by editing this file and noting why.

**Amended 8 Nov at 01:58 and 02:31, after seeing the data** (git 861b97f, bf367e4): the mental task
became silent serial subtraction (Zetamac's typing and gaze shifts were artefact), step 0 (Alpha check)
and step 1b (Calibrate) were added, and the alarm line is now 50 held 20 s. Results from sessions run
under the amended protocol are not pre-registered in the original sense; say so.

## What we are testing
- **Validated:** the mental-load model (`loadmonitor/readiness_model.py`), trained on public
  recordings of people doing mental arithmetic vs resting, scored leave-one-subject-out. Its
  live number is a trained readout.
- **Exploratory:** what the same cap shows after physical exercise. The model has never seen
  exercise. We report the raw markers for that segment and make no classifier claim.

Honest sentence for the pitch: "Mental load is the trained model. Physical fatigue is a measured
contrast we recorded today, not a classifier."

## Electrodes
Layout A, as `headset/montage.py` defines: Fz, C3, Cz, C4, Pz, P3, O1, P4. All eight must be
off the rail and under 100 uV RMS (1 to 40 Hz) before the baseline starts. The page's signal
panel shows this; red rows mean fix contact first. (8 Nov: the head map's contact view shows this per electrode; see the exclusion amendment below for how rarely all 8 met it.) Mastoid stickies on wiped skin, chin strap
tight, two minutes to settle.

## Segments, with the page's condition buttons
| step | condition button | duration | what the wearer does |
|---|---|---|---|
| 0a | | until green | (amendment 8 Nov morning) before the baseline the head map shows **contact noise** per electrode, 1 to 40 Hz after the 50 Hz notch: green under 40 uV, amber 40 to 100, red over 100, dashed = not connected. The line under the map names what to fix first. Get Pz and O1 green (part the hair, press; seat the amplifier) before going on |
| 0 | | 40 s | after the baseline: press **Alpha check** on the page, follow the spoken prompts (20 s eyes open, 20 s eyes closed). FAIL means fix contact before anything else. The result also tests every electrode on its own and says where alpha appeared: alpha only at the front or centre means the cap is probably not in layout A |
| 1 | baseline | 30 s | sits still, eyes open, looks at a blank wall |
| 1b | | 160 s | optional, after the Alpha check passes: press **Calibrate**. Spoken prompts alternate 20 s rest and 20 s silent counting down in sevens, 4 times each. The page shows the held-out score; the personal model switches on only at 0.80 or above, otherwise the generic model stays |
| 2 | mental | 3 min | **silent serial subtraction**: eyes on one fixed point, count down from 4000 in 7s in your head, no typing, no talking; say the last number at the end. (Changed 8 Nov: Zetamac's typing and gaze shifts make ASR fire on every window, so it measures movement, not effort; the model was trained on silent subtraction) |
| 3 | recovery | 2 min | sits quietly, eyes open |
| 4 | none | 2 to 3 min | cap OFF; running or stairs, enough to breathe hard |
| 5 | | under 60 s | wipe forehead and behind ears; cap on; press stickies; check the signal panel |
| 6 | physical | 3 min | sits quietly, eyes open, straight after exercise |

Press each button at the moment the segment starts. Markers land in `<log>_markers.csv` as
(t, condition) and as a column in the gauge CSV. Run the whole thing with:

    ./run_all.sh U8-2025.10.14 NAME      # NAME = the wearer, names the files

One session per person. Target three people: three sessions of about 15 minutes each.

## What to report
Per person, from the gauge CSV:
- mean load in each of mental, recovery and physical, and the peak during mental
- fraction of mental seconds above the alarm line (50 held 20 s since 8 Nov), and whether the alarm fired
- the raw markers per segment, relative to baseline: Fz theta (dB), Pz alpha (dB), and muscle
  power 30 to 40 Hz at C3 and C4 (dB)

One figure per person, and one with all three overlaid: time on x, load on y, the four
segments shaded, a second row with the muscle marker. Mental should peak during silent subtraction and fall
in recovery; after running, muscle power and alpha are the things expected to move, and the load
number does whatever it does. Report it either way.

## Eyes (amended 8 Nov, late morning, CRITIQUE stats-adv1)
The PhysioNet eegmat page (the model's training data) does not say whether eyes were open or closed. Its spectra
suggest closed: posterior alpha stays high even during arithmetic (+7.5 dB at rest, +5.0 dB during the task, 83
percent of people at +3 dB or more while counting). So live tests now match it: baseline, rest and silent
subtraction all with eyes CLOSED, relaxed jaw. This also removes blinks and eye movements. The Alpha check is the
only step with eyes open (its first 20 s). The page's baseline prompt still says "eyes open"; ignore that line.

## Things that invalidate a segment
- any of the eight channels on the rail or above 150 uV RMS: mark the segment "contact" and
  exclude it
- talking or chewing during baseline or recovery
- the cap moved between segments without a re-check
- the wearer saw their own load number during mental (keep the page off their screen)

**Amended 8 Nov (morning), after seeing the data (CRITIQUE claims-adv1).** The channel rule above was written for 8
live channels; the cap rarely gave that. Measured per whole second over every raw recording of 60 s or more
(`tests/exclusion_report.py`, 3,644 s):

| rule | share of seconds excluded |
|---|---|
| original: any of the 8 channels on the rail or above 150 uV RMS (1 to 40 Hz, 50 Hz notched) | 93% |
| same rule on the 5 model channels only (Fz C3 Cz Pz O1) | 72% |

What the gauge applied that morning was looser than both: it held a second when any model channel was on the rail,
or when fewer than 2 model channels were under 100 uV after its cleaning chain, and it scored 67% of its
post-baseline rows in the replays. From later on 8 Nov (CRITIQUE dsp-adv1, dsp-adv2) it scores a second only when
ALL 5 model channels are under 100 uV both before the reference and burst mask (4 to 30 Hz) and after the full chain:
a channel over 100 uV in 4 to 30 Hz is not brain (lab gel-cap EEG is 7 to 17 uV), and one channel carrying a foreign signal moves the model's output by a median 0.18 to 0.21 whatever its level (tests/threshold_sweep.py). Under that rule it scores 24% of the same rows (0% to
72% per session). So every load
number from the 7 and 8 Nov recordings falls outside the original exclusion rule, and must be reported that way.
From 8 Nov the exclusion rule is the gauge's hold rule. Report, per session, the share excluded under the original
rule and under the gauge's rule; the script prints both.

## Claims we may make
- The trained model raises a personal load number during mental arithmetic and lowers it in
  recovery on N of the people tested, with these numbers. Report N honestly: as of 8 Nov it is 0 of 1
  (Paing's recordings, no reliable separation, no detectable alpha).
- After exercise the cap shows the following measured changes (markers), which differ from the
  mental signature in this way.
- Not: that load equals accident risk; that exercise fatigue was classified; anything about
  patients or shift workers beyond "this is who it is for".
