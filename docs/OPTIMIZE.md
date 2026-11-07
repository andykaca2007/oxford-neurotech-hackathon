# Model optimisation, scored honestly

Layout A channels (Fz C3 Cz C4 Pz P3 P4 O1), 4 s windows, 50 percent overlap, baseline-relative. 36 subjects of PhysioNet eegmat. STRICT = the candidate is chosen on subjects 0 to 17 and reported on 18 to 35; that is the number to quote. LOSO36 is leave-one-subject-out over everyone (slightly optimistic for tuned rows). '8 s vote' averages two consecutive windows, which is what the live gauge's smoothing does.

| candidate | choose-half AUC | held-out half acc | held-out half AUC | LOSO36 acc | LOSO36 AUC | 8 s vote AUC |
|---|---|---|---|---|---|---|
| stack(bp-gb,riem-fb) | 0.821 | 0.741 +/- 0.131 | 0.867 | 0.754 | 0.871 | 0.896 |
| riem-fb | 0.698 | 0.725 +/- 0.137 | 0.837 | 0.720 | 0.808 | 0.829 |
| bp-gb | 0.779 | 0.735 +/- 0.110 | 0.836 | 0.747 | 0.841 | 0.873 |

**STRICT pick:** stack(bp-gb,riem-fb): held-out balanced accuracy 0.741, AUC 0.867 (current bp-gb on the same half: 0.735, 0.836).

What does not change: students doing arithmetic is not surgeons on shift; the model says 'looks like effort', not 'unsafe'.
