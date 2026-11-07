# Results so far (Sat 7 Nov 2026, 14:00)

## Public data: how much calibration does a personal SSVEP decoder need?

Dataset: Nakanishi et al. 2015, PLoS ONE 10(10):e0140703. 10 subjects, 12 targets
(9.25 to 14.75 Hz), 8 occipital channels, 256 Hz, 15 blocks. Credited and downloaded from
github.com/mnakanishi/12JFPM_SSVEP. Code: unicorn/trca.py, unicorn/calibration_curve.py
(written during the hackathon; TRCA from Nakanishi et al. 2018, IEEE TBME 65(1):104).

Protocol: for every subject, blocks 9 to 15 are held out and never touched by training.
TRCA (per-person spatial filters + templates) is trained on the first k blocks. CCA
(sine/cosine references, 2 harmonics) needs no training and is scored on the same held-out
blocks. Band-pass 6 to 40 Hz. Epoch starts 0.15 s after stimulus onset. Chance = 1/12 = 8%.
ITR = Wolpaw bits per selection x selections per minute, assuming window + 0.5 s per trial.

| window | CCA (0 s calib) | TRCA, 2 blocks | TRCA, 5 blocks | TRCA, 8 blocks |
|---|---|---|---|---|
| 0.5 s | 20% +/- 8 | 74% +/- 19 (12 s) | 83% +/- 13 (30 s) | see plot |
| 1.0 s | 53% +/- 22 | 89% +/- 15 (24 s) | 95% +/- 7 (60 s) | 96% +/- 5 (96 s) |
| 1.5 s | 73% +/- 22 | 93% +/- 13 (36 s) | 97% +/- 4 (90 s) | see plot |
| 2.0 s | 82% +/- 20 | 94% +/- 11 (48 s) | 99% +/- 3 (120 s) | 99% +/- 2 (192 s) |

ITR (bit/min): 1 s window, CCA 38 vs TRCA 107 (24 s calib) vs 124 (60 s). 0.5 s window, TRCA 140.
Plots: data/curve_12class_{0.5,1,1.5,2}s.png, data/curve_4class_2s.png (4 classes: CCA already 95%, ceiling).

Takeaways for the slide
- A generic decoder is near chance at 0.5 s; 12 s of personal calibration makes it 74%.
- Personalisation buys speed: at a fixed 90% target, TRCA needs about 1 s of EEG, CCA about 2.5 s.
- Gains saturate after about 60 s of calibration.

Limits (say them first)
- 10 healthy adults, lab EEG, 12 targets. Our live system has 4 targets and dry electrodes.
- Within-subject, held-out blocks from the same day. No cross-day test.
- No patients. The communication-aid use case is the motivation, not a result.

## Live headset (Unicorn BCI Core-8): pending
- Slot 1 (12:00 to 12:30): amplifier pogo row unseated, even channels open; no usable data.
- Next slot: scalp proof (occipital RMS under 40 uV, eyes-closed alpha ratio over 2), then
  48 s calibration (12 cues x 4 s), then 12 held-out cues decoded live with TRCA and CCA.
