#!/usr/bin/env bash
# One command for the whole mental-load demo: headset bridge + web page + live gauge + browser.
#
#   ./run_all.sh                      # headset U8-2025.10.14 (default)
#   ./run_all.sh U8-2025.11.14        # another amplifier
#   ./run_all.sh fake                 # no headset: fake signal, for rehearsing
#   ./run_all.sh replay recordings/<x>_raw_<y>.csv   # fallback: a recorded session through the live page, shown as REPLAY
#   ./run_all.sh lab 3.5              # same at 3.5x speed: the whole 210 s fits a 60 s video
#   ./run_all.sh lab                  # demo fallback: a held-out lab person (rest, arithmetic, rest) through the live page;
#                                     #   build it once with .venv/bin/python loadmonitor/lab_demo.py
#   ./run_all.sh U8-2025.10.14 andy   # second word = who is wearing it; names the recordings
#   ./run_all.sh "" paing 4ch         # third word 4ch = the model without C3 (Fz Cz Pz O1), when C3 will not connect
#
# Every run writes two CSVs in recordings/: <who>_<date>_<time>_raw.csv (all 8 channels, 250 Hz,
# from the bridge) and <who>_<date>_<time>_gauge.csv (load, alarm and features, once a second).
#
# Ctrl-C stops everything. Logs in logs/. Needs Bluetooth permission for the app you run it from
# (Terminal or VS Code: System Settings > Privacy & Security > Bluetooth).
set -u
cd "$(dirname "$0")"
PY=.venv/bin/python
SERIAL="${1-U8-2025.10.14}"          # no colon: an explicit '' means "whichever amplifier answers" (CRITIQUE ops-3)
ALLOW="U8-2025.10.14 U8-2025.11.14"   # our two amplifiers; other teams' Unicorns in the room are never picked
WHO="${2:-anon}"                      # ./run_all.sh U8-2025.10.14 paing  -> files named with the wearer
REPLAY_FILE=""
SPEED=1
BASE=30
FAT_ARG=""
MODEL_ARG=""                          # plain string, not an array: bash 3.2 with set -u rejects an empty array
if [ "${3-}" = "4ch" ]; then
  if [ ! -f models/readiness_4ch.joblib ]; then
    echo "models/readiness_4ch.joblib missing: .venv/bin/python loadmonitor/model_search.py --fit-best --robust --invariant --channels Fz,Cz,Pz,O1 --out models/readiness_4ch.joblib"; exit 1; fi
  MODEL_ARG="--model models/readiness_4ch.joblib"
  echo "MODEL: 4 electrodes (Fz Cz Pz O1), C3 not used"
fi
if [ "$SERIAL" = "lab" ]; then
  REPLAY_FILE=$(ls -t demo/lab_eegmat_s*_raw.csv 2>/dev/null | head -1); WHO="lab"
  if [ -z "$REPLAY_FILE" ] || [ ! -f models/readiness_demo.joblib ]; then
    echo "lab demo files missing: run  .venv/bin/python loadmonitor/lab_demo.py  once (about 5 min)"; exit 1; fi
  SERIAL="replay"; MODEL_ARG="--model models/readiness_demo.joblib"; SPEED="${2:-1}"; BASE="${3:-30}"; FAT_ARG="--fatigue-show-s 0"   # lab demo: fatigue shown at once, labelled slow trend   # ./run_all.sh lab 2.33 20 = 90 s video, 20 s baseline (10 s or less: the alarm never fires on this person)
  echo "LAB DEMO: $REPLAY_FILE with models/readiness_demo.joblib (that person held out of training)"
