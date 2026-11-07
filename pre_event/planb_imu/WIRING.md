# SwallowCue Plan B: wiring and first test

Use this if the event gives you no EMG kit. Everything here is already yours:
ESP32 DevKit + PN2222 + diode from the ELEGOO kit, GY-521 (or the kit's GY-6500),
coin motor from the Amazon order, breadboard and jumpers.

## Wiring

| From | To | Note |
|---|---|---|
| GY-521 VCC | ESP32 3V3 | |
| GY-521 GND | ESP32 GND | |
| GY-521 SDA | ESP32 GPIO 21 | |
| GY-521 SCL | ESP32 GPIO 22 | |
| GY-521 AD0 | leave open or GND | address 0x68 |
| ESP32 GPIO 25 | 1 kOhm | then to PN2222 **base** (middle leg) |
| PN2222 **emitter** | GND | flat face towards you: E, B, C left to right |
| PN2222 **collector** | coin motor black (-) | |
| coin motor red (+) | ESP32 3V3 | |
| diode across the motor | stripe (cathode) to 3V3, other end to collector | stops the motor's voltage spike hitting the transistor |

Check the PN2222 pin order on the kit's datasheet card before powering: some
TO-92 parts are C, B, E. Motor current is about 63 mA, well inside the 3V3 pin's limit.

Use 4 long, soft jumpers (30 cm or more) from the breadboard to the GY-521, twisted
together, so the sensor can sit on the throat while the board stays on the table.

## Where the sensor goes

Flat on the front of the neck, just below the Adam's apple (thyroid cartilage),
held with medical tape or a loose elastic band. Chip side out, wires running
down to the collar. Too tight and swallowing feels odd; too loose and talking
makes the sensor rattle.

## First test (10 minutes)

1. `pio_build`, `pio_devices`, `pio_upload` (I can do these when the board is plugged in).
2. Open the live view from the hackathon folder: `uv run tools/live_plot.py <port> --log s1.csv` (press Enter after each swallow).
3. Sit still for 3 s while it calibrates.
4. In the same terminal type `b` + Enter: the motor should buzz (a blank Enter is a swallow mark).
5. Swallow 10 times, a few seconds apart. Then talk for 20 s. Then nod 10 times.
   Copy the `B,` lines: columns are time, duration, peak, gyro, gap before, gap after.
6. Write `is_swallow()` in `src/is_swallow.cpp` from those numbers. Re-upload.
7. Demo setting: type `t15` + Enter to buzz after 15 s with no swallow.

## Demo script (30 s)

- Talk: grey bands, counter stays.
- Sip of water: green band, counter +1, timer resets.
- Nod: grey (gyro rejects it).
- Hold still and don't swallow: red line, wristband buzzes at 15 s.
- Swallow: timer resets.

## What we can claim

Detects swallows from throat movement in a healthy volunteer and cues when
swallowing pauses. Never "reduces drooling": nobody with Parkinson's has worn it.
Throat accelerometry for swallowing is an established research method
(swallowing accelerometry, mainly for dysphagia screening), so present it as a
cheap, open take on that, not a first.
