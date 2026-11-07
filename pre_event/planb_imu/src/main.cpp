// SwallowCue Plan B: count swallows from a motion sensor on the throat and
// buzz a coin motor when no swallow has happened for T seconds.
//
// Hardware (see WIRING.md): ESP32 DevKit + GY-521 (MPU-6050) or GY-6500
// over I2C, coin vibration motor switched by a PN2222 with a flyback diode.
//
// Serial, 115200 baud. Lines it prints:
//   S,t,envelope,threshold          50 times a second (for live_plot.py)
//   B,t,dur,peak,gyro,gap_b,gap_a,verdict   one per burst
//   C,t                              a cue (buzz)
//   #...                             human notes
// Commands you can type (end with Enter):
//   r     recalibrate (sit still for 3 s)
//   t15   set the cue period to 15 s
//   b     test buzz
//   e     switch to EMG-ENVELOPE mode: an analog muscle sensor (MyoWare-style
//         ENV output, powered from 3V3) on GPIO 34 replaces the IMU
//   i     back to IMU mode
#include <Arduino.h>
#include <Wire.h>

#include "detector.h"
#include "is_swallow.h"

// ---- pins (ESP32 DevKit) ----
static const int PIN_SDA = 21;
static const int PIN_SCL = 22;
static const int PIN_MOTOR = 25;   // to the PN2222 base through 1 kOhm
static const int PIN_EMG_ENV = 34; // analog envelope input (input-only pin, 0 to 3.3 V)

// ---- settings ----
static const float FS = 200.0f;          // samples per second
static float cue_period_s = 15.0f;       // short for the demo; real use ~30 to 60 s
static const uint32_t BUZZ_MS = 400;

static const uint8_t IMU_ADDR = 0x68;    // AD0 low

SwallowDetector detector;
CueTimer cue(cue_period_s);
static uint32_t motor_off_ms = 0;
static uint32_t swallows = 0;
static bool imu_ok = false;
static bool adc_mode = false;      // true: GPIO 34 envelope instead of the IMU

static void imu_write(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(IMU_ADDR);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

static bool imu_init() {
  Wire.beginTransmission(IMU_ADDR);
  Wire.write(0x75);  // WHO_AM_I
  if (Wire.endTransmission(false) != 0) return false;
  Wire.requestFrom(IMU_ADDR, (uint8_t)1);
  if (!Wire.available()) return false;
  uint8_t who = Wire.read();
  Serial.printf("# IMU WHO_AM_I = 0x%02X (0x68 MPU-6050, 0x70 MPU-6500)\n", who);
  imu_write(0x6B, 0x01);  // wake up, PLL clock
  delay(50);
  imu_write(0x1A, 0x03);  // digital low-pass ~44 Hz
  imu_write(0x19, 0x04);  // sample rate 1 kHz / 5 = 200 Hz
  imu_write(0x1B, 0x00);  // gyro +-250 deg/s
  imu_write(0x1C, 0x00);  // accel +-2 g
  return true;
}

static bool imu_read(float* ax, float* ay, float* az, float* gyro_dps) {
  Wire.beginTransmission(IMU_ADDR);
  Wire.write(0x3B);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(IMU_ADDR, (uint8_t)14) != 14) return false;
  int16_t r[7];
  for (int i = 0; i < 7; i++) r[i] = (int16_t)((Wire.read() << 8) | Wire.read());
  *ax = r[0] / 16384.0f;
  *ay = r[1] / 16384.0f;
  *az = r[2] / 16384.0f;
  float gx = r[4] / 131.0f, gy = r[5] / 131.0f, gz = r[6] / 131.0f;  // r[3] is temperature
  *gyro_dps = sqrtf(gx * gx + gy * gy + gz * gz);
  return true;
}

static void buzz(uint32_t now_ms) {
  digitalWrite(PIN_MOTOR, HIGH);
  motor_off_ms = now_ms + BUZZ_MS;
}