elif [ "$SERIAL" = "replay" ]; then
  REPLAY_FILE="${2:-}"; WHO="replay"
  if [ ! -f "$REPLAY_FILE" ]; then echo "usage: ./run_all.sh replay recordings/<name>_raw_<stamp>.csv"; ls -t recordings/*raw*.csv | head -5; exit 1; fi
fi
mkdir -p logs recordings
STAMP=$(date +%Y%m%d_%H%M%S)
SESSION="recordings/${WHO}_${STAMP}"
STREAM="Unicorn_${STAMP}"             # this session's own LSL stream name: no other laptop's or session's stream is picked
echo "session files: ${SESSION}_raw.csv (8-ch EEG at 250 Hz) and ${SESSION}_gauge.csv (load per second)"
PIDS=()
cleanup() { trap - EXIT; echo; echo "stopping"; for p in "${PIDS[@]}"; do kill "$p" 2>/dev/null; done; pkill -f loadmonitor/load_gauge.py 2>/dev/null; exit 0; }
trap cleanup INT TERM EXIT
# a gauge or launcher left from an earlier session (e.g. a Terminal that was never stopped) would wake up on this
# session's stream and post to the same page (CRITIQUE ops-2): stop them first
for p in $(pgrep -f "run_all.sh" | grep -vx -e "$$" -e "$PPID"); do kill "$p" 2>/dev/null; done   # not itself, not the shell that launched it
pkill -f loadmonitor/load_gauge.py 2>/dev/null

# 1. web page (reuse if already up)
# always a fresh web server: a leftover one (from another folder or a dead run) answers once and then refuses
pkill -f gauge_server.py 2>/dev/null; sleep 0.5
$PY loadmonitor/gauge_server.py > logs/server_$STAMP.log 2>&1 &
PIDS+=($!)
sleep 1.5
if curl -s -o /dev/null http://127.0.0.1:8765/state; then echo "web page started"; else echo "web page FAILED, see logs/server_$STAMP.log"; fi

if [ "$SERIAL" != "fake" ] && [ "$SERIAL" != "replay" ]; then
  # 2. headset bridge (its scope window must stay open; minimise it)
  pkill -f unicorn_gpype.py 2>/dev/null
  start_bridge() {
    $PY headset/unicorn_gpype.py ${SERIAL:+--serial "$SERIAL"} --stream "$STREAM" --csv "${SESSION}_raw.csv" > logs/bridge_$STAMP.log 2>&1 &
    BRIDGE_PID=$!
    PIDS+=($BRIDGE_PID)
    echo "connecting to ${SERIAL:-whichever amplifier answers} ..."
  }
  start_bridge
  SWITCHED=0
  for i in $(seq 1 60); do
    if $PY -c "from pylsl import resolve_byprop; import sys; sys.exit(0 if resolve_byprop('name','$STREAM',timeout=1) else 1)" 2>/dev/null; then
      echo "headset streaming${SERIAL:+ from $SERIAL}"; break
    fi
    if ! kill -0 "$BRIDGE_PID" 2>/dev/null; then
      # the scan heard the OTHER one of our amplifiers: switch to it once (last night 5 of 25 launches died this way)
      HEARD=$(grep -o "heard \['U8-[0-9.]*'" logs/bridge_$STAMP.log | head -1 | grep -o "U8-[0-9.]*")
      if [ "$SWITCHED" = 0 ] && [ -n "$HEARD" ] && [ "$HEARD" != "$SERIAL" ] && echo " $ALLOW " | grep -q " $HEARD "; then
        echo "$SERIAL not found; the scan heard $HEARD, our other amplifier: switching to it."
        echo "CHECK it is the one on the head: run the Alpha check before trusting any number."
        SERIAL="$HEARD"; SWITCHED=1; sleep 1; start_bridge; continue
      fi
      echo "bridge died, see logs/bridge_$STAMP.log:"; tail -3 logs/bridge_$STAMP.log; cleanup
    fi
    sleep 1
  done
fi

# 3. browser
open http://localhost:8765 2>/dev/null || true

# 4. the gauge, in the foreground so Ctrl-C ends the demo
if [ "$SERIAL" = "fake" ]; then
  $PY loadmonitor/load_gauge.py --fake --web --no-ui
elif [ "$SERIAL" = "replay" ]; then
  echo "REPLAY of $REPLAY_FILE at real time; the page shows a REPLAY banner"
  $PY loadmonitor/load_gauge.py --replay "$REPLAY_FILE" $MODEL_ARG --show-noisy --speed $SPEED --baseline $BASE $FAT_ARG --web --no-ui --alarm 50 --hold 20 --smooth 12 --log "${SESSION}_gauge.csv"
else
  # alarm at 50 held 20 s, 12 s smoothing: on this cap Zetamac reaches about 50 and rest wobbles 0 to 36
  # --show-noisy: keep the number moving when channels are noisy, greyed as LOW CONFIDENCE with the alarm off (Paing, 8 Nov)
  $PY loadmonitor/load_gauge.py --lsl --stream "$STREAM" $MODEL_ARG --show-noisy --web --no-ui --alarm 50 --hold 20 --smooth 12 --log "${SESSION}_gauge.csv"
fi
cleanup
