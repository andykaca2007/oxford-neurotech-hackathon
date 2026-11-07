# HANDOFF: Oxford Neurotech Hackathon, AI stream (Tobii), Sat 7 Nov 2026 ~14:30

Read this first if you are a teammate or a fresh Claude session picking the project up.

## The project in two sentences
A personal SSVEP brain decoder: look at one of four flickering tiles for 1 to 3 s and the
system picks it, buzzing a carer's wristband. The science claim: how much per-person
calibration a decoder needs, shown on 10 public subjects with held-out blocks (done) and
replicated live on team members with a g.tec Unicorn BCI Core-8 (pending the next headset slot).

## Rules that bind us (Participant Information Sheet, in ~/Downloads and summarised in GTEC_TRACK_RESEARCH.md)
- AI stream: AI must be central (we train TRCA per person), neural data core input, held-out
  split + baseline (CCA) + metric (accuracy, ITR). No inferring protected traits from people.
- All code written during the hackathon. Everything in unicorn/ was written today (7 Nov).
  The ESP32 wristband firmware (planb_imu/) and warmup/ predate the event: declare them as
  brought hardware, do not present them as hackathon code.
- Judging: scientific validity, feasibility and progress, originality, impact, presentation
  with honest limitations.

## State of the build (all in this folder, Python venv in .venv, run from this folder)
| file | what | status |
|---|---|---|
| unicorn/unicorn_gpype.py | Core-8 (BLE) -> LSL stream "Unicorn" + CSV, via g.tec's g.Pype SDK; opens a scope window that must stay open | works; `--serial U8-2025.10.14` |
| unicorn/live_view.py | autoscaled 8-channel viewer, typed amplitude/window, keys 1-8 toggle | works |
| unicorn/alpha_check.py | spoken eyes-open/closed contact + alpha test | works |
| unicorn/ssvep_stim.py | 4 flicker tiles 7.5/8.57/10/12 Hz, `--trials N` cues tiles, `--banner REPLAY` | works; display must be locked to 60 Hz |
| unicorn/ssvep_decode.py | live decoder: `--lsl`, `--csv file`, `--fake`; `--model models/x.npz` uses the personal TRCA; `--cue-port` buzzes the ESP32; `--log` | works on fake and replay |
| unicorn/ssvep_calibrate.py | records cued epochs while the stim runs `--trials`, fits TRCA, leave-one-out CCA vs TRCA, saves models/*.npz | works on fake |
| unicorn/trca.py | CCA and ensemble TRCA (Nakanishi 2018), ITR | works |
| unicorn/calibration_curve.py, speed_accuracy_plot.py | public-data evaluation, Nakanishi 2015 in data/nakanishi2015 | DONE, plots in data/ |
| unicorn/replay_demo.py | held-out public trials -> tiles + wristband, for a no-headset demo; `--say "Yes;Call the nurse"` composes phrases from held-out trials | works; `--say` tested on synthetic data only |
| unicorn/phrase_tree.py | the fixed 16-phrase tree (4 groups x 4, two looks per phrase, 10 s timeout back to groups) | DONE (Andy, ~14:00), tests in tests/ |
| ssvep_stim.py `--tree` | phrase mode: tiles show groups then phrases, carer bar shows the phrase, `--phrase-log`, ignores picks within `--settle` 3 s of a group opening | works with scripted picks |
| ssvep_decode.py `--buzz-on phrase` | buzz only on a finished phrase (group+1 pulses); use `--refractory 4` in phrase mode | runs on fake; not tested with the ESP32 |
| RESULTS.md | the numbers and the limitations | current |
| EXPERT_PANEL_2026-11-07.md | three expert reviews, gates, evaluation protocol | reference |
| GTEC_TRACK_RESEARCH.md | headset facts, Mac routes, judge questions | reference |

Headline public result: 12 targets, held-out blocks, 10 subjects. 0.5 s window: generic CCA
20%, personal TRCA 74% after 12 s of calibration. 1 s: 53% -> 89% after 24 s. Fig: data/speed_accuracy.png.

## Live headset: what happened and what is next
Slot 1 (about 12:00 to 12:30): the amplifier was not seated on the cap, every even channel
read a flat rail (+200 mV), odd channels 130 to 520 uV, no alpha. No usable data.
Next slot, in order, do not skip:
1. Cap on, amplifier pressed flat onto both pogo-pin rows, mastoid stickies with L/R clips,
   chin strap tight, twist electrodes through hair, wait 2 min.
2. `.venv/bin/python unicorn/unicorn_gpype.py --serial U8-2025.10.14` (keep window open).
3. `.venv/bin/python unicorn/alpha_check.py`: pass = PO7 POz PO8 Pz under 40 uV RMS and
   eyes-closed/open alpha ratio at POz of 2 or more. Fail = fix contact, do not decode.
4. Calibration (two terminals): `ssvep_stim.py --trials 12 --on 4 --off 2` and
   `ssvep_calibrate.py --lsl --out models/NAME.npz`. 48 s of looking.
5. Held-out trial: `ssvep_stim.py --trials 12` and
   `ssvep_decode.py --lsl --model models/NAME.npz --log NAME_test.csv [--cue-port ...]`.
   The end-of-run summary gives hits, misses, false picks per minute; the log has TRCA and
   CCA scores side by side for the slide.
6. 2 min eyes-open rest with the decoder armed (no stim): false selections per minute.
7. Film the best run on a phone. The bridge auto-saves unicorn_rec_*.csv; keep them.

## DECISION 17:00 Sat: NO FLICKER. Scanning + blink switch is the product
The user rejected flicker (tiring, impractical). The product is now a scanning communication aid:
a highlight walks the tiles (`ssvep_stim.py --spell --tiles 12 --scan 1.0 --speak`), a deliberate
blink on Fz selects (`blink_switch.py --lsl`, sends "sel" over UDP 5005; space bar fakes it).
Letters in two blinks, predicted word in one, phrases (`--tree --scan 1.0`) in two.
AI: a deliberate-vs-spontaneous blink classifier trained on the team's logged blinks
(`blink_switch.py --log`), held-out people, false-selection rate. SSVEP/TRCA code stays in the
repo as the optional fast mode and the public-data result stays on the slides as prior work.
Only Fz and the mastoid stickies need to work for the demo.

## Scope is frozen
Four tiles, personal vs generic decoder, fixed 16-phrase tree (two looks per phrase,
generated once, not a runtime LLM), wristband, replay mode. No new features.

## Honest lines for the pitch
- "Trained and evaluated on ten public subjects with held-out blocks; replicated on N of us."
- "Three healthy students, one room, one afternoon, dry electrodes: a lab-condition ceiling."
- To the Tobii judge: an eye tracker does look-to-select with a camera; this does it with no
  camera and no lighting dependence, through glasses. A comparison, not a victory.
- Never: "helps patients", "clinically validated".

## Who did what (keep it true)
Pipeline and analysis code: written with Claude (AI assistant) during the event, directed by
Paing. g.Pype is g.tec's SDK. TRCA is Nakanishi et al. 2018. Dataset Nakanishi et al. 2015.
