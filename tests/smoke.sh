#!/usr/bin/env bash
# Demo smoke test: every path the Sunday demo uses, except the Bluetooth link itself.
#   ./tests/smoke.sh          (from the repo root; takes about 2 minutes)
# Prints PASS/FAIL per step and exits non-zero if anything failed.
cd "$(dirname "$0")/.."
PY=.venv/bin/python
PORT=8765
fails=0
step() { printf '%-58s' "$1"; }
ok()   { echo "PASS"; }
bad()  { echo "FAIL  ($1)"; fails=$((fails+1)); }

step "python files compile"
if for f in $(find loadmonitor headset explored tests -name '*.py'); do $PY -c "import ast,sys; ast.parse(open('$f').read())" || exit 1; done; then ok; else bad "syntax error"; fi

step "unit tests (pytest)"
if $PY -m pytest -q tests >/tmp/smoke_pytest.log 2>&1; then ok; else bad "see /tmp/smoke_pytest.log"; fi

step "montage is 8 unique names and the model's channels are in it"
if $PY - <<'EOF' 2>/dev/null; then ok; else bad "montage/model mismatch"; fi
import sys, joblib; sys.path.insert(0,'headset'); from montage import MONTAGE
assert len(MONTAGE)==8 and len(set(MONTAGE))==8
m = joblib.load('models/readiness.joblib'); assert all(c in MONTAGE for c in m['channels']), m['channels']
EOF

step "model file loads, has the expected fields"
if $PY -c "import joblib; m=joblib.load('models/readiness.joblib'); assert m['epoch_s']>0 and 'model' in m and m.get('loso_auc',0)>0.6" 2>/dev/null; then ok; else bad "models/readiness.joblib missing or odd: run loadmonitor/model_search.py --fit-best"; fi

step "web server starts and serves the page"
pkill -f gauge_server.py 2>/dev/null; sleep 0.5
$PY loadmonitor/gauge_server.py >/tmp/smoke_server.log 2>&1 & SRV=$!
sleep 1.5
if [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$PORT/)" = "200" ]; then ok; else bad "no page on $PORT"; fi

step "gauge on fake data: baseline, load rises, alarm fires"
pkill -f load_gauge.py 2>/dev/null; sleep 0.5
$PY loadmonitor/load_gauge.py --fake --web --no-ui --baseline 8 --hold 10 --seconds 110 --log /tmp/smoke_gauge.csv >/tmp/smoke_gauge.log 2>&1 &
GPID=$!
sleep 7
curl -s -X POST http://127.0.0.1:$PORT/event -d '{"kind":"condition","value":"mental"}' >/dev/null
wait $GPID
if grep -q "baseline done" /tmp/smoke_gauge.log && grep -q "ALARM load" /tmp/smoke_gauge.log; then ok; else bad "see /tmp/smoke_gauge.log"; fi

step "gauge CSV has load, condition column, and markers file"
if [ -s /tmp/smoke_gauge.csv ] && head -1 /tmp/smoke_gauge.csv | grep -q "condition" && grep -q "mental" /tmp/smoke_gauge_markers.csv; then ok; else bad "csv/markers"; fi

step "page state has 8 channels and the condition"
if curl -s http://127.0.0.1:$PORT/state | $PY -c "import json,sys; s=json.load(sys.stdin); assert len(s['channels'])==8 and s['condition']=='mental'" 2>/dev/null; then ok; else bad "state json"; fi

step "challenge events accepted, debrief returns text"
curl -s -X POST http://127.0.0.1:$PORT/event -d '{"kind":"challenge_start"}' >/dev/null
curl -s -X POST http://127.0.0.1:$PORT/event -d '{"kind":"error","value":1,"expected":3993}' >/dev/null
if curl -s -X POST http://127.0.0.1:$PORT/debrief -d '{}' | $PY -c "import json,sys; d=json.load(sys.stdin); assert len(d['text'])>40; print('   debrief by', d['source'])" ; then ok; else bad "debrief"; fi

step "headset bridge in --sim mode streams to LSL (no Bluetooth)"
pkill -f unicorn_gpype.py 2>/dev/null; sleep 0.5
( sleep 12; echo ) | $PY headset/unicorn_gpype.py --sim --csv /tmp/smoke_raw.csv >/tmp/smoke_bridge.log 2>&1 &
sleep 5
if $PY -c "from pylsl import resolve_byprop; import sys; sys.exit(0 if resolve_byprop('name','Unicorn',timeout=5) else 1)" 2>/dev/null; then ok; else bad "no LSL stream from --sim"; fi

step "gauge --lsl reads the sim stream and posts state"
timeout_s=8; $PY loadmonitor/load_gauge.py --lsl --web --no-ui --baseline 3 --seconds 6 >/tmp/smoke_lsl.log 2>&1
if grep -q "baseline done" /tmp/smoke_lsl.log; then ok; else bad "see /tmp/smoke_lsl.log"; fi
sleep 8

step "raw recording CSV written by the bridge"
if ls /tmp/smoke_raw*.csv >/dev/null 2>&1 && [ "$(wc -l < $(ls /tmp/smoke_raw*.csv | head -1))" -gt 500 ]; then ok; else bad "no raw csv"; fi

step "SSVEP decoder on fake data (explored path still runs)"
if $PY explored/ssvep/ssvep_decode.py --fake --seconds 6 2>/dev/null | grep -q "pick=0"; then ok; else bad "ssvep decode"; fi

step "run_all.sh parses (bash 3.2 safe)"
if bash -n run_all.sh; then ok; else bad "run_all.sh syntax"; fi

kill $SRV 2>/dev/null; pkill -f unicorn_gpype.py 2>/dev/null
echo
if [ $fails -eq 0 ]; then echo "ALL PASS"; else echo "$fails FAILED"; fi
exit $fails
