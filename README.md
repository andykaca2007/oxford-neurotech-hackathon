# Oxford Neurotech Hackathon 2026: team Avengers, AI stream (Tobii)

A personal SSVEP brain decoder used as a hands-free communication aid. The user looks at one of
four flickering tiles; two looks say one of 16 fixed phrases, which appears on the carer bar and
buzzes the carer's wristband. The science claim: how much per-person calibration the decoder
needs (personal TRCA against generic CCA, held-out blocks, public data, replicated live).

Branches and pull requests, never direct to main: see [CONTRIBUTING.md](CONTRIBUTING.md).

**Start with [HANDOFF.md](HANDOFF.md)** (state of the build, headset checklist, honest pitch
lines), then [RESULTS.md](RESULTS.md) (numbers and limits).

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
- AI central: we train a model per person (TRCA). Neural data is the core input.
- Evaluation: held-out blocks, CCA baseline, accuracy and ITR (and false selections per minute).
- No covert recording; no inferring health conditions or other protected traits from people here.
- All code in `unicorn/` and `tests/` written during the event; credit libraries and datasets.

## Credits
- Nakanishi et al. 2015, PLoS ONE 10(10):e0140703 (12-target SSVEP dataset).
- TRCA: Nakanishi et al. 2018, IEEE TBME 65(1):104.
- g.Pype: g.tec's Python SDK for the Unicorn. pygame, NumPy, SciPy, pylsl, pyserial.
- Code written with Claude (AI assistant) during the event, directed by the team.
