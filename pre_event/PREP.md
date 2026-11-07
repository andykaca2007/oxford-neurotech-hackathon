# Oxford Neurotech Hackathon 2026: prep

Checked 2026-10-31. Sources: oxneurotech.com/hackathon, luma.com/ceww7ooe, winner write-ups listed at the bottom.

## 0. Before the event

1. **Applied** (you confirmed 31 Oct) at https://luma.com/ceww7ooe. Approval required: watch for the Luma "approved" email (it may land on your UCL address, not Gmail).
2. **Text Radin Moradi** (Oxford biochem, your AI x Science teammate). Local, knows the city, and judges are Oxford PIs. Sina and Andy too if they want it. Teams up to 5, each person applies separately.
3. **Email oxneurotech@gmail.com** (chair: Mattan Pelah, president@oxneurotech.com) with five questions the pages leave blank: are UCL students eligible, what BCI hardware is coming (EMG-capable?), start and end times / overnight, may we bring pre-written code, may we bring our own hardware (a servo claw + ESP32, no body contact).

**Own-hardware kit (if allowed):** ESP32 + cable, 1 to 2 servos with their own 5 V supply (not USB), a small printed claw, breadboard + jumpers, multimeter. Not your EMG board unless its bring-up passes at home first. Nothing that stimulates a person. Laptop on battery whenever anything is wired to a body.

## 1. What is known

| | |
|---|---|
| When | Sat 7 to Sun 8 Nov 2026, times not published |
| Where | Andrew Wiles Building, Mathematical Institute, Woodstock Rd, OX2 6GG |
| Teams | up to 5 |
| Tracks | 4, "from peripheral nervous-system interfaces to sub-cortical implants". Names not published |
| Hardware | "research-grade BCI systems" from an equipment partner, still unconfirmed on 31 Oct. The society owns OpenBCI kit (Cyton + Daisy, Ultracortex Mark IV) and has used a Neurosity Crown |
| AI | an "AI partner" platform for decoding models, pipelines, agents |
| Judges | per track: Oxford PIs + one industry judge |
| Prizes | GBP 5,000+ in prizes, a small startup fund + a VC consultation for the most startup-ready project |
| Criteria | not published. Global NeuroHack (Apr 2026, listed as an OxNeurotech project) used Innovation / Technical complexity / Impact / Presentation at 25% each. Assume that |
| Food | free meals, Oxford tours |

**The organiser.** Mattan Pelah, OxNeurotech founder and chair, is a DPhil in Tim Denison's Brain Engineering Lab (Oxford IBME), on closed-loop neuromodulation for pain. Listed interests: neuromodulation, bidirectional BCIs, implantables, physiological closed-loop control. His own hackathon win (Sense-OC, below) was closed-loop sensory restoration. Source: ibme.ox.ac.uk/person/mattan-pelah

## 2. Reading week fit

Reading week is 1 to 8 Nov, so no classes lost. Around it:

- Mon 2 Nov 20:00: UCL AI Soc design task due. ARC-AGI-3 closes the same day.
- Thu 5 Nov: internship follow-ups, Kaggle cron re-create.
- **Fri 13 Nov 17:00: MPHY0011 Task 1.** The Oxford weekend eats two days of that buffer. Get the draft done by Thu 5 Nov.
- Mon 9 Nov: MPHY0010 Scenario 3 week starts (compulsory). Be home Sunday night.

