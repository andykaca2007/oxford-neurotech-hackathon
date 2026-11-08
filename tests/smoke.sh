#!/usr/bin/env bash
export OXN_QUIET=1     # the gauge never speaks from a test
# Demo smoke test: every path the Sunday demo uses, except the Bluetooth link itself.
#   ./tests/smoke.sh          (from the repo root; takes about 2 minutes)
# Prints PASS/FAIL per step and exits non-zero if anything failed.
cd "$(dirname "$0")/.."
PY=.venv/bin/python
# a free port from 8799 upward (never the live page port 8765), claimed so a second agent's run cannot share it
PORT=$($PY tests/free_port.py) || { echo "no free test port"; exit 1; }
trap 'rmdir /tmp/oxn_test_port_$PORT 2>/dev/null' EXIT   # release the claim (tests/free_port.py)
T=/tmp/smoke$PORT   # per-port log names, so two runs never write the same files
echo "# test port $PORT"
fails=0
step() { printf '%-58s' "$1"; }
ok()   { echo "PASS"; }
bad()  { echo "FAIL  ($1)"; fails=$((fails+1)); }

step "python files compile"
if for f in $(find loadmonitor headset explored tests -name '*.py'); do $PY -c "import ast,sys; ast.parse(open('$f').read())" || exit 1; done; then ok; else bad "syntax error"; fi

step "unit tests (pytest)"
if $PY -m pytest -q tests >${T}_pytest.log 2>&1; then ok; else bad "see ${T}_pytest.log"; fi

step "montage is 8 unique names and the model's channels are in it"
if $PY - <<'EOF' 2>/dev/null; then ok; else bad "montage/model mismatch"; fi
import sys, joblib; sys.path.insert(0,'headset'); from montage import MONTAGE
assert len(MONTAGE)==8 and len(set(MONTAGE))==8
m = joblib.load('models/readiness.joblib'); assert all(c in MONTAGE for c in m['channels']), m['channels']
EOF

step "model file loads, has the expected fields"
if $PY -c "import joblib; m=joblib.load('models/readiness.joblib'); assert m['epoch_s']>0 and 'model' in m and m.get('loso_auc',0)>0.6" 2>/dev/null; then ok; else bad "models/readiness.joblib missing or odd: rebuild with .venv/bin/python loadmonitor/model_search.py --fit-best --robust --invariant --channels Fz,C3,Cz,Pz,O1 --out models/readiness.joblib"; fi

step "web server starts and serves the page"
$PY loadmonitor/gauge_server.py $PORT >${T}_server.log 2>&1 & SRV=$!
sleep 1.5
if [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$PORT/)" = "200" ]; then ok; else bad "no page on $PORT"; fi

step "gauge on fake data: baseline, load rises, alarm fires"
$PY loadmonitor/load_gauge.py --fake --web --web-port $PORT --no-ui --baseline 8 --hold 10 --seconds 110 --log ${T}_gauge.csv >${T}_gauge.log 2>&1 &
GPID=$!
sleep 7
curl -s -X POST http://127.0.0.1:$PORT/event -d '{"kind":"condition","value":"mental"}' >/dev/null
wait $GPID
if grep -q "baseline done" ${T}_gauge.log && grep -q "ALARM load" ${T}_gauge.log; then ok; else bad "see ${T}_gauge.log"; fi

step "gauge CSV has load, condition column, and markers file"
if [ -s ${T}_gauge.csv ] && head -1 ${T}_gauge.csv | grep -q "condition" && grep -q "mental" ${T}_gauge_markers.csv; then ok; else bad "csv/markers"; fi

step "page state has 8 channels and the condition"
if curl -s http://127.0.0.1:$PORT/state | $PY -c "import json,sys; s=json.load(sys.stdin); assert len(s['channels'])==8 and s['condition']=='mental'" 2>/dev/null; then ok; else bad "state json"; fi

step "challenge events accepted, debrief returns text"
curl -s -X POST http://127.0.0.1:$PORT/event -d '{"kind":"challenge_start"}' >/dev/null
curl -s -X POST http://127.0.0.1:$PORT/event -d '{"kind":"error","value":1,"expected":3993}' >/dev/null
if curl -s -X POST http://127.0.0.1:$PORT/debrief -d '{}' | $PY -c "import json,sys; d=json.load(sys.stdin); assert len(d['text'])>40; print('   debrief by', d['source'])" ; then ok; else bad "debrief"; fi

