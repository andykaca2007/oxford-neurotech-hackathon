"""Score a SwallowCue session: the numbers for the judges' slide.

    python3 tools/eval_session.py session.csv [more.csv ...] [--period 15]

Works on logs from live_emg/swallowcue_live.py (--log) and from
tools/live_plot.py --log (the throat-IMU board). Lines used:
    B,centre,dur,peak,gyro,gap_before,gap_after,SWALLOW|other   a detected burst
    M,t    you pressed Enter right after swallowing (ground truth)
    T,t    true swallow time (fake sessions only)
    C,t    the wristband buzzed
    S,t,...  live samples (only used for the session length)

A detection counts as a hit if its centre is within MARK_BEFORE s before
or MARK_AFTER s after a mark (you press Enter just after you swallow).
Every SWALLOW detection that matches no mark is a false count.

Reports, per file and in total:
    swallows marked, caught, missed, sensitivity
    false counts and false counts per minute
    buzzes given vs a fixed schedule with the same period (--period, default 15 s,
    use the T you ran with). The fair comparison: same spacing, but SwallowCue
    stays silent while the person keeps swallowing.
"""
import sys

MARK_BEFORE = 2.5   # detection may come up to 2.5 s before the Enter press
MARK_AFTER = 1.0    # or up to 1 s after it
TRUTH_TOL = 0.6     # for T lines (exact centres from the fake generator)
FIXED_PERIOD_S = 15.0


def read(path):
    det, marks, truth, cues, times = [], [], [], [], []
    with open(path) as f:
        for line in f:
            p = line.strip().split(",")
            try:
                if p[0] == "B" and len(p) >= 8:
                    if p[7] == "SWALLOW":
                        det.append(float(p[1]))
                    times.append(float(p[1]))
                elif p[0] == "M":
                    marks.append(float(p[1])); times.append(float(p[1]))
                elif p[0] == "T":
                    truth.append(float(p[1]))
                elif p[0] == "C":
                    cues.append(float(p[1])); times.append(float(p[1]))
                elif p[0] == "S":
                    times.append(float(p[1]))
            except ValueError:
                continue
    return det, marks, truth, cues, times


def match(det, ref, before, after):
    """Greedy one-to-one matching. Returns (hits, false_count)."""
    used = set()
    hits = 0
    for r in sorted(ref):
        best = None
        for i, d in enumerate(det):
            if i in used or not (r - before <= d <= r + after):
                continue
            if best is None or abs(d - r) < abs(det[best] - r):
                best = i
        if best is not None:
            used.add(best)
            hits += 1
    return hits, len(det) - len(used)


def score(path):
    det, marks, truth, cues, times = read(path)
    if truth:
        ref, before, after, kind = truth, TRUTH_TOL, TRUTH_TOL, "true (fake session)"
    else:
        ref, before, after, kind = marks, MARK_BEFORE, MARK_AFTER, "marked with Enter"
    hits, false = match(det, ref, before, after)
    minutes = (max(times) - min(times)) / 60 if len(times) > 1 else 0.0
    return dict(file=path, kind=kind, ref=len(ref), hits=hits, false=false,
                minutes=minutes, cues=len(cues))


def show(r, title):
    sens = r["hits"] / r["ref"] if r["ref"] else float("nan")
    fpm = r["false"] / r["minutes"] if r["minutes"] else float("nan")
    fixed = int(r["minutes"] * 60 // FIXED_PERIOD_S)
    print(f"{title}")
    print(f"  swallows {r['kind']:<22} {r['ref']}")
    print(f"  caught                         {r['hits']}  ({sens:.0%})")
    print(f"  missed                         {r['ref'] - r['hits']}")
    print(f"  false counts                   {r['false']}  ({fpm:.2f} per minute)")
    print(f"  session length                 {r['minutes']:.1f} min")
    print(f"  buzzes: SwallowCue {r['cues']} vs fixed every {FIXED_PERIOD_S:g} s {fixed}")


def main():
    global FIXED_PERIOD_S
    args = sys.argv[1:]
    if "--period" in args:
        i = args.index("--period")
        FIXED_PERIOD_S = float(args[i + 1])
        del args[i:i + 2]
    if not args:
        sys.exit(__doc__)
    rows = [score(p) for p in args]
    for r in rows:
        show(r, r["file"])
    if len(rows) > 1:
        tot = dict(kind="(all files)", ref=sum(r["ref"] for r in rows), hits=sum(r["hits"] for r in rows),
                   false=sum(r["false"] for r in rows), minutes=sum(r["minutes"] for r in rows),
                   cues=sum(r["cues"] for r in rows))
        show(tot, f"TOTAL over {len(rows)} sessions")


if __name__ == "__main__":
    main()
