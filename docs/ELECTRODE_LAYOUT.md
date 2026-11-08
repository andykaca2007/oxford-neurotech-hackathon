# Electrode layout: use all 8 electrodes in the load model

Written Sat 7 Nov 2026 by Andy (with Claude), for Paing and Paing's Claude.
Branch `andy/electrode-layout`, based on `paing/readiness`. This file proposes changes; no code has changed yet.

## The problem in one paragraph

The load model (`loadmonitor/readiness_model.py`) can only use electrode positions that exist in its
training data, PhysioNet eegmat (Zyma et al. 2019). Our BCI Core-8 montage is
**Fz C3 Cz C4 Pz PO7 POz PO8**. PO7, POz and PO8 are not eegmat positions, so the model uses only
`CH = ["Fz", "C3", "Cz", "C4", "Pz"]` and **3 of our 8 electrodes are unused**. We can physically move
electrodes on the cap, so we should move those three onto positions that eegmat has.

## eegmat positions (the only ones the model can use)

Standard 10-20, 19 EEG channels:

`Fp1 Fp2 F7 F3 Fz F4 F8 T3 C3 Cz C4 T4 T5 P3 Pz P4 T6 O1 O2`

(T3/T4/T5/T6 are the old names for T7/T8/P7/P8.) **Check this first**: print the EDF labels of one
file (`pyedflib.EdfReader(...).getSignalLabels()`, stripping the `"EEG "` prefix as `load_edf` does)
and confirm P3, P4, O1, F3, F4 are present.

## Why these positions

- During mental arithmetic, **frontal midline theta rises** (Fz; F3 and F4 nearby).
- **Alpha falls**, most strongly at the back of the head (Pz, P3, P4, O1, O2).
- C3 and C4 sit over the motor strip and are less tied to doing sums.
- Avoid Fp1/Fp2 (blinks and eye movements) and T3/T4/F7/F8 (jaw and talking muscle).

## Proposed layouts

| Layout | 8 channels | Change on the cap |
|---|---|---|
| Now (5 used) | Fz C3 Cz C4 Pz | none |
| **A (do first)** | Fz C3 Cz C4 Pz **P3 P4 O1** | move PO7 to P3, PO8 to P4, POz to O1 |
| B | Fz **F3 F4** Cz Pz P3 P4 O1 | layout A, plus move C3 to F3 and C4 to F4 |

Layout A only moves the three unused electrodes, and all three moves are short. Check each lead reaches
before committing. The reference and ground stay on the mastoid stickers: eegmat used linked ears,
which is close enough.

**Optional muscle sentinel:** an electrode at T3 is a good detector for talking or jaw clenching. Use it
only to flag "reading unreliable" on the page, never as a model input.

## What to change in the code

1. **`loadmonitor/readiness_model.py`**
   - Make `CH` selectable, e.g. `--channels Fz,C3,Cz,C4,Pz,P3,P4,O1`. `features()` already works for any
     channel count; the two ratio features use Fz and Pz by name, so keep both in every layout.
   - Run leave-one-subject-out for the three layouts in the table (now, A, B) and print all three.
   - **Avoid a flattering result.** Choosing the best of three layouts on the same LOSO scores is slightly
     optimistic. Either say so on the slide, or pick the layout on subjects 1 to 18 and report the score
     on subjects 19 to 36.
   - Save the chosen channel list in `models/readiness.joblib` (it already stores `channels=CH`).
2. **`loadmonitor/load_gauge.py`**
   - `IDX = [0, 1, 2, 3, 4]` is hard-coded and `CH8` (line ~97) lists the old montage. Replace both with
     one montage list that says what is physically in each of the 8 stream slots after the move, for
     layout A `["Fz", "C3", "Cz", "C4", "Pz", "P3", "O1", "P4"]` (slot 6 was PO7, slot 7 was POz, slot 8
     was PO8). Build `IDX` from the model's saved `channels`, so the gauge and the model can never disagree.
   - Best: put that montage list in one shared place (e.g. `headset/montage.py`) and import it in the
     gauge, the bridge and anything else that names channels.
3. **`loadmonitor/web/index.html`**
   - `POS` (line ~134) and `SIGN` (line ~195) hard-code the old names. Add the new positions to `POS`,
     and take the channel names from the `/state` channels list rather than a fixed array.
   - Suggested head-map coordinates in the existing 200 x 220 viewBox (Fz [100,52], Cz [100,110] and
     Pz [100,158] are already there): P3 [62,152], P4 [138,152], O1 [80,196], O2 [120,196],
     F3 [62,64], F4 [138,64].
4. **`headset/unicorn_gpype.py`** and the electrode check: update the montage comments and labels so
   nobody reads slot 6 as PO7 after it has moved.
5. **Results and docs.** Retrain, then update `docs/RESULTS.md` and the results table in `docs/PLAN.md`
   (currently 5 channels: 70% balanced accuracy, AUC 0.79 relative to baseline). The slide line we
   want: "moving 3 electrodes took held-out accuracy from 70% to X%". Report it honestly if X is not
   higher.
6. **Check before pushing** (CONTRIBUTING): `pytest tests`, and the gauge in fake mode
   (`load_gauge.py --fake --web`) with the page open, to confirm the head map shows the new names.

## Related notes on validity

- Saying answers out loud puts jaw and speech muscle noise into the beta band (13 to 30 Hz), which is a
  model feature. Typed answers (the Zetamac setup) avoid most of this. If anyone talks during the demo,
  the T3 sentinel above, or a "count 1, 2, 3 out loud" control showing the gauge stays low, answers the
  question before a judge asks it.
- Theta up with alpha down is the workload signature. Drowsiness and fatigue usually push alpha up, so
  call the output "load", not "fatigue".
- The model separates rest from mental arithmetic. It has not been shown to grade medium vs high load,
  so the 0 to 100 number is the model's confidence that the person is working, and the alarm threshold
  is a design choice.
