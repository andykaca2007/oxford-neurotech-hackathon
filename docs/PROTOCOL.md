# Recording protocol: mental load vs physical fatigue, one person, one cap

Written Sat 7 Nov 2026, 21:30, before any of these sessions were recorded. Fixed now so the
judges can see the test was decided before the data. Change it only by editing this file and
noting why.

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
panel shows this; red rows mean fix contact first. Mastoid stickies on wiped skin, chin strap
tight, two minutes to settle.

## Segments, with the page's condition buttons
| step | condition button | duration | what the wearer does |
|---|---|---|---|
| 0 | | 40 s | after the baseline: press **Alpha check** on the page, follow the spoken prompts (20 s eyes open, 20 s eyes closed). FAIL means fix contact before anything else |
| 1 | baseline | 30 s | sits still, eyes open, looks at a blank wall |
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
- fraction of mental seconds above the 70 alarm line, and whether the alarm fired
- the raw markers per segment, relative to baseline: Fz theta (dB), Pz alpha (dB), and muscle
  power 30 to 40 Hz at C3 and C4 (dB)

One figure per person, and one with all three overlaid: time on x, load on y, the four
segments shaded, a second row with the muscle marker. Mental should peak during Zetamac and fall
in recovery; after running, muscle power and alpha are the things expected to move, and the load
number does whatever it does. Report it either way.

## Things that invalidate a segment
- any of the eight channels on the rail or above 150 uV RMS: mark the segment "contact" and
  exclude it
- talking or chewing during baseline or recovery
- the cap moved between segments without a re-check
- the wearer saw their own load number during mental (keep the page off their screen)

## Claims we may make
- The trained model raises a personal load number during mental arithmetic and lowers it in
  recovery on N of 3 of us, with these numbers.
- After exercise the cap shows the following measured changes (markers), which differ from the
  mental signature in this way.
- Not: that load equals accident risk; that exercise fatigue was classified; anything about
  patients or shift workers beyond "this is who it is for".
