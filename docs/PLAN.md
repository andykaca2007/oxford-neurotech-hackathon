# Mental-load monitor: the plan

Oxford Neurotech Hackathon, AI stream (Tobii). Written Sat 7 Nov 2026, 20:40.

## One sentence
A cheap 8-electrode EEG headset that shows a person's mental load live, relative to their own
30-second baseline, with a model trained on public data, and alarms when load stays high.

## Who it is for
People whose mistakes hurt others when they are mentally overloaded: surgeons on long lists,
air traffic controllers, pilots, ICU nurses, long-haul and mining drivers. Mining fleets already
wear EEG fatigue caps in hard hats (SmartCap), so the market and the habit exist. Second audience:
athletes and coaches (table tennis pre-session readiness), same engine, smaller market.

## What is built (all in the repo, branch paing/readiness, PR 6)
| piece | file | status |
|---|---|---|
| Model: rest vs mental load | `loadmonitor/readiness_model.py` | done, evaluated |
| Live gauge: baseline, load 0 to 100, alarm, speech | `loadmonitor/load_gauge.py` | done, tested on fake data |
| Web dashboard: head map, load, markers, trace, maths challenge with error ticks, debrief | `loadmonitor/gauge_server.py`, `loadmonitor/web/index.html` | done, checked in a browser |
| Headset bridge (Core-8 to LSL) | `headset/unicorn_gpype.py` | done, works on the Mac |
| Live run on a real head | | NOT done: the loaner cap has dead electrodes |

## The science
- Data: PhysioNet "EEG during mental arithmetic" (Zyma et al. 2019), 36 healthy adults, 3 min rest
  then 1 min of serial subtraction, open licence. Credited.
- Cleaning: only the 5 electrodes our headset reads reliably (Fz, C3, Cz, C4, Pz); band-pass
  1 to 40 Hz; 4-second windows; each person's first 28 s of rest is their baseline and is
  subtracted from every later window.
- Features: log power in theta (4 to 8 Hz), alpha (8 to 13), beta (13 to 30) per electrode, plus
  frontal theta/alpha and parietal alpha/beta ratios. 17 numbers per window.
- Model: logistic regression. Small on purpose: 36 people is not enough for a deep net, and a
  judge will ask.
- Evaluation: leave-one-subject-out. Train on 35 people, test on the 36th, repeat 36 times.
  No test person's data ever touches training.

| features | balanced accuracy | AUC |
|---|---|---|
| raw | 63% | 0.75 |
| relative to own baseline, logistic | 70% | 0.79 |
| relative to own baseline, gradient boosting + rich features | 75% | 0.84 |

Chance is 50% and 0.5. The finding: a 30-second personal baseline is worth 7 points on strangers.
Personalisation beats a universal model.

## How the live system works
1. Cap on. 30 s sitting still, eyes open: the baseline.
2. Every second, the last 4 s of EEG goes through the same features and the model. The output
   probability is smoothed and shown as 0 to 100.
3. The head map shows each electrode's activity change from baseline in dB, so bad contact is
   visible. Markers: frontal theta up and parietal alpha down are the fatigue signature.
4. Above the alarm line (50 since 8 Nov) for 20 s: alarm. Red strip on the page, spoken "load above the line" (no advice).
5. Page is a local website; it can be open on a phone across the room as the supervisor view.

## The demo (the wow)
1. Cap on a judge. 30 s baseline. The room sees their head map and a calm blue page.
2. (Amended 8 Nov) Alpha check first. Then silent subtraction: 4000 minus 7 in their head, eyes on one
   point, no talking or typing; they say the last number at the end. If the cap and the person allow it,
   the load climbs; we show whatever it does.
3. (Removed: "wrong answers as red ticks, strain shows before the mistakes". Spoken or typed answers add
   artefact, and we have no data for that claim.)
4. They stop. The number falls. Blue again.
5. A three-line debrief appears, written by Claude (claude-opus-5-5) from the session numbers:
   when load peaked, how long above the line, where the errors fell, one recommendation.
   Built. Needs `export ANTHROPIC_API_KEY=...` before starting gauge_server.py; without a key it
   falls back to a plain template so the demo never hangs.

