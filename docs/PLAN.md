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
4. Above 70 for 20 s: alarm. Red strip on the page, a spoken "take a break".
5. Page is a local website; it can be open on a phone across the room as the supervisor view.

## The demo (the wow)
1. Cap on a judge. 30 s baseline. The room sees their head map and a calm blue page.
2. Maths challenge on the projector: 4000 minus 7, out loud, against a clock, a teammate types
   the answers. The load climbs, the frontal electrode lights up, the page turns to alarm.
3. Wrong answers appear as red ticks on the load trace: strain shows before the mistakes.
4. They stop. The number falls. Blue again.
5. A three-line debrief appears, written by Claude (claude-opus-5-5) from the session numbers:
   when load peaked, how long above the line, where the errors fell, one recommendation.
   Built. Needs `export ANTHROPIC_API_KEY=...` before starting gauge_server.py; without a key it
   falls back to a plain template so the demo never hangs.

## What we claim, and what we do not
Claim: a 400-pound dry headset plus a 30-second baseline detects mental load on people the
model never saw, 75% balanced accuracy, AUC 0.84, and shows it live.
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
