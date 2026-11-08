# The 3-minute slot: 90 s talk, 90 s video

Five slides from `figures/slides/best8/`, then the recorded demo. The script is about 165 words, which is 90 seconds
at a calm pace. Read it twice against a stopwatch.

| Slide | Time | Say |
|---|---|---|
| 0 Problem | 0:00 | "Surgeons, pilots and shift workers overload quietly, and the mistakes come after. There is no gauge for it. EEG carries the signal: under mental work, alpha at the back of the head falls and theta at the front rises. The hard part is the hardware: a dry headset on hair gives six thousand microvolts of noise around thirty of brain." |
| 2 Filters | 0:25 | "Four seconds from our own cap. Six stages, detrend to artefact subspace reconstruction, take it from six thousand microvolts to thirty-four, which is scalp EEG. The fifty hertz hum goes; the brain bands stay." |
| 4 ROC | 0:45 | "A gradient boosting model, trained on thirty-six people and tested one held-out person at a time: pooled AUROC zero point seven four, median zero point eight one. It works well for twenty-three of thirty-six." |
| 7 Limits | 1:05 | "What works: the pipeline, end to end, on real EEG. What does not yet: clean contact on our dry cap; four of eight electrodes rarely connected, and the system said so rather than inventing a number. Next: gel electrodes, more people, longer sessions." |
| Video | 1:30 | Before pressing play: "This is a held-out person from the public dataset, replayed through our live gauge at real time. Rest reads zero; watch the load climb under silent subtraction, then fall back." Then let the video run. |

Slides 1 (how it works), 3 (training curve), 5 (demo trace) and 6 (app) stay in the folder for questions; the video
covers 5 and 6, and the ROC covers 3.

## Rules
- Say "held-out person from a public dataset" before the video. Nothing on screen says it.
- Quote only held-out numbers (0.74 pooled, 0.81 median). Never the 0.90 training figure.
- If you overrun, cut the second sentence of the Problem slide, not the Limits slide.