### Demo fallback: lab EEG replay (added 8 Nov morning)
If the cap does not pass the Alpha check, show the same live pipeline on real EEG instead, and say so:
`./run_all.sh lab` (build once with `.venv/bin/python loadmonitor/lab_demo.py`, about 5 min).
- Data: PhysioNet "EEG during mental arithmetic" (gel cap, 36 people). The demo person (09) was picked by a rule
  fixed before replaying anyone: the person at the 75th percentile of held-out AUC (0.89, 10th of 36). The model on
  screen (`models/readiness_demo.joblib`) was trained without that person.
- Across all 36 held out in turn: median per-person AUC 0.81, 23 of 36 at 0.7 or more, 5 below 0.5. Say this: it
  works for about two in three people, and fails for some.
- What the page shows (replayed through the live gauge, 8 Nov): rest 0 the whole time; mental arithmetic climbs from
  31 to a peak of 88, alarm at 139 s; recovery falls from 76 back to 0 by 190 s (smoothing lag).
- The recovery minute is the same person's earlier rest (the dataset has no rest after the task).
- On screen (8 Nov, Paing's call): no replay label; the status reads "running" (never "live") and the header reads
  "eeg · 8 ch · 250 hz" instead of naming the Unicorn. The narration MUST say it is a held-out person from a public EEG
  dataset recorded with a gel cap: that line is the only disclosure in the video.

## What we claim, and what we do not
Claim (corrected 8 Nov): the live model, trained on lab EEG (PhysioNet eegmat, 36 people, rest vs mental
arithmetic, leave-one-subject-out), scores AUC 0.76 and balanced accuracy 68% on people it never saw, and is
at chance for about 1 in 6 of them. Every accuracy number is from lab EEG. On our dry cap we have not yet shown
brain signal (no alpha in last night's recordings), and on Paing's recordings the gauge did not reliably
separate task from rest. (The earlier line, "75%, AUC 0.84, and shows it live", described an older model
and claimed a live result we do not have.)
Not claimed: that load equals accident risk; that students doing sums are surgeons at hour
eleven; that one session proves errors follow load. Say these before the judges ask.

## Judging criteria, how we score
- Validity: public data, held-out people, baseline, metric. Strong.
- Feasibility: it runs, on the channels the loaner cap actually has. Strong if the cap works.
- Originality: the 30-second baseline result and the head map are ours; fatigue monitoring itself
  is known. Medium.
- Impact: safety-critical jobs, an existing market. Strong.
- Presentation: live brain on a judge, honest limits. Strong.

## Roles for tonight and Sunday
- Signal and demo (Paing): get a cap with live electrodes, run the gauge on three people,
  record a 60 s video of a real run.
- Data: re-run `readiness_model.py`, write the protocol half-page, fill the results table.
- Slides (five): problem and audience; how it works (one diagram); the results table; the live
  demo; limits and next step (a shift study with a safety-critical employer).
- Pitch: 90 seconds, then the judge demo, three timed rehearsals Sunday morning.
- Code freeze Sunday 13:00.

## Run it
```bash
# terminal 1: headset -> stream
.venv/bin/python headset/unicorn_gpype.py --serial U8-2025.10.14
# terminal 2: the web page
.venv/bin/python loadmonitor/gauge_server.py        # http://localhost:8765
# terminal 3: the gauge (real head)             or without a headset:
.venv/bin/python loadmonitor/load_gauge.py --lsl --web --log s1.csv
.venv/bin/python loadmonitor/load_gauge.py --fake --web --no-ui
```

## Everything else in the repo
SSVEP decoder and calibration curve, speller, scanning aid, head-controlled game, robot arena:
today's explored alternatives. They stay as evidence of the search, not as the product.

Code written with Claude (AI assistant) during the event, directed by Paing. Dataset: Zyma et al.
2019. SDK: g.tec g.Pype.
