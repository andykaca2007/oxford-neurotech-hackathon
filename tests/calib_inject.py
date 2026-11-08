"""Calibrate with a known injected effect, under the live channel gate (CRITIQUE calib-adv2, 8 Nov).

    .venv/bin/python tests/calib_inject.py            # about 2 minutes

His recordings of 200 s or more; ASR fitted on the first 30 windows; a window enters calibration only when all 5 model
channels are connected and at least 2 are clean (the gauge holds otherwise, 0c25f19). Task blocks get a fixed shift of
d feature SDs along one random direction (d = 0 is the null). Compares the live rule with stricter variants.
Starts every 10 s overlap (about 12 independent 160 s runs in total); read the shares as relative, not as rates.
Adapted from the critic's script (/tmp/adv6/lopo.py); its base features now drop infinities as the gauge does.
"""
import sys, os, glob, numpy as np, warnings
warnings.filterwarnings("ignore")
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, R + "/loadmonitor"); sys.path.insert(0, R + "/headset")
import joblib, model_search as ms, readiness_model as rm
from model_search import clean_window, ASR, feats
from montage import MONTAGE
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis as LDA
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
m = joblib.load(R + "/models/readiness.joblib"); cfg = m["feat_cfg"]; fmask = m["feature_mask"]
ms.CH[:] = m["channels"]; rm.CH[:] = m["channels"]
IDX = [MONTAGE.index(c) for c in m["channels"]]; FS = 250
def load(p):
    rows = []
    for line in open(p):
        if line.startswith("#"): continue
        try: rows.append([float(v) for v in line.split(",")[1:9]])
        except ValueError: continue
    return np.array(rows).T
recs = []
for p in sorted(glob.glob(R + "/recordings/paing_2026110[78]_*raw*.csv")):
    X = load(p); n = X.shape[1]
    if n < 200 * FS: continue
    ends = np.arange(4 * FS, n, FS); asr = ASR(cfg["asr"]); cal = []; F = []; OK = []
    for k, e in enumerate(ends):
        W = X[:, e - 4 * FS:e]; dead = (W.std(1) < 1e-6) | (np.abs(np.abs(W.mean(1)) - 200000) < 1)
        if k < 30:
            cal.append(W[IDX].copy())
            if k == 29:
                asr.fit([clean_window(w, FS, cfg) for w in cal])
                base = np.mean([np.nan_to_num(feats(w, FS, True, cfg, asr), nan=0, posinf=0, neginf=0)[fmask] for w in cal], 0)
            continue
        rms = asr(clean_window(W[IDX], FS, cfg)).std(1)
        live5 = all(not dead[i] for i in IDX); nclean = sum((not dead[i]) and 0.5 < rms[j] < 100 for j, i in enumerate(IDX))
        OK.append((live5 and nclean >= 2, live5 and nclean == len(IDX)))
        F.append(np.nan_to_num(feats(W[IDX], FS, True, cfg, asr), nan=0, posinf=0, neginf=0)[fmask] - base)
    recs.append((os.path.basename(p)[:22], np.array(F), np.array(OK)))
mk = lambda: make_pipeline(StandardScaler(), LDA(solver="lsqr", shrinkage="auto"))
rng = np.random.default_rng(0)
allF = np.vstack([r[1] for r in recs]); sd = allF.std(0) + 1e-9
u = rng.normal(size=allF.shape[1]); u /= np.linalg.norm(u)
def run(F, OK, s, gate, minw, shift):
    blocks = {}
    for b in range(8):
        for o in range(5, 20):
            k = s + b * 20 + o
            if OK[k][gate]:
                v = F[k].copy()
                if shift is not None and b % 2: v = v + shift
                blocks.setdefault(b, []).append(v)
    aucs = []
    for hp in range(4):
        tr = [b for b in range(8) if b // 2 != hp and b in blocks]; te = [b for b in (2*hp, 2*hp+1) if b in blocks]
        if len(te) < 2 or min(len(blocks[b]) for b in te) < minw or len({b % 2 for b in tr}) < 2: continue
        Xtr = np.vstack([blocks[b] for b in tr]); ytr = np.concatenate([[b % 2]*len(blocks[b]) for b in tr])
        Xte = np.vstack([blocks[b] for b in te]); yte = np.concatenate([[b % 2]*len(blocks[b]) for b in te])
        aucs.append(roc_auc_score(yte, mk().fit(Xtr, ytr).predict_proba(Xte)[:, 1]))
    if minw and len(aucs) < 4: return "untestable"
    return np.mean(aucs) if aucs else "untestable"
print("recordings:", [(n, len(F), int(sum(o[0] for o in OK)), int(sum(o[1] for o in OK))) for n, F, OK in recs])
RULES = {"live (5 connected, 2 of 5 clean, any folds)": (0, 0), "live gate + 4 folds, >=5 windows per held-out block": (0, 5), "5 of 5 clean + 4 folds, >=5 windows": (1, 5)}
for d in (0.0, 0.5, 1.0):
    for name, (gate, minw) in RULES.items():
        res = []
        for n, F, OK in recs:
            for s in range(0, len(F) - 160, 10):
                res.append(run(F, OK, s, gate, minw, None if d == 0 else d * u * sd))
        a = np.array([r for r in res if not isinstance(r, str)]); nu = sum(isinstance(r, str) for r in res)
        print(f"effect {d:.1f} SD | {name:62s} | starts {len(res)} testable {len(a)} untestable {nu} | pass>=0.80 {np.sum(a>=0.8)} ({100*np.mean(a>=0.8) if len(a) else float('nan'):.1f}% of testable)")
