// Swallow burst finder for a throat-worn accelerometer.
//
// Same pipeline as warmup/swallow.py, with motion instead of EMG:
//   accel (3 axes) -> remove gravity and slow posture drift -> magnitude
//   -> smooth into an envelope -> burst = envelope above ON x quiet level.
//
// No Arduino code in here, so the native tests run it on a laptop.
#pragma once
#include <stdint.h>

struct Burst {
  float start_s;        // when the envelope crossed the ON threshold
  float end_s;          // when it fell below the OFF threshold
  float duration_s;     // end - start (shorter than the real movement: edges are clipped)
  float centre_s;
  float peak;           // highest envelope value, in g
  float gyro_peak_dps;  // fastest head rotation during the burst
  float gap_before_s;   // quiet time since the previous burst ended (1e9 if none)
  float gap_after_s;    // quiet time until the next burst; CAPPED at decide_after_s (2 s),
                        // so a rule needing more than 2 s of quiet after never fires
};

struct DetectorConfig {
  float fs = 200.0f;            // samples per second
  float hp_tau_s = 0.5f;        // gravity / posture removal time constant
  float env_cut_hz = 5.0f;      // envelope smoothing
  float base_tau_s = 10.0f;     // how fast the quiet level adapts
  float calib_s = 3.0f;         // sit still for this long after power-up
  float on_factor = 3.0f;       // burst starts above on_factor x quiet level
  float off_factor = 2.0f;      // and ends below off_factor x quiet level
  float min_burst_s = 0.08f;    // ignore shorter blips
  float max_burst_s = 3.0f;     // longer = posture change; burst is closed and gravity re-learnt
  float decide_after_s = 2.0f;  // wait this long after a burst to measure gap_after
  float min_base_g = 0.0005f;   // floor for the quiet level
};

class SwallowDetector {
 public:
  explicit SwallowDetector(const DetectorConfig& cfg = DetectorConfig());

  // Feed one sample: time in s, acceleration in g, gyro magnitude in deg/s.
  // Returns true when a burst has just been finalised (its gap_after is
  // known); the burst is written to *out.
  bool push(float t_s, float ax, float ay, float az, float gyro_dps, Burst* out);

  void recalibrate();
  bool calibrating() const { return calibrating_; }
  float envelope() const { return env_; }
  float threshold() const { return cfg_.on_factor * base_; }

 private:
  DetectorConfig cfg_;
  float a_hp_, a_env_, a_base_, a_base_fast_;
  bool started_ = false;
  bool calibrating_ = true;
  float t0_ = 0;
  float mx_ = 0, my_ = 0, mz_ = 0;  // slow means (gravity)
  float env_ = 0;
  float base_ = 0;
  bool active_ = false;
  Burst cur_{};
  bool pending_ = false;
  Burst pend_{};
  float last_end_s_ = -1.0f;
};

// When the wristband should buzz: T s after the last swallow, then every T s
// until the next one. Mirrors cue_times() in warmup/swallow.py.
class CueTimer {
 public:
  explicit CueTimer(float period_s = 30.0f) : T_(period_s) {}
  void start(float t_s) { next_ = t_s + T_; }
  void swallow(float t_s) { if (t_s + T_ > next_) next_ = t_s + T_; }
  // True once per cue.
  bool due(float t_s) {
    if (t_s < next_) return false;
    next_ += T_;
    return true;
  }
  void set_period(float T, float now_s) { T_ = T; next_ = now_s + T_; }
  float period() const { return T_; }

 private:
  float T_;
  float next_ = 1e9f;
};
