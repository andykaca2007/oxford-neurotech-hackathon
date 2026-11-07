# The g.tec brain-interface track: what you are walking into

Written Sat 7 Nov 2026, late morning, from the web and the hackathon Discord.
Nothing here was tested on a headset. Where a fact comes from one gist or one
page, it says so. Confirm the starred items at the g.tec table before building.

## 1. The kit (almost certainly the Unicorn Hybrid Black)

g.tec's hackathon headset is the Unicorn Hybrid Black. Facts that matter:

| What | Value | Confidence |
|---|---|---|
| EEG channels | 8: Fz, C3, Cz, C4, Pz, PO7, Oz, PO8 | high (g.tec Recorder page, validation paper) |
| Reference and ground | sticky electrodes on the two mastoids (behind the ears), L and R clips | high (g.tec quick-start) |
| Sample rate | 250 Hz fixed, 24-bit | high |
| Electrodes | hybrid: work dry, better wet (a drop of water or the g.tec gel) | high |
| Extras in the stream | 3-axis accelerometer (g), 3-axis gyro (deg/s), battery %, sample counter | high |
| Radio | Bluetooth 2.1 + EDR classic, serial-port profile (SPP), not BLE | high |
| Battery | more than 3 h | g.tec claim |
| Official software | Unicorn Suite: Recorder, Speller (P300), Python/C/.NET/Android APIs, LSL + UDP senders. WINDOWS ONLY | high |
| BrainFlow | board id UNICORN_BOARD; Windows and Linux only, needs the g.tec USB dongle, pair via the dongle not built-in BT | high (BrainFlow docs) |
| g.Pype | g.tec's newer Python SDK, `pip install gpype`; PyPI ships macOS universal2 wheels (py3.10 to 3.13) and says Windows + macOS | medium: one doc summary said the HybridBlack source raises NotImplementedError off Windows, another said macOS needs the event loop running. TRY IT |

Starred, ask on site: do they lend the USB dongle, the gel, and a Windows laptop
with the Suite licence? Is the Speller licence active on the lent units?

## 2. Your Mac problem, three routes (do them in this order)

**Route A, teammate with Windows.** Unicorn Suite on their laptop, Unicorn LSL
or UDP sender streams to your Mac over the venue Wi-Fi (or a phone hotspot:
venue Wi-Fi often blocks peer traffic). You read it with pylsl. Fastest and
official. Also the only way to run the impedance view and the P300 Speller.

