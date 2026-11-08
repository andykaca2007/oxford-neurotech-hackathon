# Oxford Neurotech Hackathon 2026: team Avengers, AI stream (Tobii)

A live mental-load monitor on a dry 8-electrode headset (g.tec Unicorn BCI Core-8). A model trained on
public lab EEG (PhysioNet eegmat, 36 people, rest vs mental arithmetic) scores each 4 s window against the
wearer's own 30 s baseline and shows a load number, an alarm line, a head map, an eyes-closed Alpha check,
an optional personal Calibrate step, and a Claude-written debrief.

What is and is not shown (8 Nov):
- Lab only: leave-one-subject-out AUC 0.76, balanced accuracy 68%, at chance for about 1 in 6 people.
- The live model is the generic one; a personal model replaces it only if an interleaved calibration
  clears a held-out AUC of 0.80.
- Not shown on the cap yet: last night's recordings contain no detectable alpha, and the gauge did not
  reliably separate task from rest on them.

**Start with the morning summary at the end of [docs/OVERNIGHT.md](docs/OVERNIGHT.md)**, then
[docs/CRITIQUE.md](docs/CRITIQUE.md) (independent review, ranked) and [docs/PROTOCOL.md](docs/PROTOCOL.md).
Earlier state: [docs/HANDOFF.md](docs/HANDOFF.md), [docs/RESULTS.md](docs/RESULTS.md) (numbers there are
lab-only and partly superseded). The SSVEP communication aid we explored first is under `explored/`.

Branches and pull requests, never direct to main: see [CONTRIBUTING.md](CONTRIBUTING.md).

## Layout
| path | what |
|---|---|
| `loadmonitor/` | THE PRODUCT: mental-load model (`readiness_model.py`), live gauge (`load_gauge.py`), web dashboard (`gauge_server.py` + `web/index.html`), model figures |
| `headset/` | Unicorn BCI Core-8 bridge to LSL (`unicorn_gpype.py`), raw-Bluetooth fallback, live viewer, alpha/contact check |
| `explored/ssvep/` | SSVEP decoder, TRCA, public calibration curve, flicker screen, replay: explored Saturday, kept as evidence |
| `explored/communication/` | phrase tree, speller, blink switch |
| `explored/control/` | head-command detector, runner game, robot arena |
| `figures/` | result plots (committed) |
| `docs/` | PLAN (read first), RESULTS, HANDOFF, expert panel, headset research |
| `tests/` | `python -m pytest tests` |
| `data/` | datasets, not committed: `data/eegmat/` (PhysioNet) and `data/nakanishi2015/` |
| `models/`, `recordings/` | trained model and headset recordings: local only |
| `pre_event/` | material from **before** the hackathon: declare as brought kit, not hackathon code |

## Setup
```bash
python -m venv .venv
# Mac:      .venv/bin/python -m pip install -r requirements.txt
# Windows:  .venv\Scripts\python -m pip install -r requirements.txt
```
Public dataset: Nakanishi et al. 2015, from github.com/mnakanishi/12JFPM_SSVEP, files
`s1.mat` to `s10.mat` into `data/nakanishi2015/`.

## Phrase mode (two looks per phrase)
Two terminals, run from the repo root:
```bash
python explored/ssvep/ssvep_stim.py --tree --speak --phrase-log recordings/NAME_phrases.csv   # --speak: the Mac says the phrase (no wristband at the event)
python explored/ssvep/ssvep_decode.py --lsl --model models/NAME.npz --refractory 4 --buzz-on phrase [--cue-port PORT]
```
- Look 1 opens a group (NEED, BODY, PEOPLE, ANSWER); the tiles then show that group's phrases.
  Look 2 says the phrase. No second look within `--tree-timeout` (10 s) goes back to the groups,
  so one stray pick never says anything.
- `--refractory 4` (window + 1 s) makes the decoder wait for fresh EEG before the second look;
  the stim also ignores picks within `--settle` (3 s) of a group opening.
- The wristband buzzes once per finished phrase: 1 to 4 pulses for the group.
- The phrase log records every open, say, timeout and ignored pick, for looks-per-message.

No headset (replay of held-out public trials, labelled REPLAY on screen):
```bash
python explored/ssvep/ssvep_stim.py --tree --banner REPLAY
python explored/ssvep/replay_demo.py --subject 3 --say "Water, please;Call the nurse;Yes"
```

## Rules we must meet (AI stream)
- AI central: a model trained on public EEG scores the wearer's brain data live; a personal model is used only if its held-out calibration clears 0.80; Claude writes the debrief. (The explored SSVEP aid used per-person TRCA.)
- Evaluation: held-out blocks, CCA baseline, accuracy and ITR (and false selections per minute).
- No covert recording; no inferring health conditions or other protected traits from people here.
- All code in `loadmonitor/`, `headset/`, `explored/` and `tests/` written during the event; credit libraries and datasets.

## Credits
- Nakanishi et al. 2015, PLoS ONE 10(10):e0140703 (12-target SSVEP dataset).
- TRCA: Nakanishi et al. 2018, IEEE TBME 65(1):104.
- g.Pype: g.tec's Python SDK for the Unicorn. pygame, NumPy, SciPy, pylsl, pyserial.
- Code written with Claude (AI assistant) during the event, directed by the team.