Getting there (you don't drive): train from Paddington or Marylebone, about 1 h, or the Oxford Tube coach from London (cheaper, runs all night). The venue is a short walk north of the city centre.

## 3. Past winners (closest events, 2022 to 2026)

| Event | Place | Team | Built | Signal |
|---|---|---|---|---|
| London Neurotech Hackathon (Imperial), Feb 2026, Bluesky | 1st | **Sense-OC (incl. Mattan Pelah)** | arm sleeve that restores touch by electrical stimulation after stroke / diabetic neuropathy, guided by camera glasses + EEG feedback | stimulation + CV + EEG |
| London Neurotech Hackathon, Feb 2026, NeuroAI | 1st | Flextra | game app + EEG error-related negativity to measure cognitive rigidity in OCD | EEG (ERN) |
| London Neurotech Hackathon, Jan 2025 | 1st | GastroMod | flexible electrodes inside the gut (concept) | concept |
| same | runner-up | ShutEye | EEG sleep mask, working prototype in 24 h (lost to a concept: investor judges) | EEG |
| Global NeuroHack SF, Apr 2026, Blue Sky | 1st | NeuroBite (5 first-years) | detects teeth grinding and interrupts it | EEG + mouthpiece |
| same, speech decoding | 1st / 2nd | CereBro / FABLE | EEG foundation-model backbones for inner speech / EEG storybook for aphasia | EEG |
| same, Science Corp bit rate | 1st | NeuralShred | Guitar Hero game driven by decoded mock spikes, judged on bit rate | mock spikes |
| Imperial closed-loop hackathon, Jun 2025 | 1st | Birmingham team | real-time EEG-driven audio stimulation, scored on measured relaxation biomarkers | Elemind EEG |
| Precision Neuroscience Brain Storm, Jan 2026 | 1st (91.7 vs 69.2) | MindMeld | micro-ECoG tone decoder; won by measuring window length vs latency from day 1 | implant data |
| NeuroTechX student clubs 2023 | 1st / 2nd | NeurotechSC / Triton | facial EMG silent speech / 4-channel EMG armband | **EMG** |
| NeurotechEU Neurospark, Nov 2025 | winners | 3 teams | phone-scrolling alert, therapy-room EEG, motor-imagery stroke rehab game | EEG |
| g.tec BR41N.IO, 2022 to 2025 | category wins | many | mostly P300 speller or band-power "focus/emotion" driving a robot, Alexa, ChatGPT, a game | EEG, ECoG data |

**What the record says:**

1. **Named patient + closed loop.** OCD, stroke, neuropathy, bruxism, aphasia. Most go sense, decide, then act on the body or the world.
2. **EMG wins and is rare.** It took 1st and 2nd at NTX 2023, and no UK neurotech hackathon winner used it. Open lane in a peripheral track.
3. **SSVEP almost never wins.** One win found (2022, when the prompt demanded a visual paradigm). Spellers are the overdone demo.
4. **Metric tracks go to whoever builds the scoring script first** (MindMeld, NeuralShred, Imperial closed-loop). If a sponsor track states a number, optimise that number from hour 1.
5. **Investor judges reward framing, PI judges reward substance.** Oxford's are PIs: a measured result on a real signal counts more here than in London.
6. **Implant tracks:** nobody builds implant hardware in a weekend. Winners there are concept + pitch, or decoding of real implant data.

LinkedIn profiles block reading (login wall). Winner details come from search snippets, one public activity feed, news posts, the e184 blog, Felix, Imperial, br41n.io and university pages.

## 4. What to compete with

### 4a. LOCKED 4 Nov: SwallowCue, a swallow-sensing drooling aid for Parkinson's

**History:** tremor phase-locking (dropped 2 Nov: the Oxford judges' own work), then hijack-and-defend (dropped 4 Nov: clever but not useful now). Picked from a patient-first sweep of 4 groups, see `RESEARCH_2026-11-04.md`.

**Patient:** up to 70% of people with Parkinson's drool. They make normal saliva but swallow too rarely. It is embarrassing enough that people stop eating out (PMC9955579).

**What it does:**
1. EMG electrodes under the chin (submental muscles), from the event's kit.
2. Band-pass, rectify, envelope; find muscle bursts.
3. Classify each burst: swallow, or talking/chewing (duration + whether it stands alone).
4. If no swallow for T seconds (set per person), the ESP32 wristband buzzes. A swallow resets the timer.
5. Screen: live swallow count, time since last swallow, cues given, and what a fixed once-a-minute schedule would have done over the same time.

**The gap (checked 4 Nov):**
- McNaney 2019 (PD-CUE, 28 people): a wristband buzzing ONCE A MINUTE reduced self-reported drooling.
- CueBand (Northumbria, Parkinson's UK funded, 300-person trial ISRCTN59284050): still a FIXED schedule, no swallow sensing.
- Northwestern "Aria" patch (NCT04664634, about 60 people, no results): DOES sense and cue, apparently acoustic. So we are not first. Pitch: **"a smart, open, cheap CueBand that buzzes only when you have stopped swallowing, using muscle signals"**.
- Offline under-chin EMG swallow detection in PD: 83% (MDPI Sensors 2025). No live closed-loop version found at a hackathon.

**Demo (30 s, nothing faked):** talk: no count. Sip water: count +1. Chew gum: no count. Hold off swallowing: buzz at T. Swallow: reset. Slide: detection rate on swallows and false counts per minute of talking and chewing, measured on the team during the weekend (state N).

**Claims allowed:** detects and cues swallows in healthy volunteers, with numbers. **Never** "reduces drooling" (needs a patient trial; cite McNaney for why cueing is plausible).

**Risks:** talking/chewing false positives (duration + isolation rule; optional chin IMU or throat mic as a second check); beards (clean-shaven wearer); head-down posture; a 250 Hz Cyton only sees up to 125 Hz (fine for an envelope).

**Team roles:** signal processing + classifier (you), ESP32 wristband + link, dashboard, patient story (a clinician or neuro student).

**Startup angle:** CueBand shows people will wear a cueing band; the add-on is the sensor that makes it smart and gives clinicians a swallow-rate record.

**Plan B, if there is no EMG kit (built 6 Nov, `planb_imu/`):** the organisers only announce hardware on Saturday, so SwallowCue also runs on your own parts. GY-521 taped to the throat below the Adam's apple senses the larynx lifting; ESP32 DevKit + PN2222 buzzes the coin motor. Same loop: movement envelope, bursts, `is_swallow()` (yours, `src/is_swallow.cpp`), cue after T s. The gyro rejects head nods. Detector tests pass on the laptop (6/6), firmware builds; **nothing flashed or worn yet**. Wiring, sensor placement, 10-minute first test and demo script: `planb_imu/WIRING.md`. Live demo screen: `uv run tools/live_plot.py <port>`. Swallowing accelerometry is an established research method (dysphagia screening), so pitch it as cheap and open, not first.

**Full prep pack (6 Nov): `prep_pack/main.pdf`, 10 pages.** Tonight's checklist, travel (leave Marble Arch by 06:15), kit list, timeline with checkpoints, hardware-to-path table, track decision table, pin-level wiring, electrode placement, measurement protocol, pitch skeleton, judge Q&A, risks, team, safety. Tools built the same day:
- `live_emg/swallowcue_live.py`: live chin-EMG pipeline (BrainFlow: cyton, cyton_daisy, ganglion, synthetic, or `--board fake`), mains notch, filters set from the sample rate (Cyton+Daisy is only 125 Hz), uses YOUR `is_swallow()` from `warmup/swallow.py`, sends `b` to the ESP32 wristband, `--log` for scoring. Tested on fake and synthetic boards only.
- `tools/live_plot.py`: demo screen for any path (serial port or a log file), `--log` + Enter marks.
- `tools/eval_session.py`: caught %, false counts per minute, buzzes vs a fixed schedule (`--period`).
- `planb_imu` firmware now also runs as wristband-only (no IMU) and reads a muscle-sensor envelope on GPIO 34 (`e`).

### 4c. Runners-up if a track demands something else

- GuardRelease: lumbar EMG + IMU, buzz when back muscles stay braced at full bend (chronic back pain, the organiser's pain field).
- BreathDrive: respiratory-muscle EMG drive for MND, flag for NIV review (most unique, riskier demo).
- Hijack-and-defend (`warmup/spoof.py`): only if a track is about device safety.

### 4b. Safe fallback: closed-loop EMG assist

**Pick if A is blocked (no IMU, or a track that excludes it): a closed-loop EMG assist for stroke hand rehab.** Weak residual forearm EMG, decode the intent to open or close, drive an assist (a claw, glove or vibration cue), and hold when the decoder is unsure, because a hand that moves the wrong way is worse than one that waits.

Why this, given the record:
- Closed loop on a peripheral signal, with a named patient: the exact shape of the organiser's own win and his DPhil.
- EMG wins (NTX 2023) and nobody in the UK events used it.
- PI judges: you bring a measured number. Accuracy and hold rate on a session or person not used for training, with a chance line.
- You already know the method (emg_hand/ml design: session split, conformal hold). The weekend goes on the demo.

The "hold when unsure" part is the safety layer and the Technical score, not the headline. The headline is the patient and the loop.

**If there is no EMG hardware:** close a loop on EEG with a measured effect (the Imperial closed-loop pattern: sense a state, stimulate with sound or light, show the biomarker change), or an ERP marker with a game (the Flextra pattern). Not an SSVEP speller.

**If a sponsor track states a metric:** drop the plan and optimise that metric. Write the scoring script in hour 1.

Still yours to decide with the team on day 1: the patient group (stroke rehab, prosthesis, something a clinician teammate knows), and how the hold looks on screen (freeze, slow, ask to confirm).

Avoid: SSVEP spellers, motor imagery (long calibration, often fails live), "decode thoughts or images", stimulating a person beyond what the organisers' kit and rules allow.

Rules that hold:
- **Do not bring your EMG board as the demo.** Its analogue front end has never been powered. Use their hardware (an OpenBCI Cyton records EMG).
- Prior code (emg_hand/ml) is fine only if the rules allow it. Ask, and say it is prior work in the pitch.
- Team work is team work. Never present it as solo afterwards.

## 5. Before 7 Nov (about 3 h total)

1. **Warm-up, 45 min:** `warmup/swallow.py`, write `is_swallow()` (rule for swallow vs talking/chewing, guidance in the docstring), run `python3 -m pytest -q test_swallow.py` in `warmup/` until it passes.
1b. **Buy by Fri 6 Nov:** coin vibration motors (about GBP 5); a pack of disposable gel ECG/EMG electrodes as a backup to the event's (about GBP 6 to 8); an NPN transistor (2N2222 or S8050) or small MOSFET to switch the motor, unless the ELEGOO kit has one (my notes confirm only its 1 A diodes). You own the ESP32s. The second IMU is no longer needed.
2. **Laptop, 45 min:** venv with `numpy scipy scikit-learn torch mne brainflow pylsl neurokit2`. Check BrainFlow's synthetic board streams (works without a headset). BrainFlow also reads the OpenBCI Cyton, so the same script runs on their kit.
3. **EMG refresher, 30 min:** reread `~/Documents/emg_hand/ml/README.md` and `conformal.py` so the session split and hold rule are fresh.
4. **Pitch skeleton, 30 min:** 5 slides. Patient / the loop / live demo / honest number with chance line / what next. Fill on the day.
5. **Team:** Radin + 1 to 3 more, one of them a clinician or neuroscientist.

## 6. On the day

- Bring: ESP32 DevKit, GY-521, PN2222 + diode + 1 kOhm, coin motors, breadboard, long jumpers, medical tape, USB cable, gel electrodes. Registration 08:45, talks ~09:45.
- First hour: find the equipment table, ask if anything records EMG, take a 2-minute recording. No EMG: switch to `planb_imu/` at once. Read the track briefs for any stated metric. Look up each track's PI judges.
- Checkpoints (shift once times are known): track + idea chosen by start + 2 h; ugly end-to-end loop by start + 8 h; sleep 4 to 5 h; feature freeze 3 h before the deadline; pitch rehearsed twice.
- Record a backup video of the demo working, in case the live one fails.
- After: one-line follow-up to each PI judge within 2 days.

## Sources

- https://oxneurotech.com/hackathon and https://luma.com/ceww7ooe
- https://ibme.ox.ac.uk/person/mattan-pelah/
- https://felixonline.co.uk/articles/the-london-neurotech-hackathon/
- https://iclneurotech.co.uk/hackathon
- https://www.uclbbk-mrcdtp.ac.uk/news/first-place-london-neurotech-hackathon
- https://engineering.ucsc.edu/news/ucsc-students-win-global-neurohack-2026/
- https://e184.substack.com/p/two-bci-events-one-goal
- https://global-neurohack.github.io/
- https://www.imperial.ac.uk/dementia-research-institute/events/closed-loop-neurotechnology-hackathon
- https://qsimeon.github.io/brainstorm_bci_blog.html
- https://openbci.com/community/?p=37201 and https://openbci.com/community/?p=34193
- https://neurotecheu.umh.es/en/2025/11/18/el-hackathon-de-2025-celebrado-en-la-umh-neurospark/
- https://br41n.io (IEEE-SMC-2022, 2023, 2025; Spring-School-2022, 2023)
- https://github.com/OxNeurotech
- Hijack-and-defend (4a, added 2 Nov): https://pubmed.ncbi.nlm.nih.gov/27184896/ (Pycroft 2016 Brainjacking), https://doaj.org/article/05914149d0014aa6afadec1d9cbd90d6 (IEEE Access 2025 DBS false-data defence), Trippel et al. 2017 WALNUT (IEEE EuroS&P), Shoukry et al. 2015 PyCRA (ACM CCS)
- Why the tremor pick was dropped: https://doaj.org/article/dcadfca39a9b480a886624ff0e1680b9 (Reis 2021), https://academic.oup.com/brain/article/140/1/5/2748089 (Cagnan 2017), https://cdn.clinicaltrials.gov/large-docs/90/NCT06235190/Prot_000.pdf (Felix NeuroAI)
