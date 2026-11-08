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

## Plain version (chosen 8 Nov): the figures carry the detail, the talk stays non-technical

About 100 words in 90 seconds, so each figure gets a few seconds of silence to be read.

| Time | Slide | Say |
|---|---|---|
| 0:00 | 0 Problem | "Pilots, surgeons and shift workers overload quietly, and mistakes follow. We built a gauge for it from a consumer brain headset." |
| 0:25 | 2 Filters | "The raw signal is nearly all noise. Our software strips it layer by layer until what is left is the brain." |
| 0:45 | 4 ROC | "We tested on people the system had never seen. It separates rest from hard thinking well for most of them." |
| 1:05 | 7 Limits | "The software works. Our dry electrodes do not connect well yet, and when they do not, it says so instead of guessing." |
| 1:30 | video | "Here is a real recording from a public dataset, through our live system. Watch the number climb when they start calculating." |

If a judge asks for numbers, they are on the slides: 6,000 µV to 34 µV; AUROC 0.74 held out, median 0.81 per person.

## Final order (8 Nov): the demo sandwiched inside the pitch

The demo is the selling point, so it comes right after the problem, while the room is curious; the proof and the
limits follow once they have seen it work.

| Time | Slide | Say |
|---|---|---|
| 0:00 | 0 Problem | "Pilots, surgeons and shift workers overload quietly, and mistakes follow. We built a gauge for it from a consumer brain headset. Here it is running." |
| 0:20 | video (1:30) | Before play: "A real recording from a public dataset, through our live system. Watch the number climb when they start calculating, and fall when they stop." Then silence. |
| 1:50 | 2 Filters | "What you just saw is only possible because the raw signal, nearly all noise, is stripped layer by layer until what is left is the brain." |
| 2:15 | 4 ROC | "Tested on people the system had never seen, it separates rest from hard thinking well for most of them." |
| 2:35 | 7 Next | "A personal number, proven on people the system had never seen. Next: better electrodes, more people, and the slow fatigue trend on the same page." |
| 3:00 | end | |

Paing's call (8 Nov): no limits slide in the pitch. The one disclosure that must stay is the line before the video,
"a real recording from a public dataset, through our live system", since nothing on screen says it. If a judge asks
about the dry cap, the honest answer is in docs/OVERNIGHT.md: four of eight electrodes rarely connected and the gauge
held rather than scored.