**Route B, raw Bluetooth on your Mac, no dongle.** The headset is a classic
Bluetooth serial device. Pair it in System Settings > Bluetooth (it shows up
as `UN-YYYYMMDD`, the serial number). It then appears as `/dev/cu.UN-YYYYMMDD`.
Protocol, from Robert Oostenveld's unicorn2lsl gist and the Rust `gtec` crate
(both say it came from g.tec's own Bluetooth protocol document):

- 115200 baud
- start: send `61 7C 87`, device answers `00 00 00`
- stop: send `63 5C C5`
- then 45-byte frames at 250 Hz:
  - bytes 0 to 1: `C0 00`
  - byte 2 low nibble: battery, 100 * n / 15 percent
  - bytes 3 to 26: 8 x 24-bit signed big-endian EEG, uV = raw * 4500000 / 50331642
  - bytes 27 to 32: accel X Y Z int16 little-endian, g = raw / 4096
  - bytes 33 to 38: gyro X Y Z int16 little-endian, dps = raw / 32.8
  - bytes 39 to 42: uint32 little-endian sample counter
  - bytes 43 to 44: `0D 0A`

The two public Python gists have two bugs: EEG sign extension is wrong and the
gyro reads the accelerometer bytes. `unicorn/unicorn_mac.py` in this folder
fixes both and logs CSV, pushes LSL if pylsl is installed, and prints a
per-channel quality line every second. If Bluetooth stalls: `sudo pkill bluetoothd`
(FieldTrip's tip), power-cycle the headset, re-pair.

**Route C, g.Pype on the Mac.** `uv pip install gpype`, then try the
HybridBlack source. If it imports and discovers the device, it is the cleanest
official path on macOS. If it raises NotImplementedError, fall back to B.

## 3. What wins on this hardware (g.tec's own hackathons, BR41N.IO)

g.tec's categories: BCI gaming, BCI programming (Speller to smart home, ChatGPT,
drone, orthosis), data analysis, and arts. Documented winners used the Unicorn
with a P300 speller to drive a remote robot, and EEG to steer a NAO robot's
expressed emotion. g.tec's own developer guide says the usual failure is
signal quality, not the classifier. Two-day reality on 8 channels:

| Paradigm | Why it fits this headset | Setup cost | Risk |
|---|---|---|---|
| SSVEP (flicker, look at a target) | PO7, Oz, PO8 are exactly the occipital sites; no training; works for most people on first try | 2 to 3 h | screen timing; some people get nothing; eye strain |
| P300 (Speller) | g.tec ships it; Fz, Cz, Pz are the P300 sites | needs the Windows Suite and 5 to 10 min calibration per user | slow (seconds per choice); looks like a demo of their product, not yours |
| Motor imagery (C3, C4) | the hardware is right for it | 20 to 40 min training per person, and often fails on day one | highest risk; avoid as the main demo |
| Band power / neurofeedback (alpha at Oz with eyes closed, beta, engagement) | zero training, a strong effect you can show in 30 s | 1 h | judges have seen "brain-controlled lamp" many times |
| Artefact-as-signal (blinks, jaw clench, SWALLOWS) | giant, reliable, 1 line of thresholding | 30 min | it is not brain; say so out loud or lose the room |

Recommendation: SSVEP as the backbone, with one of your own physical outputs on
the end (the ESP32 wristband or motor you already built and brought) so the
demo is a real device, not a cursor. Add the artefact channel as a second,
honest input if the application calls for it.

## 4. Where SwallowCue fits, or does not

Two honest findings:

1. Swallows produce a large EMG and glossokinetic artefact across nearly all
   EEG channels (a Buenos Aires EEG-artefact chapter shows a swallow window
   contaminating almost every trace). A 32-channel volitional-swallow study
   (Frontiers 2021) found swallow onsets from submental EMG and then looked at
   EEG, so the brain side of swallowing is studied, but with a chin EMG as the
   ground truth, not the other way round.
2. The track is "brain interface". A throat-EMG drool cue is peripheral. Judges
   are Oxford PIs plus a g.tec person. They will ask what the brain adds.

Options, best first:

**Option 1 (recommended): "Cue by intent". Keep the Parkinson's cueing idea,
move the input to the brain.** People with PD need cues (gait freezing, swallow
reminders, speech volume) and often cannot press a button quickly or at all.
Build an SSVEP "cue remote": 3 or 4 flickering tiles on the laptop (water,
swallow, stand, help). Look at one for 2 s and the ESP32 wristband buzzes the
matching pattern, or sends the cue to a carer's phone. Your prep carries over:
the ESP32, the motor, the cue timer, the scoring script. The pitch: hands-free,
no training, works with 8 dry electrodes, and the cue is a thing you built.

**Option 2: SwallowCue stays, the headset becomes the sensor.** Detect swallows
from the EEG artefact plus the head-IMU in the headset, cue when none for T s.
Cheap to build (your detector already takes any envelope), but the honest claim
is "we used the headset as an EMG and motion sensor". A g.tec judge will say
"then why not a chin electrode". Only do this as the add-on to Option 1
(a swallow counter running on the same stream, shown in the corner).

**Option 3: Neurofeedback for PD attention or relaxation.** Alpha/beta ratio
at Cz and Pz driving a visual. Easy, but generic.

Someone in #questions asked at 11:00 "are there any EMG electrodes for us to
use?" and had no answer by 11:30. If the answer turns out to be yes, your
original under-chin EMG plan is back on the table for a different track.

## 5. SSVEP numbers you need

- Screen flicker must be an integer divisor of the refresh rate. On a 60 Hz
  display the usable set is 15, 12, 10, 8.57, 7.5 Hz (4, 5, 6, 7, 8 frames).
  Pick 7.5, 8.57, 10, 12 Hz for four targets, at least 1 Hz apart. Set the
  MacBook to a fixed 60 Hz in System Settings > Displays (ProMotion varies).
- Channels: PO7, Oz, PO8, plus Pz. Band-pass 5 to 40 Hz, notch 50 Hz (UK mains).
- Decoder: canonical correlation analysis. For each target f, reference
  Y_f = [sin 2pi f t, cos 2pi f t, sin 2pi 2f t, cos 2pi 2f t], X = the 4
  channels over a 2 to 4 s window; score_f = max canonical correlation. Pick the
  argmax if it beats the runner-up by a margin, else abstain. Expect 4-class
  accuracy of 80 to 95 percent in 3 s on a good head, far less on a bad one.
- Literature anchor: the Nakanishi 2015 benchmark (8 occipital channels,
  256 Hz) is the standard CCA test set; the BR41N.IO SSVEP data-analysis
  track used 4 classes.

## 6. First hour at the g.tec table

1. Get a headset, the two mastoid stickies, the gel or a water spray.
2. Pair with your Mac over plain Bluetooth, run `uv run unicorn/unicorn_mac.py --list`
   then `uv run unicorn/unicorn_mac.py --port /dev/cu.UN-XXXXXXXX --log s0.csv`.
   If the first 45-byte frame does not start `C0 00`, try Route A or C instead.
3. Quality line: every channel should sit under about 30 uV RMS at rest with
   the electrodes wet; a channel at hundreds of uV is not touching the scalp
   (press, twist, add a drop). Mains hum means the mastoid reference is loose.
4. Alpha test: eyes closed 10 s, the Oz 8 to 12 Hz power should jump 2x or
   more. If it does, the headset is on properly. Blink test on Fz. Jaw clench on
   everything.
5. Only then start the flicker screen and the decoder.

## 7. Questions the judges will ask

- Why 8 dry channels and not a lab EEG? (Wearable, 5-minute setup, that is the point of the Unicorn.)
- Training per user? (SSVEP: none. Say it.)
- How many false selections per minute? (Have the number from your log; abstain rule.)
- Does it work on someone who has not practised? (Demo on a judge if the pipeline is clean; otherwise on a teammate who put it on 5 min before.)
- Who is this for and what did a patient say? (Nobody with PD wore it. Say so. Cite the cueing need, not an outcome.)
- What is the brain part? (The decision is read from visual cortex; the actuator is yours.)

## 8. Claims you may make

- "Hands-free selection from 8-channel dry EEG, no per-user training, X percent on N trials in our team."
- Never: "helps patients", "reduces drooling", "clinically validated".
- Team work is the team's. Say who built what.

## Sources

- g.tec Unicorn Hybrid Black product and resources pages (specs, Windows-only Suite, mastoid reference)
- g.tec quick-start PDF (electrode placement)
- Pontifex 2023 validation of the Unicorn (8 ch, 250 Hz, mastoid reference)
- BrainFlow SupportedBoards.rst (Unicorn: Windows, Linux, dongle)
- gpype.gtec.at HybridBlack page and PyPI gpype (macOS wheels)
- Oostenveld unicorn2lsl gist and myd7349 fork (serial protocol, known bugs); docs.rs gtec crate README (packet table incl. gyro at 33 to 38)
- FieldTrip realtime/unicorn page (SPP, bluetoothd tip)
- g.tec IEEE SMC 2026 BR41N.IO page (categories, prizes); Tilburg CSAI news (winning Unicorn projects)
- Buenos Aires EEG artefact chapter; Frontiers Hum Neurosci 2021 volitional swallow EEG
- Nakanishi 2015 SSVEP benchmark; BR41N.IO SSVEP data-analysis write-up
- Hackathon Discord #announcements, #questions (read 11:30 Sat)
