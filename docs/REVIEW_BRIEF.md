# Review brief (for an outside agent checking this work)

Repo: `~/Documents/hackathons/oxneurotech_2026-11-07`, branch `paing/readiness` (pushed to
github.com/andykaca2007/oxford-neurotech-hackathon). Product: a live EEG mental-load monitor on a g.tec Unicorn
BCI Core-8 dry headset, for the Oxford Neurotech Hackathon (7 to 8 Nov 2026). The deliverable is a 3-minute video.

Your job: **check, do not change.** Find bugs, wrong numbers, and claims the evidence does not support. Write the
findings to `docs/REVIEW_ANTIGRAVITY.md` (format at the end). Another agent (Claude) commits to this branch about
every 10 minutes, so do not edit tracked files in this checkout.

## Hard rules

1. **Never touch port 8765** (Paing's live page) and never kill his processes: `run_all.sh`, `gauge_server.py` (no
   port argument), `load_gauge.py --lsl ...`, `headset/unicorn_gpype.py`. Check `ps` before killing anything.
2. `tests/smoke.sh` and `tests/replay_all.py` each claim a free port from 8799 upward (`tests/free_port.py`, never
   8765) and write per-port log names, so your runs and Claude's loop can run at the same time. To look at the page,
   use a spare port such as 8797 (recipe below).
3. Do not start the headset bridge. Bluetooth only works from Paing's Terminal.app.
4. Do not commit, push, force-push, merge, or touch `main`. If you want to try a code change, make your own branch in
   a separate worktree (`git worktree add ../oxn_review -b antigravity/review`) and never push it.
5. Do not inflate numbers or claim the headset or model works on a head. Nothing has been shown to.

## Folder map

| Path | What it is |
|---|---|
| `run_all.sh` | One command for a live session: bridge, page server, gauge. `./run_all.sh replay <file>` replays a recording |
| `loadmonitor/load_gauge.py` | **The live gauge.** Reads LSL (or `--replay` / `--fake`), scores every second, posts state to the page |
| `loadmonitor/model_search.py` | Cleaning chain (`clean_window`, `ROBUST_CFG`), artefact subspace reconstruction (`ASR`), features (`feats`), model fitting (`--fit-best`) |
| `loadmonitor/calibration.py` | Personal Calibrate test: leave-one-pair-out LDA, shared with the tests |
| `loadmonitor/gauge_server.py` | Page server: `/state`, `/event`, `/debrief` (Claude debrief with template fallback), `summary()` |
| `loadmonitor/web/index.html` | The page: load number, fatigue, head map (contact view and change view), markers, buttons |
| `loadmonitor/readiness_model.py` | Lab data loader (`load_edf`) and basic features |
| `headset/montage.py` | Channel order: Fz C3 Cz C4 Pz P3 O1 P4 ("layout A") |
| `headset/unicorn_gpype.py` | Bluetooth bridge to LSL, writes the raw CSV |
| `tests/` | `smoke.sh` (end to end), `replay_all.py` (every recording through the gauge), `test_*.py` (pytest), `alpha_check_eval.py`, `calib_null.py`, `calib_inject.py` (evidence scripts) |
| `docs/OVERNIGHT.md` | Log of every change with its evidence; read the latest entries first |
| `docs/CRITIQUE.md` | 84 ranked issues from 20 critic agents, each marked done, rejected or open, with reasons |
| `docs/PROTOCOL.md` | Demo protocol (alpha check, calibrate, silent subtraction) with dated amendments |
| `docs/OPTIMIZE.md`, `PLAN.md`, `README.md` | Model choices, demo plan, overview. OPTIMIZE is partly out of date (CRITIQUE claims-adv3, open) |
| `recordings/` | His raw sessions, 7 to 8 Nov (not in git). Files `paing_2026110[78]_*raw*.csv`, 8 channels in uV, 250 Hz |
| `models/readiness.joblib` | Live model (not in git). Stored with its exact rebuild command (`m["rebuild"]`) |
| `data/eegmat/` | PhysioNet EEG mental arithmetic dataset (36 people, rest `_1.edf` and task `_2.edf`) |
| `.vscode/tasks.json` | Run tasks matching `run_all.sh` |

## The live pipeline, in order (`load_gauge.py`)

1. One 4 s window per second from LSL.
2. Dead check per channel: flat, or any sample on the +/-200 mV rail (open input).
3. Contact numbers per electrode (`contact_metrics`): hum 48 to 52 Hz; 1 to 40 Hz RMS after a 50 Hz notch; and
   8 to 13 Hz RMS.
