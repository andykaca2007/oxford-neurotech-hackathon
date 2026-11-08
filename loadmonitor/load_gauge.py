"""Live mental-load gauge with a personal baseline and an alarm.

    .venv/bin/python loadmonitor/load_gauge.py --lsl [--log shift.csv]      # headset via unicorn_gpype.py
    .venv/bin/python loadmonitor/load_gauge.py --fake                        # no headset: rest, then load after 45 s
    add --no-ui for a text readout only

Protocol: the first --baseline seconds (default 30) the person sits quietly: that is their
own calm, and every later reading is relative to it (readiness_model.py showed this lifts
held-out detection from 63 to 70 percent). Then a 4 s window every second goes through the
same features and the trained classifier (models/readiness.joblib); the gauge shows a
smoothed probability of "under load" as 0 to 100. When it stays above --alarm for --hold
seconds the screen goes red and the Mac speaks. Keys: B redo the baseline, Esc quit.

Output rows: t, load_pct, alarm, then the 17 features. Honest reading of the number: how much
this brain looks like the public "doing arithmetic" recordings versus its own rest; not sleepiness,
not risk. Needs the model's channels alive (layout A: all 8).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import deque

import joblib
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from readiness_model import CH, features as features_basic  # noqa: E402
from model_search import feats as features_rich  # noqa: E402

FS = 250
from scipy.signal import butter as _butter, sosfiltfilt
SIG_SOS = _butter(4, [1, 40], btype="band", fs=FS, output="sos")
FAT_SOS_TH = _butter(4, [4, 8], btype="band", fs=FS, output="sos")
FAT_SOS_AL = _butter(4, [8, 13], btype="band", fs=FS, output="sos")
FAT_SOS_BE = _butter(4, [13, 30], btype="band", fs=FS, output="sos")
ALPHA_SOS = _butter(4, [2, 40], btype="band", fs=FS, output="sos")
POSTERIOR = ["Pz", "O1", "P3", "P4"]


def alpha_height(x):
    """Alpha peak height in dB per channel: mean of 8 to 13 Hz above a 1/f line fitted on 3 to 7 and 15 to 30 Hz.
    About +6 dB at Pz/O1 for lab-cap EEG at rest with eyes closed, about 0 for flat noise (overnight test, 8 Nov)."""
    from scipy.signal import iirnotch, tf2sos, welch
    x = x - x.mean(1, keepdims=True)
    t = np.linspace(-1, 1, x.shape[1])
    V = np.vander(t, 4)
    c, *_ = np.linalg.lstsq(V, x.T, rcond=None)
    x = x - (V @ c).T
    b, a_ = iirnotch(50.0, 30.0, fs=FS)
    x = sosfiltfilt(ALPHA_SOS, sosfiltfilt(tf2sos(b, a_), x, axis=1), axis=1)
    f, p = welch(x, fs=FS, nperseg=2 * FS, axis=1)
    fit = ((f >= 3) & (f < 7)) | ((f >= 15) & (f < 30))
    al = (f >= 8) & (f <= 13)
    lf = np.log10(f[1:])
    out = []
    for row in p:
        lp = np.log10(row[1:] + 1e-20)
        k = np.polyfit(lf[fit[1:]], lp[fit[1:]], 1)
        out.append(float(10 * (lp - np.polyval(k, lf))[al[1:]].mean()))
    return np.array(out)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'headset'))
from montage import MONTAGE  # noqa: E402
IDX = [MONTAGE.index(c) for c in CH]   # model channels -> stream slots, from headset/montage.py


def src_fake(seed=0):
    """Rest for 45 s (strong alpha at Pz/Cz), then load (frontal theta up, alpha down)."""
    rng = np.random.default_rng(seed)
    n = 0
    while True:
        t = n / FS
        x = rng.normal(0, 8, 8)
        load = t > 75
        a_amp = 6 if load else 14
        th_amp = 10 if load else 3
        x[4] += a_amp * np.sin(2 * np.pi * 10 * t)
        x[2] += 0.6 * a_amp * np.sin(2 * np.pi * 10 * t + 1)
        x[0] += th_amp * np.sin(2 * np.pi * 6 * t)
        yield t, x
        n += 1
        if n % 50 == 0:
            time.sleep(0.2 / 1.0 * 1.0 / 1.0 * 0.2)   # ~5x real time for a quick test


def src_replay(path, speed):
    """Stream a recorded raw CSV (recordings/*_raw*.csv) through the live pipeline at real time x speed."""
    rows = []
    for line in open(path):
        if line.startswith("#"):
            continue
        try:
            rows.append([float(v) for v in line.split(",")[1:9]])
        except ValueError:
            continue
    print(f"# REPLAY {os.path.basename(path)}: {len(rows) / FS:.0f} s at {speed:g}x", flush=True)
    for n, r in enumerate(rows):
        yield n / FS, np.array(r)
        if n % 50 == 49:
            time.sleep(0.2 / speed)


def src_lsl():
    from pylsl import StreamInlet, resolve_byprop
    s = resolve_byprop("name", "Unicorn", timeout=10)
    if not s:
        sys.exit("no LSL stream named Unicorn: start unicorn_gpype.py first")
    inlet = StreamInlet(s[0])
    t0 = None
    while True:
        smp, ts = inlet.pull_sample()
        if t0 is None:
            t0 = ts
        yield ts - t0, np.array(smp[:8])


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--lsl", action="store_true")
    g.add_argument("--fake", action="store_true")
    g.add_argument("--replay", default=None, help="stream a recorded raw CSV instead of the headset (demo fallback, test)")
    ap.add_argument("--model", default="models/readiness.joblib")
    ap.add_argument("--baseline", type=float, default=30.0)
    ap.add_argument("--alarm", type=float, default=70.0, help="load percent that triggers the alarm")
    ap.add_argument("--hold", type=float, default=20.0, help="s above --alarm before it fires")
    ap.add_argument("--smooth", type=float, default=8.0, help="s of smoothing on the gauge")
    ap.add_argument("--gain", type=float, default=40.0, help="load points per spread of the model output above the wearer's rest (36-subject sweep: 40 = task median 45, rest false alarm 2 percent)")
    ap.add_argument("--strict", action="store_true", help="contact gate + settle check before the baseline, and freeze on contact loss (off: the plain behaviour)")
    ap.add_argument("--speed", type=float, default=1.0, help="replay speed")
    ap.add_argument("--replay-markers", default=None, help="markers CSV (t,condition) to replay; default: the matching _gauge_markers.csv")
    ap.add_argument("--calib-s", type=int, default=0, help="seconds of mental to train a personal model; OFF by default: on 8 Nov replay it learned session drift, not effort (recovery read 77)")
    ap.add_argument("--load-min-clean", type=int, default=2, help="hold the load (label Held, noisy) when fewer channels than this are clean after the chain")
    ap.add_argument("--quality-uv", type=float, default=100.0, help="a channel counts as clean when its RMS AFTER the cleaning chain is under this (uV); fatigue needs 3 clean")
    ap.add_argument("--log")
    ap.add_argument("--no-ui", action="store_true")
    ap.add_argument("--web", action="store_true", help="post state to gauge_server.py (http://localhost:8765) every second")
    ap.add_argument("--web-port", type=int, default=8765)
    ap.add_argument("--seconds", type=float, default=0)
    a = ap.parse_args()

    m = joblib.load(a.model)
    clf = m["model"]
    fmask = m.get("feature_mask")
    if fmask is not None:
        print(f"# amplitude-invariant features: {int(fmask.sum())} of {len(fmask)} (absolute power dropped, contact quality cannot push the needle)", flush=True)
    riem = None
    if m.get("riem"):
        from riem_live import RiemFB
        riem = RiemFB(FS, m["riem"]["ts"])
        riem_clf = m["riem"]["clf"]
        print("# stack: boosting on band powers + logistic on Riemannian filter-bank covariances, probabilities averaged", flush=True)
    base_covs = []
    rich = bool(m.get("rich", False))
    # the model's own channel list wins: works for the old 5-channel and the new 8-channel model
    import readiness_model as _rm, model_search as _ms
    model_ch = list(m.get("channels", CH))
    _rm.CH[:] = model_ch
    _ms.CH[:] = model_ch
    global IDX
    IDX = [MONTAGE.index(c) for c in model_ch]
    print(f"# model channels {model_ch} -> stream slots {IDX}", flush=True)
    feat_cfg = m.get("feat_cfg")
    if feat_cfg:
        print(f"# processing: {feat_cfg['lo']:.0f} to {feat_cfg['hi']:.0f} Hz order {feat_cfg.get('order', 4)}{', 50 Hz notch' if feat_cfg.get('notch') else ''}{', common average reference' if feat_cfg.get('car') else ''}{', burst masking' if feat_cfg.get('burst') else ''}{', median Welch' if feat_cfg.get('median') else ''}{', no delta' if feat_cfg.get('drop_delta') else ''}{', no gamma' if feat_cfg.get('drop_gamma') else ''}{', polynomial detrend' if feat_cfg.get('detrend') else ''}", flush=True)
    asr = None
    from model_search import ASR, clean_window
    if feat_cfg and feat_cfg.get("asr"):
        asr = ASR(feat_cfg["asr"])
        print(f"# artefact subspace reconstruction: components over {feat_cfg['asr']:.0f}x their resting power are removed (calibrated on your baseline)", flush=True)
    asr_cal = []
    features = (lambda x, fs: features_rich(x, fs, True, feat_cfg, asr)) if rich else features_basic
    print(f"# model: {m.get('config', {}).get('model', 'logreg')}, {'rich' if rich else 'basic'} features, held-out AUC {m.get('loso_auc', 0):.2f}", flush=True)
    win = int(m["epoch_s"] * FS)
    buf = deque(maxlen=win)
    base_feats, base = [], None
    base_chan, chan_base, chan_now = [], None, None
    CH8 = MONTAGE
    ema, above_since, alarmed = None, None, False
    base_fat, fat_base, fat_ema, fatigue_pct, contact = [], 0.0, None, 0.0, False
    amp_hist = deque(maxlen=40)
    fat_start = 0.0
    fat_sd = 0.1
    rest_mean, rest_sd = 0.3, 0.2
    personal, calib_task = None, []
    replay_marks = []
    if a.replay:
        mpath = a.replay_markers or re.sub(r"_raw.*\.csv$", "_gauge_markers.csv", a.replay)
        if os.path.exists(mpath):
            for line in open(mpath).read().splitlines()[1:]:
                tm, c = line.split(",")[:2]
                replay_marks.append((float(tm), c.strip()))
            print(f"# replaying {len(replay_marks)} condition markers from {os.path.basename(mpath)}", flush=True)
    p_recent = deque(maxlen=5)
    fat_recent = deque(maxlen=5)
    clean_n = 0
    try:
        FAT_REF = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fatigue_ref.json")))["values"]
    except Exception:
        FAT_REF = []
    log = open(a.log, "w") if a.log else None
    if log:
        header_written = [False]
    markers = open(a.log.replace(".csv", "") + "_markers.csv", "w") if a.log else None
    if markers:
        markers.write("t,condition\n")
    cond = {"now": "none", "rebaseline": 0, "redo": False, "alpha_check": 0}
    # eyes-closed alpha check: 20 s eyes open, 20 s eyes closed; PASS when posterior alpha rises 3 dB to a peak of +3 dB or more
    ac = dict(active=False, t0=None, open=[], closed=[], result=None, said=set())
    alpha_now = None

    ui = None
    if not a.no_ui:
        import pygame
        pygame.init()
        screen = pygame.display.set_mode((1100, 640), pygame.RESIZABLE, vsync=1)
        pygame.display.set_caption("Mental load")
        font = pygame.font.SysFont("Avenir Next", 34)
        huge = pygame.font.SysFont("Avenir Next", 150, bold=True)
        small = pygame.font.SysFont("Menlo", 18)
        ui = dict(pygame=pygame, screen=screen, font=font, huge=huge, small=small, hist=deque(maxlen=600))

    def speak(txt):
        subprocess.Popen(["say", txt])

    state = "BASELINE: sit still, eyes open, 30 s"
    hist = deque(maxlen=600)
    import urllib.request

    def post_state(t_now):
        if not a.web:
            return
        chans = []
        if chan_now is not None:
            for i, n in enumerate(CH8):
                d = dict(name=n, dead=bool(chan_now["dead"][i]))
                if chan_base is not None and not d["dead"]:
                    d["db"] = round(10 * float(chan_now["tot"][i] - chan_base["tot"][i]), 1)       # change vs baseline, dB
                    d["theta_db"] = round(10 * float(chan_now["th"][i] - chan_base["th"][i]), 1)
                    d["alpha_db"] = round(10 * float(chan_now["al"][i] - chan_base["al"][i]), 1)
                else:
                    d["db"] = 0.0
                chans.append(d)
        # last 2 s of every channel, 1 to 40 Hz, 50 samples per second, for the live traces on the page
        sig = []
        try:
            Xs = np.array(buf)[-2 * FS:, :8].T
            Xs = sosfiltfilt(SIG_SOS, Xs - Xs.mean(1, keepdims=True), axis=1)[:, ::5]
            sig = [[int(v) for v in row] for row in Xs]
        except Exception:
            pass
        body = json.dumps(dict(t=round(t_now, 1), state=state, load=round(load_pct, 1), fatigue=round(fatigue_pct, 1), clean=int(clean_n), fatigue_held=bool(clean_n < 3 and not a.fake), load_held=bool(clean_n < a.load_min_clean and not a.fake), contact=bool(contact or not a.strict), alarm=bool(alarmed), alarm_at=a.alarm, hold_s=a.hold, alpha_now=None if alpha_now is None else round(alpha_now, 1),
                               alpha_check=dict(active=ac["active"], elapsed=None if (not ac["active"] or ac["t0"] is None) else round(t_now - ac["t0"]), result=ac["result"]), personal=personal is not None, calib=len(calib_task), calib_s=a.calib_s, replay=bool(a.replay), channels=chans, sig=sig,
                               baseline_done=base is not None, baseline_s=a.baseline,
                               baseline_progress=min(1.0, len(base_feats) / a.baseline) if base is None else 1.0,
                               hist=list(hist))).encode()
        try:
            r = urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{a.web_port}/state", data=body,
                                                              headers={"Content-Type": "application/json"}), timeout=0.3)
            reply = json.loads(r.read() or b"{}")
            new = reply.get("condition", cond["now"])
            if a.replay:
                # in a replay the recording's own markers are the truth; before the first one the condition is "none"
                due = [c for tm, c in replay_marks if tm <= t_now]
                want = due[-1] if due else "none"
                if want != new:
                    new = want
                    try:
                        urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{a.web_port}/event",
                                               data=json.dumps({"kind": "condition", "value": new, "t": t_now}).encode(),
                                               headers={"Content-Type": "application/json"}), timeout=0.3)
                    except Exception:
                        pass
            rb = int(reply.get("rebaseline", 0))
            if rb != cond["rebaseline"]:
                cond["rebaseline"] = rb
                cond["redo"] = True
            ac_n = int(reply.get("alpha_check", 0))
            if ac_n != cond["alpha_check"]:
                cond["alpha_check"] = ac_n
                ac.update(active=True, t0=None, open=[], closed=[], result=None, said=set())
            if new != cond["now"]:
                cond["now"] = new
                print(f"t={t_now:6.1f} CONDITION {new}", flush=True)
                if markers:
                    markers.write(f"{t_now:.1f},{new}\n"); markers.flush()
        except Exception as e:
            if cond.get("web_err") != repr(e)[:60]:
                cond["web_err"] = repr(e)[:60]
                print(f"# web page not reachable: {cond['web_err']}", flush=True)
    next_eval = 0.0
    load_pct = 0.0
    t = 0.0
    print(f"# {state}", flush=True)
    try:
        for t, x in (src_fake() if a.fake else src_replay(a.replay, a.speed) if a.replay else src_lsl()):
            if a.seconds and t > a.seconds:
                break
            buf.append(x)
            if ui is not None:
                for e in ui["pygame"].event.get():
                    if e.type == ui["pygame"].QUIT:
                        raise KeyboardInterrupt
                    if e.type == ui["pygame"].KEYDOWN:
                        if e.key == ui["pygame"].K_ESCAPE:
                            raise KeyboardInterrupt
                        if e.key == ui["pygame"].K_b:
                            base_feats, base, ema, alarmed, above_since = [], None, None, False, None
                            state = "BASELINE: sit still, eyes open, 30 s"
                            print("# re-baselining", flush=True)
            if len(buf) < win or t < next_eval:
                if ui is not None and t >= next_eval - 0.9:
                    pass
                continue
            next_eval = t + 1.0
            X8 = np.array(buf).T                      # (8, n)
            f = np.nan_to_num(features(X8[IDX], FS), nan=0.0, posinf=0.0, neginf=0.0)   # a flat channel gives log(0)
            if fmask is not None:
                f = f[fmask]
            # per-electrode activity: band power 1 to 40 Hz and theta/alpha, for the head map
            from scipy.signal import welch as _welch
            fr, pw = _welch(X8 - X8.mean(1, keepdims=True), fs=FS, nperseg=FS * 2, axis=1)
            tot = pw[:, (fr >= 1) & (fr < 40)].mean(1)
            th = pw[:, (fr >= 4) & (fr < 8)].mean(1)
            al = pw[:, (fr >= 8) & (fr < 13)].mean(1)
            be = pw[:, (fr >= 13) & (fr < 30)].mean(1)
            dead = X8.std(1) < 1e-6
            chan_now = dict(tot=np.log10(tot + 1e-12), th=np.log10(th + 1e-12), al=np.log10(al + 1e-12), dead=dead)
            # fatigue index: log10((theta + alpha) / beta) over the live model channels (Jap et al. 2009 ratio);
            # it drifts UP over minutes as someone tires. Not a trained model: a published ratio against the baseline.
            rail = np.abs(np.abs(X8.mean(1)) - 200000) < 1          # +/-200 mV = open input
            dead = dead | rail
            chan_now["dead"] = dead
            post = [MONTAGE.index(c) for c in POSTERIOR if c in MONTAGE and not dead[MONTAGE.index(c)]]
            if post:
                ah = alpha_height(X8[post])
                alpha_now = float(np.max(ah))
                if ac["active"]:
                    if ac["t0"] is None:
                        ac["t0"] = t
                        speak("Alpha check. Eyes open, look at one point.")
                        print(f"t={t:6.1f} ALPHA CHECK started: 20 s eyes open, then 20 s eyes closed", flush=True)
                    el = t - ac["t0"]
                    if 4 <= el < 20:
                        ac["open"].append(dict(zip([MONTAGE[i] for i in post], ah)))
                    elif el >= 20 and "close" not in ac["said"]:
                        ac["said"].add("close"); speak("Close your eyes.")
                    if 24 <= el < 40:
                        ac["closed"].append(dict(zip([MONTAGE[i] for i in post], ah)))
                    if el >= 40:
                        best = None
                        for ch in POSTERIOR:
                            o = [d[ch] for d in ac["open"] if ch in d]
                            c_ = [d[ch] for d in ac["closed"] if ch in d]
                            if len(o) >= 5 and len(c_) >= 5:
                                delta = float(np.median(c_) - np.median(o))
                                if best is None or delta > best[1]:
                                    best = (ch, delta, float(np.median(o)), float(np.median(c_)))
                        if best is None:
                            ac["result"] = dict(ok=False, text="not enough live posterior windows")
                        else:
                            # PASS rule from the 8 Nov null test: rise >= 3 dB AND eyes-closed peak >= +3 dB; pure noise on
                            # his 16 recordings passes this 0.9 percent of the time (a 2 dB rise alone: 15 to 20 percent)
                            ok = best[1] >= 3.0 and best[3] >= 3.0
                            ac["result"] = dict(ok=ok, ch=best[0], delta=round(best[1], 1), open_db=round(best[2], 1), closed_db=round(best[3], 1),
                                                text=f"{'PASS' if ok else 'FAIL'}: alpha at {best[0]} {best[2]:+.1f} dB eyes open, {best[3]:+.1f} dB eyes closed (rise {best[1]:+.1f}; pass needs +3 and +3)")
                        ac["active"] = False
                        print(f"t={t:6.1f} ALPHA CHECK {ac['result']['text']}", flush=True)
                        speak("Open your eyes. " + ("Brain signal confirmed." if ac["result"]["ok"] else "No alpha change. Fix the contact."))
            live = [i for i in IDX if not dead[i]] or list(IDX)
            live_n = int(sum(not dead[i] for i in IDX))
            contact = live_n >= 6 or a.fake
            # signal quality: 1 to 40 Hz RMS per channel; dry electrodes on hair give hundreds to thousands of uV of
            # artefact, and the fatigue ratio reads artefact as theta. Fatigue uses clean channels only, else holds.
            # quality is judged on what survives the chain (detrend, notch, reference, band-pass, burst mask, ASR):
            # that is the signal the model and the fatigue ratio actually see
            Xc = X8[IDX]
            if feat_cfg:
                Xc = clean_window(Xc, FS, feat_cfg)
                if asr is not None and asr.V is not None:
                    Xc = asr(Xc)
            else:
                Xc = sosfiltfilt(SIG_SOS, Xc - Xc.mean(1, keepdims=True), axis=1)
            rms_c = Xc.std(1)
            clean = [i for k, i in enumerate(IDX) if (not dead[i]) and rms_c[k] < a.quality_uv]
            clean_n = len(clean)
            # fatigue ratio from Hilbert band envelopes: band-pass theta, alpha, beta, take the analytic-signal envelope,
            # and use its MEDIAN over the window as the band amplitude (a burst cannot set it); median over clean channels
            if clean_n >= 3 or a.fake:
                from scipy.signal import hilbert as _hilbert
                idxs = clean if clean_n >= 3 else live
                # the fatigue ratio runs on the SAME cleaned window as the model (detrend, notch, reference, band-pass,
                # burst mask, artefact subspace reconstruction), so drift and hum cannot ramp it
                rowsel = [IDX.index(i) for i in idxs]
                env = []
                for sos_b in (FAT_SOS_TH, FAT_SOS_AL, FAT_SOS_BE):
                    xb = sosfiltfilt(sos_b, Xc[rowsel], axis=1)
                    env.append(np.median(np.abs(_hilbert(xb, axis=1))[:, FS // 2:-FS // 2], axis=1))     # drop the filter edges
                fat_now = float(np.median(np.log10((env[0] ** 2 + env[1] ** 2) / (env[2] ** 2 + 1e-12) + 1e-12)))
            else:
                fat_now = None
            # amplitude of the live channels, 1 to 40 Hz, for the settle check (dry electrodes drift for a minute or two)
            amp_hist.append(float(np.median(np.sqrt(tot[live]))) if len(live) else 0.0)
            if cond.get("redo"):
                cond["redo"] = False
                base, chan_base, fat_ema, fatigue_pct, alarmed, above_since, ema = None, None, None, 0.0, False, None, None
                base_feats.clear(); base_chan.clear(); base_fat.clear(); base_covs.clear(); amp_hist.clear(); asr_cal.clear(); p_recent.clear()
                personal = None; calib_task.clear()
                if asr is not None:
                    asr.V = None
                print(f"t={t:6.1f} REBASELINE requested from the page", flush=True)
                speak("New baseline")
            if base is None:
                # do not start the baseline until the electrodes are really on the head: a channel pinned at the
                # +/-200 mV rail (open input) or perfectly flat is dead. Need at least 6 of the model's channels live.
                if not contact and a.strict:
                    amp_hist.clear()
                    base_feats.clear(); base_chan.clear(); base_fat.clear()
                    names = [MONTAGE[i] for i in IDX if dead[i] or rail[i]]
                    state = f"WAITING FOR CONTACT: {live_n}/8 live, dead {' '.join(names)}"
                    if int(t) % 5 == 0:
                        print(f"# {state}", flush=True)
                    post_state(t)
                    continue
                # settle check: the median amplitude over the last 10 s must be within 25 percent of the 10 s before,
                # else the baseline would capture the drift and everything after reads as "load"
                if a.strict and not a.fake and not base_feats:
                    if len(amp_hist) < 20 or len(list(amp_hist)) < 20 or amp_hist[-1] <= 0 or abs(np.median(list(amp_hist)[-10:]) / (np.median(list(amp_hist)[-20:-10]) + 1e-9) - 1) > 0.25:
                        state = f"SETTLING: {live_n}/8 live, signal still drifting ({amp_hist[-1]:.0f} uV); hold still"
                        if int(t) % 5 == 0:
                            print(f"# {state}", flush=True)
                        post_state(t)
                        continue
                base_feats.append(f)
                if asr is not None:
                    asr_cal.append(X8[IDX].copy())
                if riem is not None:
                    base_covs.append(riem.covs(X8[IDX]))
                base_chan.append(chan_now)
                if fat_now is not None:
                    base_fat.append(fat_now)
                if len(base_feats) * 1.0 >= a.baseline:
                    if asr is not None and asr_cal:
                        asr.fit([clean_window(w, FS, feat_cfg) for w in asr_cal])
                        base_feats[:] = [np.nan_to_num(features(w, FS), nan=0.0, posinf=0.0, neginf=0.0)[fmask] if fmask is not None
                                         else np.nan_to_num(features(w, FS), nan=0.0, posinf=0.0, neginf=0.0) for w in asr_cal]
                    base = np.mean(base_feats, axis=0)
                    # rest calibration: what the model says about THIS person's resting signal (mean and spread of p);
                    # the gauge reads how far above that rest the current output is, so sitting still reads low by construction
                    try:
                        pr = clf.predict_proba(np.array(base_feats) - base)[:, 1]
                        rest_mean, rest_sd = float(np.mean(pr)), max(float(np.std(pr)), 0.10)
                    except Exception:
                        rest_mean, rest_sd = 0.3, 0.2
                    print(f"# rest calibration: model output on your rest = {rest_mean:.2f} +/- {rest_sd:.2f}; load = {a.gain:.0f} x (p - rest) / sd, 0 at rest", flush=True)
                    if riem is not None:
                        riem.set_baseline(base_covs)
                    chan_base = {k: np.mean([c[k] for c in base_chan], axis=0) for k in ("tot", "th", "al")}
                    fat_sd = max(float(np.std(base_fat)), 0.05) if len(base_fat) >= 3 else 0.1
                    if len(base_fat) >= 5 and FAT_REF:
                        fat_base = float(np.median(base_fat))
                        # the percentile among 36 lab-cap subjects does NOT transfer to a dry cap (a dry resting ratio sits
                        # above all of them), so it is printed for information only; the scale starts at 50 = "your start"
                        # and moves with this session, scored against the spread of your own baseline
                        pct = 100.0 * float(np.mean(np.array(FAT_REF) < fat_base))
                        fat_start = 50.0
                        print(f"# fatigue: start 50 (your own start); baseline ratio {fat_base:.2f} +/- {fat_sd:.2f} from {len(base_fat)} clean windows (lab-cap percentile {pct:.0f}, not used)", flush=True)
                    else:
                        fat_base, fat_start = (float(np.median(base_fat)) if base_fat else float(np.mean(FAT_REF)) if FAT_REF else 1.2), 50.0
                        print(f"# fatigue start unknown (only {len(base_fat)} clean baseline windows under {a.quality_uv:.0f} uV): starting at 50", flush=True)
                    state = "monitoring"
                    print("# baseline done", flush=True)
                    speak("Baseline done")
                load_pct = 0.0
                post_state(t)
            elif not contact and a.strict:
                # contact lost after the baseline: hold the last numbers, say so, do not feed rail data to the model
                names = [MONTAGE[i] for i in IDX if dead[i]]
                state = f"CONTACT LOST: {live_n}/8 live, dead {' '.join(names)}"
                if int(t) % 5 == 0:
                    print(f"# {state}", flush=True)
                if log and header_written[0]:
                    log.write(f"{t:.1f},{load_pct:.1f},{fatigue_pct:.1f},{int(alarmed)},{cond['now']},0," + ",".join("nan" for _ in f) + "\n")
                hist.append(round(load_pct, 1))
                post_state(t)
            elif clean_n < a.load_min_clean and not a.fake:
                # too few channels survive the cleaning chain: the model would be reading noise. Hold the load, say so.
                state = f"NOISY: {clean_n}/8 clean, load held"
                if int(t) % 5 == 0:
                    print(f"# {state}", flush=True)
                if log and header_written[0]:
                    log.write(f"{t:.1f},{load_pct:.1f},{fatigue_pct:.1f},{int(alarmed)},{cond['now']},1," + ",".join("nan" for _ in f) + "\n")
                hist.append(round(load_pct, 1))
                post_state(t)
            else:
                state = "monitoring"
                xf = (f - base)[None, :]
                if personal is None and a.calib_s > 0 and cond["now"] == "mental":
                    calib_task.append(xf[0])
                    state = f"CALIBRATING: {len(calib_task)}/{a.calib_s} s of mental"
                    if len(calib_task) >= a.calib_s:
                        # personal model: his own 30 s rest (baseline) versus his own first minute of Zetamac;
                        # shrinkage LDA on the same cleaned, amplitude-invariant features (tested on tonight's sessions:
                        # 0.98 within a session, 0.67 to 0.69 across sessions; the generic model gave none on him)
                        from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
                        from sklearn.pipeline import make_pipeline
                        from sklearn.preprocessing import StandardScaler
                        X0 = np.array(base_feats) - base
                        X1 = np.array(calib_task)
                        personal = make_pipeline(StandardScaler(), LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto"))
                        personal.fit(np.vstack([X0, X1]), [0] * len(X0) + [1] * len(X1))
                        ema = None
                        p_recent.clear()
                        print(f"t={t:6.1f} PERSONAL MODEL trained on {len(X0)} s rest + {len(X1)} s mental; load now = 100 x its probability", flush=True)
                        speak("Calibrated")
                if personal is not None:
                    p = float(personal.predict_proba(xf)[0, 1])
                else:
                    p = float(clf.predict_proba(xf)[0, 1])
                if riem is not None:
                    pr = float(riem_clf.predict_proba(riem.features(riem.covs(X8[IDX]))[None, :])[0, 1])
                    p = 0.5 * (p + pr)
                p_recent.append(p)
                p_med = float(np.median(p_recent))      # median of the last 5 outputs: a one-second glitch cannot move the gauge
                ema = (0.2 if personal is None else 0.1) if ema is None else ema   # start calm, let the evidence raise it
                ema = ema + (p_med - ema) * (1.0 / a.smooth)
                if personal is not None:
                    load_pct = float(np.clip(100 * ema, 0, 100))      # personal model: its probability is already his own scale
                else:
                    load_pct = float(np.clip(a.gain * (ema - rest_mean) / rest_sd, 0, 100))   # 0 at his own rest; --gain points per spread above it
                # fatigue: slow EMA (about 2 min) of the ratio drift, starting AT the baseline; +0.5 log10 (ratio x3) reads as 100
                if fat_now is not None:
                    fat_recent.append(fat_now)
                    fat_robust = float(np.median(fat_recent))        # median of the last clean windows: one bad window cannot move it
                    fat_ema = fat_base if fat_ema is None else fat_ema + (fat_robust - fat_ema) / 180.0
                elif fat_ema is None:
                    fat_ema = fat_base
                # percentile start, then drift scored against his own baseline spread: +10 points per spread above rest,
                # capped at 25 points per doubling of the ratio so a noisy baseline cannot make it hypersensitive
                z = (fat_ema - fat_base) / fat_sd
                fatigue_pct = float(np.clip(fat_start + min(10 * z, (fat_ema - fat_base) / 0.301 * 25) if z > 0 else fat_start + 10 * z, 0, 100))
                if load_pct >= a.alarm:
                    above_since = above_since or t
                    if not alarmed and t - above_since >= a.hold:
                        alarmed = True
                        print(f"t={t:6.1f} ALARM load {load_pct:.0f}", flush=True)
                        speak("High mental load. Take a break.")
                else:
                    above_since, alarmed = None, False
                if log:
                    if not header_written[0]:
                        log.write("t,load_pct,fatigue_pct,alarm,condition,contact," + ",".join(f"f{i}" for i in range(len(f))) + "\n")
                        header_written[0] = True
                    log.write(f"{t:.1f},{load_pct:.1f},{fatigue_pct:.1f},{int(alarmed)},{cond['now']},1," + ",".join(f"{v:.3f}" for v in f) + "\n")
                    log.flush()
                hist.append(round(load_pct, 1))
                post_state(t)
                if a.no_ui or int(t) % 5 == 0:
                    print(f"t={t:6.1f} load {load_pct:5.1f}  raw p {p:.2f}  {'ALARM' if alarmed else ''}", flush=True)
            if ui is not None:
                pg, sc = ui["pygame"], ui["screen"]
                ui["hist"].append(load_pct)
                w, h = sc.get_size()
                sc.fill((110, 20, 20) if alarmed else (12, 12, 16))
                title = ui["font"].render(state, True, (200, 200, 200))
                sc.blit(title, (40, 30))
                if base is not None:
                    col = (240, 80, 80) if load_pct >= a.alarm else ((250, 180, 60) if load_pct >= a.alarm - 20 else (80, 200, 120))
                    num = ui["huge"].render(f"{load_pct:.0f}", True, col)
                    sc.blit(num, num.get_rect(center=(w // 2, h // 2 - 60)))
                    lbl = ui["font"].render("mental load, 0 to 100, relative to your own baseline", True, (150, 150, 150))
                    sc.blit(lbl, lbl.get_rect(center=(w // 2, h // 2 + 50)))
                    pg.draw.rect(sc, (40, 40, 48), (40, h - 140, w - 80, 90), border_radius=8)
                    pts = [(40 + i * (w - 80) / 600, h - 50 - v * 0.9) for i, v in enumerate(ui["hist"])]
                    if len(pts) > 1:
                        pg.draw.lines(sc, (200, 200, 200), False, pts, 2)
                    ya = h - 50 - a.alarm * 0.9
                    pg.draw.line(sc, (240, 80, 80), (40, ya), (w - 40, ya), 1)
                    if alarmed:
                        al = ui["font"].render("HIGH LOAD: take a break", True, (255, 255, 255))
                        sc.blit(al, al.get_rect(center=(w // 2, h // 2 + 100)))
                else:
                    done = min(len(base_feats), a.baseline)
                    pg.draw.rect(sc, (60, 60, 70), (w // 2 - 250, h // 2, 500, 30), border_radius=8)
                    pg.draw.rect(sc, (80, 200, 120), (w // 2 - 250, h // 2, int(500 * done / a.baseline), 30), border_radius=8)
                foot = ui["small"].render("B = redo baseline   Esc = quit", True, (110, 110, 110))
                sc.blit(foot, (40, h - 28))
                pg.display.flip()
    except KeyboardInterrupt:
        pass
    finally:
        if log:
            log.close()
        if markers:
            markers.close()
        if ui is not None:
            ui["pygame"].quit()
        print(f"# stopped at t={t:.0f} s, last load {load_pct:.0f}")


if __name__ == "__main__":
    main()