static void handle_serial(float t) {
  static char line[16];
  static uint8_t n = 0;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      line[n] = 0;
      if (n > 0) {
        if (line[0] == 'r') {
          detector.recalibrate();
          Serial.println("# recalibrating: sit still for 3 s");
        } else if (line[0] == 't') {
          float T = atof(line + 1);
          if (T >= 3.0f) {
            cue_period_s = T;
            cue.set_period(T, t);
            Serial.printf("# cue period = %.0f s\n", T);
          }
        } else if (line[0] == 'b') {
          buzz(millis());
        } else if (line[0] == 'e') {
          adc_mode = true;
          detector.recalibrate();
          cue.start(t + 3.0f);
          Serial.println("# EMG-envelope mode on GPIO 34: relax your chin for 3 s");
        } else if (line[0] == 'i' && imu_ok) {
          adc_mode = false;
          detector.recalibrate();
          cue.start(t + 3.0f);
          Serial.println("# IMU mode: sit still for 3 s");
        }
      }
      n = 0;
    } else if (n < sizeof(line) - 1) {
      line[n++] = c;
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_MOTOR, OUTPUT);
  digitalWrite(PIN_MOTOR, LOW);
  Wire.begin(PIN_SDA, PIN_SCL, 400000);
  delay(200);
  for (int tries = 0; tries < 3 && !(imu_ok = imu_init()); tries++) {
    Serial.println("# no IMU at 0x68: check SDA=21, SCL=22, VCC=3V3, GND");
    delay(1000);
  }
  if (imu_ok) {
    Serial.println("# SwallowCue Plan B. Sit still for 3 s to calibrate.");
    cue.start(millis() / 1000.0f + 3.0f);
  } else {
    // EMG path: the laptop decides, this board is only the wristband.
    Serial.println("# no IMU: WRISTBAND-ONLY mode. 'b' + Enter buzzes; 'e' + Enter reads an EMG envelope on GPIO 34.");
  }
}

void loop() {
  static uint32_t next_us = micros();
  static uint32_t k = 0;
  const uint32_t period_us = (uint32_t)(1e6f / FS);

  if ((int32_t)(micros() - next_us) < 0) return;
  next_us += period_us;

  uint32_t now_ms = millis();
  float t = now_ms / 1000.0f;
  handle_serial(t);

  if (motor_off_ms && (int32_t)(now_ms - motor_off_ms) >= 0) {
    digitalWrite(PIN_MOTOR, LOW);
    motor_off_ms = 0;
  }

  float ax, ay, az, g;
  if (adc_mode) {
    // An envelope in volts goes in as one 'axis'. The detector removes its
    // resting level the same way it removes gravity, so the rest is shared.
    ax = analogReadMilliVolts(PIN_EMG_ENV) / 1000.0f;
    ay = az = 0.0f;
    g = 0.0f;
  } else {
    if (!imu_ok) return;  // wristband-only mode
    if (!imu_read(&ax, &ay, &az, &g)) return;
  }

  Burst b;
  if (detector.push(t, ax, ay, az, g, &b)) {
    bool sw = is_swallow(b);
    Serial.printf("B,%.2f,%.2f,%.4f,%.0f,%.2f,%.2f,%s\n", b.centre_s, b.duration_s, b.peak,
                  b.gyro_peak_dps, b.gap_before_s > 1e8f ? -1.0f : b.gap_before_s,
                  b.gap_after_s, sw ? "SWALLOW" : "other");
    if (sw) {
      swallows++;
      cue.swallow(b.centre_s);
      Serial.printf("# swallow %lu\n", (unsigned long)swallows);
    }
  }

  if (!detector.calibrating() && cue.due(t)) {
    buzz(now_ms);
    Serial.printf("C,%.2f\n", t);
  }

  if (++k % 4 == 0) {
    Serial.printf("S,%.2f,%.5f,%.5f\n", t, detector.envelope(), detector.threshold());
  }
}
