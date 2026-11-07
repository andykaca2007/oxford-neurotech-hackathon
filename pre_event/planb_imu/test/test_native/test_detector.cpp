// Runs on the laptop: pio_test env=native
#include <math.h>
#include <unity.h>

#include <vector>

#include "detector.h"

static const float FS = 200.0f;

// Small deterministic noise source (no <random> differences between compilers).
static uint32_t seed = 12345;
static float noise() {
  seed = seed * 1664525u + 1013904223u;
  return ((seed >> 8) / 16777216.0f) * 2.0f - 1.0f;  // -1 to 1
}

// Fake throat recording: gravity on z, sensor noise, and a smooth bump
// (larynx going up and back down) for each (start, length) in bumps.
static std::vector<Burst> run(float seconds, const std::vector<std::pair<float, float>>& bumps,
                              float amp_g = 0.05f) {
  SwallowDetector d;
  std::vector<Burst> found;
  int n = (int)(seconds * FS);
  for (int i = 0; i < n; i++) {
    float t = i / FS;
    float ax = 0.004f * noise(), ay = 0.004f * noise(), az = 1.0f + 0.004f * noise();
    for (auto& b : bumps) {
      if (t >= b.first && t < b.first + b.second) {
        float s = sinf(3.14159265f * (t - b.first) / b.second);
        ax += amp_g * s;
        ay += 0.5f * amp_g * s;
      }
    }
    Burst out;
    if (d.push(t, ax, ay, az, 2.0f, &out)) found.push_back(out);
  }
  return found;
}

void test_quiet_recording_has_no_bursts() {
  auto b = run(20.0f, {});
  TEST_ASSERT_EQUAL_INT(0, (int)b.size());
}

void test_one_swallow_is_one_burst() {
  auto b = run(20.0f, {{10.0f, 0.8f}});
  TEST_ASSERT_EQUAL_INT(1, (int)b.size());
  TEST_ASSERT_TRUE(b[0].centre_s > 9.8f && b[0].centre_s < 11.0f);
  TEST_ASSERT_TRUE(b[0].duration_s > 0.1f && b[0].duration_s < 1.5f);
  TEST_ASSERT_TRUE(b[0].gap_after_s >= 2.0f);
  TEST_ASSERT_TRUE(b[0].gap_before_s > 1e8f);  // first burst: nothing before it
}

void test_gaps_between_two_bursts() {
  auto b = run(30.0f, {{10.0f, 0.8f}, {16.0f, 0.8f}});
  TEST_ASSERT_EQUAL_INT(2, (int)b.size());
  // 5 s apart: gap_after stops counting at decide_after_s (2 s) so the first
  // burst is not held back; gap_before of the second sees the full gap.
  TEST_ASSERT_FLOAT_WITHIN(0.05f, 2.0f, b[0].gap_after_s);
  TEST_ASSERT_FLOAT_WITHIN(1.0f, 5.2f, b[1].gap_before_s);
}

void test_close_bursts_measure_the_real_gap() {
  // Chewing-like: bursts 1.2 s apart, so gap_after is measured, not capped.
  auto b = run(30.0f, {{10.0f, 0.6f}, {11.8f, 0.6f}, {13.6f, 0.6f}});
  TEST_ASSERT_EQUAL_INT(3, (int)b.size());
  TEST_ASSERT_TRUE(b[0].gap_after_s < 2.0f);
  TEST_ASSERT_FLOAT_WITHIN(0.01f, b[0].gap_after_s, b[1].gap_before_s);
}

void test_cue_timer_matches_python() {
  // cue_times([10], seconds=100, T=30) == [40, 70] in warmup/swallow.py
  CueTimer c(30.0f);
  c.start(0.0f);
  std::vector<float> cues;
  for (int i = 0; i <= 1000; i++) {
    float t = i * 0.1f;
    if (fabsf(t - 10.0f) < 1e-3f) c.swallow(t);
    if (c.due(t)) cues.push_back(t);
  }
  TEST_ASSERT_EQUAL_INT(3, (int)cues.size());  // 40, 70 and 100
  TEST_ASSERT_FLOAT_WITHIN(0.11f, 40.0f, cues[0]);
  TEST_ASSERT_FLOAT_WITHIN(0.11f, 70.0f, cues[1]);
}

void test_regular_swallows_never_cue() {
  // cue_times([10, 20, 30], seconds=60, T=30) == []
  CueTimer c(30.0f);
  c.start(0.0f);
  int cues = 0;
  for (int i = 0; i < 600; i++) {
    float t = i * 0.1f;
    if (i == 100 || i == 200 || i == 300) c.swallow(t);
    if (c.due(t)) cues++;
  }
  TEST_ASSERT_EQUAL_INT(0, cues);
}

int main() {
  UNITY_BEGIN();
  RUN_TEST(test_quiet_recording_has_no_bursts);
  RUN_TEST(test_one_swallow_is_one_burst);
  RUN_TEST(test_gaps_between_two_bursts);
  RUN_TEST(test_close_bursts_measure_the_real_gap);
  RUN_TEST(test_cue_timer_matches_python);
  RUN_TEST(test_regular_swallows_never_cue);
  return UNITY_END();
}
