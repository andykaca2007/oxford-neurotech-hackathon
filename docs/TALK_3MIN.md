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

## Deck order (8 Nov afternoon, `deck/index.html`)

The web deck adds three illustrated slides in front: 0 title (Team Avengers), 1 problem, 2 solution. The talk
above maps onto it as: title (silent, 0:00) -> problem (0:05, the Problem line) -> solution (0:15, "We built a
gauge for it from a consumer brain headset. Here it is running.") -> 4 video (0:25, the disclosure line, then
1:30 of silence) -> 5 filters (1:55) -> 8 ROC (2:20) -> 10 next (2:40). Skip slides 3, 6, 7 and 9 with the hash
keys if time is short; they stay in for questions.

## FINAL, judged version (8 Nov, 18:00): one beat per judging criterion, 2:52 with the 98 s video

Criteria: scientific validity, feasibility and implementation, originality, impact and marketability, presentation and
demonstration with honest limitations. Every slide now carries the criterion it answers as a small top-right tag, and
slide 10 (limitations) is back in the spoken path because the fifth criterion asks for it.

| Time | Slide | Criterion | Say |
|---|---|---|---|
| 0:00 | 0 title | | silent, 2 s |
| 0:02 | 1 problem | impact | "Surgeons, pilots, controllers and shift workers overload quietly, and the mistakes come after. There is no gauge for it. The brain shows it within seconds, but dry electrodes drown thirty microvolts of brain in six thousand of noise." |
| 0:14 | 2 solution | originality | "Our contribution is not a new headset. It is trust: six filters, features that ignore the electrode's gain, a model trained on thirty-six public brains, and a gauge that refuses to score a dirty signal instead of guessing. Here it is running." |
| 0:28 | 4 video | demonstration | "A real recording from a public dataset, through our live system, at real time. Watch the number climb under arithmetic and fall back." Then play; silence 0:34 to 2:12. |
| 2:12 | 5 filters | validity | "Validity first: every stage of that chain is checked against the live code, six thousand microvolts in, thirty-four out." |
| 2:20 | 8 ROC | validity | "Tested one held-out person at a time: AUROC zero point seven four pooled, zero point eight one median, good for twenty-three of thirty-six." |
| 2:29 | 7 how it works | feasibility | "It runs in real time on a laptop and an eight-electrode consumer headset; everything that comes next is software." |
| 2:37 | 10 limitations | honesty | "Honestly: on our dry cap four of eight electrodes rarely connected, so the gauge held rather than invent a number. The demo is a lab person, not our headset. Five of thirty-six people score below chance." |
| 2:49 | 11 next | feasibility | "Next: better electrodes, more people, longer sessions. We are Team Avengers." |
| 2:55 | end | | |

Slides 3, 6 and 9 stay in the deck for questions. If you overrun, shorten slide 2 to its first two sentences.
Never cut the line before the video or the limitations slide: criterion five is the one judges can check on the spot.

## FINAL, every slide (8 Nov, 17:15): 82 s of talk around the 98 s video, about 190 words

| Time | Slide | Say |
|---|---|---|
| 0:00 | 0 title | silent, 2 s |
| 0:02 | 1 problem | "Surgeons, pilots and shift workers overload quietly, and the mistakes come after. The brain shows it within seconds, but no wearable reads it: dry electrodes drown thirty microvolts of brain in six thousand of noise." |
| 0:14 | 2 solution | "So we built a gauge from a consumer headset. Eight dry electrodes, six filters, a model trained on thirty-six people, and a number that is zero at your own rest." |
| 0:26 | 3 numbers | "Three numbers: six thousand microvolts in, thirty-four out, and a load that sits at zero at rest and climbs under arithmetic. Here it is running." |
| 0:34 | 4 video | "A real recording from a public dataset, through our live system. Watch the number climb when they start calculating, and fall when they stop." Then play; silence 0:40 to 2:18. |
| 2:18 | 5 filters | "That works because the raw signal, nearly all noise, is stripped layer by layer until what is left is the brain." |
| 2:26 | 6 spectrum | "In frequency: the fifty hertz hum disappears, the brain bands stay." |
| 2:32 | 7 how it works | "Every second, a four-second window goes through the chain, becomes twenty-nine features, and the model turns them into one number against your own rest." |
| 2:41 | 8 ROC | "Tested on people it had never seen, it separates rest from hard thinking well for most of them." |
| 2:49 | 9 training curve | "It scores higher on people it trained on. We only quote the held-out number." |
| 2:54 | 10 next | "Next: better electrodes, more people, and the slow fatigue trend on the same page. We are Team Avengers." |
| 3:00 | end | |

If you run long, cut slide 9 first, then the first sentence of slide 7. Never cut the line before the video.

## FINAL script (8 Nov, 17:00): 82 s of talk around the 98 s video, about 140 words

| Time | Slide | Say |
|---|---|---|
| 0:00 | 0 title | silent, 3 s |
| 0:03 | 1 problem | "Surgeons, pilots and shift workers overload quietly, and the mistakes come after. There is no gauge for it. The brain shows it within seconds, but no wearable reads it: dry electrodes give six thousand microvolts of noise around thirty of brain." |
| 0:20 | 2 solution | "So we built a gauge from a consumer headset. Eight dry electrodes, six filters, a model trained on thirty-six people, and a number that is zero at your own rest. Here it is running." |
| 0:35 | 4 video | Before play: "A real recording from a public dataset, through our live system. Rest reads zero. Watch the number climb when they start calculating, and fall when they stop." Then silence; the video runs 0:40 to 2:18. |
| 2:18 | 5 filters | "That only works because the raw signal, nearly all noise, is stripped layer by layer until what is left is the brain." |
| 2:30 | 8 ROC | "Tested on people the system had never seen, it separates rest from hard thinking well for most of them." |
| 2:42 | 10 next | "A personal number, proven on people it had never met. Next: better electrodes, more people, and the slow fatigue trend on the same page. We are Team Avengers." |
| 3:00 | end | |

If you overrun, drop the second sentence of the problem slide. Never skip the line before the video.

Paing's call (8 Nov): no limits slide in the pitch. The one disclosure that must stay is the line before the video,
"a real recording from a public dataset, through our live system", since nothing on screen says it. If a judge asks
about the dry cap, the honest answer is in docs/OVERNIGHT.md: four of eight electrodes rarely connected and the gauge
held rather than scored.
