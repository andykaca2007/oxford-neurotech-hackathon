# Expert panel, Sat 7 Nov 2026, 13:00

Three AI-generated reviews (Nobel-persona prompts: AI researcher, polymath, systems engineer),
each given the Participant Information Sheet, the judging criteria and our assets. Verdict first,
then the three reports verbatim.

## Verdict (Claude's synthesis)

Stream: MEDTECH (Bitbrain). Two of three reviewers chose it; the third chose AI because a public
dataset removes the headset bottleneck, and that evidence is kept here as the validity backbone.
Medtech example 1 in the sheet is literally "a BCI that lets people with ALS or locked-in syndrome
communicate", which is this project. It plays to the team's strengths (hardware, signal,
biomedical framing) and avoids the one stream where strong-ML teams cluster.

Project, two sentences: a hands-free communication aid for people who can no longer speak or
type reliably (advanced Parkinson's "off" periods, ALS): look at one of four flickering tiles
for about 3 s and the carer's wristband buzzes with the chosen phrase. The decoder calibrates to
the person in one minute, and we show on held-out sessions how much that minute buys over a
generic decoder.

Keep: 4-tile SSVEP, CCA baseline vs per-person TRCA, fixed 16-phrase tree (two looks per
phrase, generated once offline), wristband output, calibration-length curve on the public
Tsinghua or Nakanishi benchmark (leave-one-subject-out) plus the same curve on 2 to 3 teammates
(train session A, test session B). Replay mode and a filmed run as the demo insurance.
Cut: runtime LLM relabelling (keep only as an offline phrase-tree generator, off the science
slide), cross-montage transfer-learning claim, Parkinson's drool-cue framing.

Medtech paperwork (one page, a teammate writes it): population and condition (ALS, advanced PD
with severe dysarthria and bradykinesia), prescribing clinician (speech and language therapist
via neurologist), intended use (AAC selection input), regulatory route (UKCA via MHRA, EU MDR;
argue Class I communication aid, note Rule 11 as the challenge), validation plan (3-site
usability and accuracy study in the target population, ITR and false selections per minute as
endpoints, comparison with eye-tracker AAC).

Honest sentence for the slide: three healthy students, one room, one headset, one afternoon;
nothing here shows it works for a patient, whose tremor, eye movement and medication state
differ; these numbers are a lab-condition ceiling.

Gates (engineer's):
- G1 15:00 scalp proof: all 8 channels nonzero and distinct; PO7 POz PO8 Pz under 40 uV RMS in
  1 to 40 Hz; POz alpha ratio eyes closed/open at least 2; a blink on Fz. No decoder work before.
- G2 17:00: 2 min cued recording, offline 4-class accuracy at least 70 percent on 3 s windows.
  Fail: two tiles (7.5 and 12 Hz), 4 s window.
- G3 20:00: live loop 8 of 10 cued selections, rest false selections under 2 per min.
  Fail: freeze CCA only, drop TRCA, demo by replay.
- G4 22:00: eval dataset from 3 members recorded, demo video in hand. Sleep.
- Sun 09:00 to 11:00 TRCA vs CCA figure; 11:00 to 13:00 slides and three dry runs; 13:00 code
  frozen, replay tested on the demo laptop.

Do before 14:00: team of 5 or 6; lock Medtech on the sign-up sheet; ask an organiser whether
pre-event code (CCA decoder, ESP32 firmware) must be declared, and declare it on a slide anyway;
book the Sunday headset slot ending at the demo; in the current slot record raw LSL to disk
before anything else.

---

## Report 1: AI researcher persona

### 1. Stream
Medtech (Bitbrain). Rough odds of taking the stream prize: Medtech 30 to 35 percent, Consumer 15 to 20, AI 10 to 15. Reasons: the AI stream will hold the most teams with identical headsets and at least two with stronger ML hands than a year-2 team recruited at 13:00; a flicker screen is a poor everyday consumer journey; Medtech rewards what you already hold (Parkinson's framing, a wristband, a validation plan you write rather than run) and the judging is on reasoning, not on who has the biggest model. The TRCA-vs-CCA evaluation still earns the scientific-validity mark in any stream.

### 2. The project
A hands-free call-and-phrase aid for people with advanced Parkinson's in an "off" period, when speech and hand control fail together: the patient looks at one of four tiles for 2 s and the carer's wristband buzzes with the message. The decoder is calibrated to the person in about one minute and we report, on held-out sessions, how much that calibration buys over the generic decoder.

### 3. ML core
Model: ensemble TRCA (Nakanishi 2018) spatial filters plus per-class templates, 4 channels, 2 s and 3 s windows. Baseline: your existing CCA with sine-cosine references and harmonics. Add a rejection rule (top-minus-second correlation margin) so "no pick" exists.
Data: (a) live, 2 to 3 team members, two sessions each, re-donning the headset with at least 20 min between, 4 classes x 10 trials x 3 s per session, plus 60 s of eyes-on-blank per session; (b) Nakanishi 2015 public set for the calibration-length curve (train TRCA on 1, 2, 4, 8 trials per class, test on the rest, 10 subjects).
Held-out protocol: train on session A, test on session B, never split trials inside one session. Report per-subject accuracy with Wilson 95 percent intervals over roughly 40 test trials each, chance 25 percent. On public data use leave-one-subject-out; pooled trial-level CV across subjects is the first thing a PI will tear apart.
Leakage traps: templates or spatial filters built from any test trial; rejection threshold or window length tuned on session B; alpha state and impedance drift hiding behind a same-session split; and the LLM prior reweighting the decoder before scoring. Cross-device transfer from Nakanishi (3 overlapping electrodes, different frequencies) will probably fail; do it only on public data and claim only what the curve shows.
Headline metric: held-out-session selection accuracy at 2 s. Second number on the same slide: false activations per minute during eyes-on-blank, because a buzzing carer is the cost of a false positive.

### 4. The LLM layer
It hurts validity the moment it touches the decoder: unmeasurable prior, hallucinated intents, and no reproducible evaluation. In Medtech it is also an IEC 62304 problem. Keep it only above the decoder: the LLM proposes three next tiles from a fixed logged vocabulary, tile four is always Cancel, deterministic phrase tree as fallback, and raw EEG never leaves the laptop (only labels go to the API). Evaluate it separately: looks-per-message on ten scripted messages versus the fixed tree. Never claim it improves decoding; keep it off the science slide.

### 5. 26-hour plan
Sat 14:00: stream locked, roles fixed: you on decoder and data, one medical or bio teammate on population, intended use, device class and validation plan, one on UI, wristband and LLM, one on protocol, recording and slides. Go/no-go: one real SSVEP peak visible in the POz PSD. Nakanishi downloaded, CCA baseline run on it. Lock the MacBook to 60 Hz, ProMotion off.
Sat 18:00: TRCA vs CCA leave-one-subject-out plus the calibration-length curve plotted on public data. This is the kill-switch deliverable. Subject 1 session A recorded with markers.
Sat 23:00: subject 1 session B tested; live loop end to end, look, decode, buzz; eyes-on-blank false-pick run; LLM keep or drop decided.
Sun 09:00: subjects 2 and 3 recorded in the fresh headset slot; results table filled; regulatory one-pager done (argue Class I under MDR, state that Rule 11 is the challenge).
Sun 12:00: slides frozen, demo rehearsed twice, backup video of the live loop recorded.
Kill switch, at 23:00 at the latest: no live SSVEP on any subject means the public-only version: "how little calibration does a personal SSVEP decoder need", wristband driven by replayed recorded EEG, labelled as replay, journey and regulatory sections unchanged.

### 6. Three ways to lose
Live demo dies on stage (dry electrodes, hair, someone's refresh rate). Fix: Sunday-morning video and a replay mode, rehearsed as if it were the main path.
A PI judge dismantles n=3 and same-session numbers. Fix: session split, intervals, the blank condition and public LOSO, and you state the limitations before they ask.
You look like the fourth "CCA plus a buzzer" team. Fix: the one artefact nobody else will have by Sunday, a measured calibration-length curve on held-out sessions, beside a concrete carer journey.

---

## Report 2: polymath persona

### 1. Inversion: how this loses on Sunday
1. No team of 5 by 14:00 (p 0.25). Pitch now, 30 s: "EEG typing with a wristband, decoder and hardware exist, need data, UI, clinical-writer, presenter." Take anyone.
2. Real-head SSVEP under 70 percent in the slot: dry electrodes, hair, hall noise (p 0.40). Record raw LSL to disk for the whole slot first; develop offline; never debug live.
3. TRCA calibration eats the slot, comparison never finishes on real data (p 0.50). Do the CCA vs TRCA comparison on the public dataset first; real heads are a replication, not the result.
4. "Transfer learning" from Nakanishi/Tsinghua to the Unicorn is incoherent: different montage, rate and frequencies (p 0.60 it looks fake). Align your tiles to dataset frequencies (8/10/12/14 Hz exist in Tsinghua) and call it "cross-subject initialisation", or drop the claim.
5. Tobii sponsors the AI stream; a judge asks "an eye tracker does look-at-a-tile better" (p 0.70). Have one honest sentence: SSVEP needs no camera, no lighting, works with glasses; it is a comparison, not a victory.
6. The PD cue story is muddled: a patient buzzing their own wrist by staring at a screen has no user journey (p 0.50). Reframe as communication for severe dysarthria (AAC), no medical claim.
7. Live demo dies at 15:00 Sunday because the headset is in another team's slot (p 0.35). Film the best slot; build a replay mode from the recording; say which it is.
8. Scope: LLM + TRCA + transfer + wristband + GUI with strangers in 24 h (p 0.70 one piece drags everything). Cut, see section 3.
9. Coordination with five strangers (p 0.40). Four modules with stub interfaces written by 15:00; nobody waits on anyone.
10. "All code during the hackathon" vs your pre-event CCA decoder and wristband firmware (p 0.30 questioned). Ask an organiser at 13:00; declare it on the slide; rewriting 40 lines of CCA live costs nothing.

### 2. Falsification
Strongest PI line: "CCA and TRCA on SSVEP were solved in 2015. The LLM autocomplete is not neuroscience and is not trained on neural data. Your transfer result is uninterpretable across montages, and with two heads and one slot you cannot state any accuracy with a confidence interval." The plan as stated does not survive. It survives only if the scientific claim moves to the public dataset: 35 subjects, held-out trials, accuracy and ITR versus number of calibration trials, CCA as the zero-calibration baseline. Then the real heads are a replication with n of 2, labelled as such.

### 3. Occam version
Keep: 4-tile SSVEP, CCA baseline vs per-person TRCA, calibration-trials-vs-accuracy curve on Tsinghua plus the same curve on two teammates, wristband buzz as output, a fixed 4 x 4 phrase tree (16 phrases, two looks) generated once offline. Cut: runtime LLM relabelling, transfer learning claim, Parkinson's framing. The phrase tree keeps the composition idea at zero runtime risk.

### 4. Streams
Outside view first: roughly 18 teams, 3 streams, top 3 of about 6 means a random team places with p near 0.45.
Stream | p(top 3) | Why
AI (Tobii) | 0.45 | Fits his DSP skills; public dataset satisfies held-out, baseline, metric without the headset; crowded with EEG-plus-model teams but most will lack a baseline.
Consumer (Emotiv) | 0.28 | Working demo rules, and a shared dry headset in a hall is the most fragile demo in the room; easiest stream so most crowded.
Medtech (Bitbrain) | 0.35 | Document-heavy; a Y2 BME can write a credible MDR Class IIa route and validation plan; SSVEP AAC fits, PD cueing does not.

### 5. Alternatives
A. Calibration-budget study as the core, headset as garnish: on Tsinghua, measure accuracy versus calibration trials for CCA, FBCCA, TRCA and TRCA initialised from other subjects' templates; replicate on two heads. The headset slot stops being the bottleneck and every AI-stream criterion is met by Saturday night. p beats leading plan 0.60 (it is the leading plan with the fiction removed).
B. SwallowCue on the Unicorn: if the Core-8 leads can be relocated, put one under the chin and one on the mastoid and run is_swallow() live, framed Medtech (PD sialorrhoea, named clinician, Class IIa). High originality and a clean user journey, but it rests on a physical question nobody has checked. p beats leading plan 0.25, high variance; spend five minutes checking the electrode leads before 14:00 and not one minute more.

### 6. Do this at 13:00
1. Recruit to five by 13:15 with the one-line pitch above, then ask an organiser whether pre-event decoder code must be declared.
2. Lock the AI stream at 14:00 under the title "How much calibration does a personal SSVEP decoder need?", CCA versus TRCA on the Tsinghua benchmark with held-out trials, replicated on two of you.
3. Drop the runtime LLM and the Parkinson's cue; use a fixed 16-phrase tree and the dysarthria communication story.
4. In every headset slot record raw LSL to disk before anything else, film the best run, and build replay mode so Sunday's demo cannot die.
5. Freeze code at 12:00 Sunday; spend the last hours on the curve, the baseline, the limitations slide and a 60 s video.

---

## Report 3: systems engineer persona

### 1. Signal chain failure modes (detect under 60 s, then fix)
- Contact: dry pins float on occipital hair, 100 to 500 uV broadband, no alpha. Detect: live per-channel RMS 1 to 40 Hz. Fix: part hair under PO7 POz PO8 Pz, press pins, chin strap, wait 60 s for drift to settle.
- Reference: a dry mastoid sticky makes every channel noisy and identical. Detect: odd channels correlate above 0.9, 50 Hz dominant. Fix: fresh sticky on wiped skin, firm clips.
- Pogo rows: even channels exactly zero = one row open (today's fault). Detect: zero variance. Fix: reseat until both rows click.
- BLE: 150 laptops on 2.4 GHz drop packets. Detect: sample-counter gaps, timestamp jumps over 20 ms. Fix: amplifier under 1 m, laptop Wi-Fi off, g.tec dongle not built-in BT.
- LSL timing: CCA is phase-free, so jitter only mislabels epochs. Detect: cue vs EEG local_clock differ over 50 ms. Fix: stamp cues with the same clock in the same process.
- Display: ProMotion drifts to 120 or 48 Hz and breaks frame counting. Detect: 600 frames must take 10.00 s plus or minus 0.02, zero dropped frames. Fix: lock 60 Hz in Displays, vsync on, LLM call in a thread.
- Filter: per-window filtering adds a startup transient. Detect: first 0.5 s of a window at 10x RMS. Fix: filter the stream continuously, then slice.
- CCA window: 3 s plus two hops plus refractory = 3.5 s per selection, not 2. Fix: the pitch says 3 to 4 s.
- Pick rule: floor 0.45 may exceed a weak responder's peak. Detect: 60 s rest, log peak correlation (null sits 0.2 to 0.3). Fix: floor = rest 99th percentile plus 0.1.
- Serial: ESP32 resets on port open, first "b" lost. Detect: no ack byte. Fix: open once at boot, wait 2 s, flush, require ack.
- Motor: coin inrush browns out the ESP32. Detect: port re-enumerates after a buzz. Fix: 100 uF across the motor, flyback diode.
Scalp proof, in order: all 8 channels nonzero and non-identical; after 60 s, PO7 POz PO8 Pz RMS 1 to 40 Hz under 40 uV and 50 Hz under 10 uV post-notch; 15 s eyes open then 15 s closed, POz 8 to 12 Hz power ratio at least 2 (3 is comfortable); one blink visible on Fz. Without steps 2 and 3, no decoder work.

### 2. Demo rig that cannot fail
One code path, two sources: live BLE or a recorded raw file with cue times. Pre-record Saturday inside the slot: three full message compositions, a 2 min armed rest, and a phone video of the live run. Sunday: one live attempt, 2 min cap; on no selection or BLE drop, switch to replay with a visible REPLAY banner plus the video. Crowded room: dongle, amplifier under 1 m, Wi-Fi off; the replay is the real insurance. Headset: book the Sunday slot ending at the demo, but treat Saturday's slot as the only one that exists; every dataset, video and screenshot comes out of it. Bring your own mastoid stickies and alcohol wipes; 12 teams drain consumables.

### 3. Schedule, 5 roles
Sat 13:00 to 14:00: lock Medtech (PD population, prescribing clinician, class I communication aid route). Screen locks 60 Hz and runs tiles; wristband closes the ack loop; eval writes the recorder; pitch storyboards.
G1 15:00: scalp proof passes. Fail: signal stays with g.tec staff; decoder validates CCA on synthetic sines plus pink noise; others proceed.
G2 17:00: 2 min cued recording, offline 4-class accuracy at least 70 percent on 3 s windows. Fail: 2 tiles (7.5 and 12 Hz), 4 s window.
G3 20:00: live loop, 8 of 10 cued selections, rest false selections under 2 per min. Fail: freeze CCA only, drop TRCA, demo by replay.
G4 22:00: eval dataset from 3 members recorded, demo video in hand. Sleep.
Sun 09:00 to 11:00: TRCA vs CCA offline, one figure. 11:00 to 13:00: slides, three dry runs. 13:00 to 15:00: code frozen, everything charged, replay tested on the demo laptop.

### 4. Evaluation protocol
Three healthy team members, one session each: 60 s calibration (4 classes x 5 x 3 s), then 4 blocks of 12 cued trials (4 classes x 3, random order), 4 s stimulus, 3 s rest: 48 trials per subject, 144 total, plus 2 min eyes-open rest with the decoder armed. Held out: blocks 3 and 4, recorded after the training blocks; CCA needs no training so it also gets cross-subject. Report accuracy, false selections per minute = armed-rest selections / 2, and ITR with N=4: bits = log2 N + P log2 P + (1-P) log2((1-P)/(N-1)), per minute over the 7 s trial including rest. Honest sentence: three healthy students, one room, one headset, one afternoon; nothing here shows it works for a person with Parkinson's, whose tremor, eye movement and medication state differ, and these numbers are a lab-condition ceiling.

### 5. The first risk
The occipital electrodes sit where hair is thickest and cap pressure weakest, and 130 to 520 uV with no alpha says they were floating, not merely unseated; fixing the pogo row alone may leave PO7 POz PO8 above 40 uV all weekend. Prove contact in the first hour or decode from Pz and Cz only, which halves the SNR but is honest.
