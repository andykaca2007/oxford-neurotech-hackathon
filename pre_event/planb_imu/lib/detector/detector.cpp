#include "detector.h"

#include <math.h>

static float alpha_tau(float tau_s, float fs) { return 1.0f - expf(-1.0f / (tau_s * fs)); }
static float alpha_cut(float fc_hz, float fs) { return 1.0f - expf(-2.0f * 3.14159265f * fc_hz / fs); }

SwallowDetector::SwallowDetector(const DetectorConfig& cfg) : cfg_(cfg) {
  a_hp_ = alpha_tau(cfg_.hp_tau_s, cfg_.fs);
  a_env_ = alpha_cut(cfg_.env_cut_hz, cfg_.fs);
  a_base_ = alpha_tau(cfg_.base_tau_s, cfg_.fs);
  a_base_fast_ = alpha_tau(0.5f, cfg_.fs);
}

void SwallowDetector::recalibrate() {
  calibrating_ = true;
  started_ = false;
  active_ = false;
  pending_ = false;
  last_end_s_ = -1.0f;
}

bool SwallowDetector::push(float t, float ax, float ay, float az, float gyro_dps, Burst* out) {
  if (!started_) {
    started_ = true;
    t0_ = t;
    mx_ = ax; my_ = ay; mz_ = az;
    env_ = 0;
    base_ = cfg_.min_base_g;
  }

  // 1. Remove gravity and slow posture changes from each axis. The estimate is
  //    frozen during a burst; otherwise it follows the bump and overshoots
  //    afterwards, which shows up as a second, fake burst.
  if (!active_) {
    mx_ += a_hp_ * (ax - mx_);
    my_ += a_hp_ * (ay - my_);
    mz_ += a_hp_ * (az - mz_);
  }
  float hx = ax - mx_, hy = ay - my_, hz = az - mz_;

  // 2. Size of the movement, whatever the sensor's orientation.
  float mag = sqrtf(hx * hx + hy * hy + hz * hz);

  // 3. Smooth into an envelope.
  env_ += a_env_ * (mag - env_);

  // 4. Calibration: learn the quiet level while the wearer sits still.
  if (calibrating_) {
    base_ += a_base_fast_ * (env_ - base_);
    if (base_ < cfg_.min_base_g) base_ = cfg_.min_base_g;
    if (t - t0_ >= cfg_.calib_s) calibrating_ = false;
    return false;
  }

  bool decided = false;

  if (!active_) {
    if (env_ > cfg_.on_factor * base_) {
      active_ = true;
      cur_ = Burst{};
      cur_.start_s = t;
      cur_.peak = env_;
      cur_.gyro_peak_dps = gyro_dps;
      // A new burst starting closes the gap after the pending one.
      if (pending_) {
        pend_.gap_after_s = t - pend_.end_s;
        *out = pend_;
        pending_ = false;
        decided = true;
      }
    } else {
      // Only learn the quiet level while nothing is happening.
      base_ += a_base_ * (env_ - base_);
      if (base_ < cfg_.min_base_g) base_ = cfg_.min_base_g;
      if (pending_ && t - pend_.end_s >= cfg_.decide_after_s) {
        pend_.gap_after_s = t - pend_.end_s;
        *out = pend_;
        pending_ = false;
        decided = true;
      }
    }
  } else {
    if (env_ > cur_.peak) cur_.peak = env_;
    if (gyro_dps > cur_.gyro_peak_dps) cur_.gyro_peak_dps = gyro_dps;
    bool too_long = t - cur_.start_s > cfg_.max_burst_s;
    if (too_long) {
      // Probably a posture change, not a swallow: re-anchor gravity here.
      mx_ = ax; my_ = ay; mz_ = az;
      env_ = 0;
    }
    if (too_long || env_ < cfg_.off_factor * base_) {
      active_ = false;
      cur_.end_s = t;
      cur_.duration_s = cur_.end_s - cur_.start_s;
      cur_.centre_s = 0.5f * (cur_.start_s + cur_.end_s);
      if (cur_.duration_s >= cfg_.min_burst_s) {
        cur_.gap_before_s = last_end_s_ < 0 ? 1e9f : cur_.start_s - last_end_s_;
        last_end_s_ = cur_.end_s;
        pend_ = cur_;
        pending_ = true;
      }
    }
  }
  return decided;
}
