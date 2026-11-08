# Model optimisation, scored honestly

Layout A channels (Fz C3 Cz C4 Pz P3 P4 O1), 4 s windows, 50 percent overlap, baseline-relative. 36 subjects of PhysioNet eegmat. STRICT = the candidate is chosen on subjects 0 to 17 and reported on 18 to 35; that is the number to quote. LOSO36 is leave-one-subject-out over everyone (slightly optimistic for tuned rows). '8 s vote' averages two consecutive windows, which is what the live gauge's smoothing does.

| candidate | choose-half AUC | held-out half acc | held-out half AUC | LOSO36 acc | LOSO36 AUC | 8 s vote AUC |
|---|---|---|---|---|---|---|
| stack(bp-gb,riem-fb) | 0.821 | 0.741 +/- 0.131 | 0.867 | 0.754 | 0.871 | 0.896 |
| riem-fb | 0.698 | 0.725 +/- 0.137 | 0.837 | 0.720 | 0.808 | 0.829 |
| bp-gb | 0.779 | 0.735 +/- 0.110 | 0.836 | 0.747 | 0.841 | 0.873 |

**STRICT pick:** stack(bp-gb,riem-fb): held-out balanced accuracy 0.741, AUC 0.867 (current bp-gb on the same half: 0.735, 0.836).

What does not change: students doing arithmetic is not surgeons on shift; the model says 'looks like effort', not 'unsafe'.

## Amplitude-invariant model (what runs live from 7 Nov 23:00)

The dry Unicorn on hair gives 1 to 40 Hz amplitudes of 300 to 4000 uV that change 5x between windows; the lab data the model learned from changes 1 to 3 dB. Any feature that carries absolute power therefore reads contact quality, not brain, and the gauge only ever rises. Test: random per-window gain of 0.3x to 3x applied to the held-out subject.

| features | LOSO AUC (clean) | LOSO AUC with 0.3x to 3x gain swings |
|---|---|---|
| all 109 (log band powers + relative + ratios + entropy + gradient + blink) | 0.841 | 0.719 |
| 60 amplitude-invariant (relative powers, ratios, entropy, Fz-Pz theta gradient) | 0.807 | 0.807 |

(Superseded, see the end of this file.) Gradient boosting on the 60 invariant features (`--fit-best --invariant`, 8 channels). Costs 0.034 AUC on clean data, immune to a gain change shared by all channels (NOT to a gain change on one electrode: with independent per-channel gains of 0.3x to 3x the LOSO AUC falls from 0.762 to 0.658, because the median reference mixes channels and the Fz minus Pz theta gradient compares absolute power across channels; CRITIQUE model-2). The stack (0.867 strict AUC) is parked in models/readiness_stack.joblib; it also uses absolute power and has the same weakness on this headset.

## Final live processing (8 Nov 00:30): robust chain

Common average reference (dead channels excluded), 50 Hz notch, 3 to 30 Hz order-6 band-pass, Hilbert-envelope burst masking (samples over 4x the window median blanked), median-averaged Welch over 1 s segments, bands theta/alpha/low beta/high beta only, 44 amplitude-invariant features, gradient boosting. Load shown = 15 + 20 z against the wearer's own rest (model output mean and spread measured during the baseline).

| model | LOSO AUC (clean lab data) | wearer's recordings, idle: median load / share above 70 |
|---|---|---|
| all features, 1 to 40 Hz (first version) | 0.841 | 89 / 0.85 |
| invariant, 1 to 40 Hz | 0.807 | 59 / 0.39 (no rest calibration) |
| invariant + notch + 3 Hz HP + no delta | 0.811 | 59 / 0.22 |
| robust chain above, rest-calibrated (LIVE) | 0.763 | 23 and 17 / 0.00 |

Trade: 0.08 AUC on clean data for a gauge that sits low at rest on a dry headset with heavy mains and drift. The fatigue ratio uses Hilbert band envelopes (median over time, median over channels under 300 uV) with the 36-subject rested reference computed the same way.


## Live model and how to rebuild it exactly (8 Nov)

5 channels (Fz C3 Cz Pz O1), robust chain (detrend, notch comb, median reference, 4 to 30 Hz order 8, burst mask with protected edges, ASR, median Welch), 29 amplitude-invariant features (invariant to a common gain only, see the note above), gradient boosting. LOSO AUC 0.760, balanced accuracy 0.679 (lab only). Rebuild, about 5 minutes:

```
.venv/bin/python loadmonitor/model_search.py --fit-best --robust --invariant --channels Fz,C3,Cz,Pz,O1 --out models/readiness.joblib
```

Without `--out` it writes models/readiness_candidate.joblib and leaves the live model alone. The command is stored in the joblib under `rebuild`. Checked 8 Nov: a rebuild with this command matches the live model exactly (max probability difference 0 over all 2,083 lab windows).
