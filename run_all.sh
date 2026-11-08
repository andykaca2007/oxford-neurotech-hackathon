#!/usr/bin/env bash
# One command for the whole mental-load demo: headset bridge + web page + live gauge + browser.
#
#   ./run_all.sh                      # headset U8-2025.10.14 (default)
#   ./run_all.sh U8-2025.11.14        # another amplifier
#   ./run_all.sh fake                 # no headset: fake signal, for rehearsing
#   ./run_all.sh replay recordings/<x>_raw_<y>.csv   # fallback: a recorded session through the live page, shown as REPLAY
#   ./run_all.sh U8-2025.10.14 andy   # second word = who is wearing it; names the recordings
#
# Every run writes two CSVs in recordings/: <who>_<date>_<time>_raw.csv (all 8 channels, 250 Hz,
# from the bridge) and <who>_<date>_<time>_gauge.csv (load, alarm and features, once a second).
#
# Ctrl-C stops everything. Logs in logs/. Needs Bluetooth permission for the app you run it from
# (Terminal or VS Code: System Settings > Privacy & Security > Bluetooth).
set -u
cd "$(dirname "$0")"
PY=.venv/bin/python
SERIAL="${1:-U8-2025.10.14}"
WHO="${2:-anon}"                      # ./run_all.sh U8-2025.10.14 paing  -> files named with the wearer
REPLAY_FILE=""
if [ "$SERIAL" = "replay" ]; then
  REPLAY_FILE="${2:-}"; WHO="replay"
  if [ ! -f "$REPLAY_FILE" ]; then echo "usage: ./run_all.sh replay recordings/<name>_raw_<stamp>.csv"; ls -t recordings/*raw*.csv | head -5; exit 1; fi
fi
mkdir -p logs recordings
STAMP=$(date +%Y%m%d_%H%M%S)
SESSION="recordings/${WHO}_${STAMP}"
echo "session files: ${SESSION}_raw.csv (8-ch EEG at 250 Hz) and ${SESSION}_gauge.csv (load per second)"
PIDS=()
cleanup() { echo; echo "stopping"; for p in "${PIDS[@]}"; do kill "$p" 2>/dev/null; done; exit 0; }
trap cleanup INT TERM

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
  $PY headset/unicorn_gpype.py --serial "$SERIAL" --csv "${SESSION}_raw.csv" > logs/bridge_$STAMP.log 2>&1 &
  BRIDGE_PID=$!
  PIDS+=($BRIDGE_PID)
  echo "connecting to $SERIAL ..."
  for i in $(seq 1 40); do
    if $PY -c "from pylsl import resolve_byprop; import sys; sys.exit(0 if resolve_byprop('name','Unicorn',timeout=1) else 1)" 2>/dev/null; then
      echo "headset streaming"; break
    fi
    if ! kill -0 "$BRIDGE_PID" 2>/dev/null; then echo "bridge died, see logs/bridge_$STAMP.log:"; tail -3 logs/bridge_$STAMP.log; cleanup; fi
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
  $PY loadmonitor/load_gauge.py --replay "$REPLAY_FILE" --speed 1 --web --no-ui --alarm 50 --hold 20 --smooth 12 --log "${SESSION}_gauge.csv"
else
  # alarm at 50 held 20 s, 12 s smoothing: on this cap Zetamac reaches about 50 and rest wobbles 0 to 36
  $PY loadmonitor/load_gauge.py --lsl --web --no-ui --alarm 50 --hold 20 --smooth 12 --log "${SESSION}_gauge.csv"
fi
cleanup