4. Alpha height per electrode (`alpha_height`), used by the Alpha check (`alpha_rule`, `layout_note`).
5. Cleaning chain on the 5 model channels (Fz C3 Cz Pz O1):
   - cubic detrend
   - notch at 50 and 100 Hz
   - median common reference (dead channels zeroed)
   - 4 to 30 Hz band-pass
   - Hilbert burst mask
   - ASR fitted on the baseline
6. 29 amplitude-invariant features, then gradient boosting (lab leave-one-subject-out AUC 0.76).
7. Load = 40 x (smoothed p minus rest mean) / rest sd, so about 0 at rest. Alarm at 50 held for 20 s.
8. The load is **held, not scored**, in four cases:
   - a model channel is dead (CHANNEL LOST)
   - fewer than 2 channels are clean, meaning under 100 uV after cleaning (NOISY)
   - the stream stops (NO DATA)
   - a personal model is on and any model channel is not clean (HELD)

   The load keeps scoring during an Alpha check and during Calibrate. Eyes closed in the Alpha check will move it.
9. Fatigue = median Hilbert-envelope ratio (theta + alpha) / beta on the cleaned window. It is a published ratio,
   not trained. It is shown only after 20 min of monitoring.

## How to run the checks

```bash
cd ~/Documents/hackathons/oxneurotech_2026-11-07
.venv/bin/python -m pytest -q tests                 # unit tests, seconds
bash tests/smoke.sh                                  # end to end on a claimed port, about 4 min, must print ALL PASS
.venv/bin/python tests/replay_all.py                 # all recordings at 40x on a claimed port, must end "0 failed"
.venv/bin/python tests/alpha_check_eval.py           # Alpha check: chance, injected real alpha, flank attack (2 min)
.venv/bin/python tests/calib_null.py                 # Calibrate null and lab positive control (5 min)
.venv/bin/python tests/calib_inject.py               # Calibrate with an injected effect (2 min)
```

To look at the page on a replay (spare port 8797, stop both processes afterwards):

```bash
.venv/bin/python loadmonitor/gauge_server.py 8797 &
.venv/bin/python loadmonitor/load_gauge.py --replay recordings/<file>_raw_<...>.csv --speed 1 --web --web-port 8797 --no-ui --alarm 50 --hold 20 --smooth 12 &
open http://localhost:8797
```

## What is known and must not be "fixed" into a claim

- No brain signal has been shown on this cap. None of the 16 recordings has alpha, and no eyes-closed test was ever
  recorded. The raw signal was mostly 50 Hz hum and drift.
- The model is validated on lab gel-cap data only (AUC 0.76, 36 people). It is untested on this cap.
- Several thresholds were chosen on these same recordings: alarm 50, gain 40, the Alpha check rule, and the 40 and
  100 uV contact limits. They need new data to validate.
- Calibrate and the Alpha check have never run on a head.

## What to review, most important first

1. **Can a number be shown that the data does not support?** Walk through the main loop branches in `load_gauge.py`
   (baseline, CONTACT LOST, CHANNEL LOST / NOISY hold, scoring, NO DATA). Check that every held state is held on the
   page too (`index.html` `tick()`).
2. **Alpha check:** `alpha_height`, `alpha_rule`, the 15 uV noise gate, the timing (eyes-open 4 to 19 s,
   eyes-closed 24 to 39 s) and `layout_note`. Re-run `alpha_check_eval.py`.
3. **Contact view:** `contact_metrics`, the 40 and 100 uV limits (measured: lab gel cap 7 to 17 uV, his cap a median
   of 140 to 290 uV), and the fix-first line in `index.html`.
4. **Calibrate:** block collection in `load_gauge.py` and `calibration.py`. CRITIQUE calib-3 and calib-4 are open.
5. **Debrief honesty:** `gauge_server.py` `summary()`, `CONTEXT`, `fallback_live`, `fallback_debrief`. Held seconds
   must be excluded, and the debrief must say UNVERIFIED unless the Alpha check passed.
6. **Docs vs numbers:** every number in README, PROTOCOL, PLAN, OPTIMIZE and OVERNIGHT should match a script output.
7. **Open CRITIQUE items:** the rows in `docs/CRITIQUE.md` whose last column says `open`.

## How to report

Create `docs/REVIEW_ANTIGRAVITY.md` (a new file, do not commit it) with one row per finding:

| # | Severity (high / medium / low) | file:line | What is wrong | Evidence (command and its output, or the exact lines) | Suggested fix |

Mark anything you could not reproduce as "unverified". Claude will re-check each finding against the recordings
before changing code.