if pgrep -f "unicorn_gpype.py --serial" >/dev/null; then
  step "headset bridge --sim and gauge --lsl"; echo "SKIP  (a live headset session is running; a second LSL stream named Unicorn would confuse it)"
else
step "headset bridge in --sim mode streams to LSL (no Bluetooth)"
( sleep 25; echo ) | $PY headset/unicorn_gpype.py --sim --csv ${T}_raw.csv >${T}_bridge.log 2>&1 & BRP=$!
sleep 5
if $PY -c "from pylsl import resolve_byprop; import sys; sys.exit(0 if resolve_byprop('name','Unicorn',timeout=5) else 1)" 2>/dev/null; then ok; else bad "no LSL stream from --sim"; fi

step "gauge --lsl reads the sim stream and posts state"
$PY loadmonitor/load_gauge.py --lsl --web --web-port $PORT --no-ui --baseline 3 --seconds 12 >${T}_lsl.log 2>&1
if grep -q "baseline done" ${T}_lsl.log; then ok; else bad "see ${T}_lsl.log"; fi
sleep 8
fi

step "raw recording CSV written by the bridge (sim)"
if [ -z "$BRP" ]; then echo "SKIP"; elif ls -t ${T}_raw*.csv >/dev/null 2>&1 && [ "$(wc -l < $(ls -t ${T}_raw*.csv | head -1))" -gt 500 ]; then ok; else bad "no raw csv"; fi

step "SSVEP decoder on fake data (explored path still runs)"
if $PY explored/ssvep/ssvep_decode.py --fake --seconds 6 2>/dev/null | grep -q "pick=0"; then ok; else bad "ssvep decode"; fi

step "headset stall: NO DATA shown, page age grows, Ctrl-C stops the gauge"
$PY -c "import signal,os,sys; signal.signal(signal.SIGINT, signal.SIG_DFL); os.execv(sys.argv[1], sys.argv[1:])" $PY loadmonitor/load_gauge.py --fake --stall-after 30 --web --web-port $PORT --no-ui --baseline 4 >${T}_stall.log 2>&1 & STP=$!
for i in $(seq 1 40); do grep -q "NO DATA" ${T}_stall.log && break; sleep 1; done   # wait for the stall (start-up is slower under load)
sleep 2; kill -INT $STP 2>/dev/null; sleep 3
STALL_ALIVE=0; kill -0 $STP 2>/dev/null && STALL_ALIVE=1 && kill $STP 2>/dev/null
sleep 2
AGE=$(curl -s http://127.0.0.1:$PORT/state | $PY -c "import json,sys; print(int(json.load(sys.stdin).get('age_s') or 0))" 2>/dev/null)
if grep -q "NO DATA" ${T}_stall.log && [ "$STALL_ALIVE" = 0 ] && ! grep -q Traceback ${T}_stall.log && [ "${AGE:-0}" -ge 3 ]; then ok; else bad "see ${T}_stall.log (alive after Ctrl-C: $STALL_ALIVE, page age: $AGE)"; fi

step "replay of a real recording through the gauge"
R=$(ls recordings/paing_20261108_011525_raw*.csv 2>/dev/null | head -1)
if [ -z "$R" ]; then echo "SKIP"; elif $PY loadmonitor/load_gauge.py --replay "$R" --speed 40 --seconds 120 --web --web-port $PORT --no-ui >${T}_replay.log 2>&1 && grep -q "baseline done" ${T}_replay.log && ! grep -q Traceback ${T}_replay.log; then ok; else bad "see ${T}_replay.log"; fi

step "run_all.sh parses (bash 3.2 safe)"
if bash -n run_all.sh; then ok; else bad "run_all.sh syntax"; fi

kill $SRV 2>/dev/null; [ -n "$BRP" ] && kill $BRP 2>/dev/null
echo
if [ $fails -eq 0 ]; then echo "ALL PASS"; else echo "$fails FAILED"; fi
exit $fails
