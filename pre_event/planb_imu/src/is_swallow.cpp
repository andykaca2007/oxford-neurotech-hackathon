#include "is_swallow.h"

// TODO (yours, about 5 to 8 lines): the C++ twin of is_swallow() in
// warmup/swallow.py, now for throat MOVEMENT instead of chin EMG.
//
// You get one Burst (detector.h):
//   duration_s     how long the movement lasted (edges clipped, so shorter than real)
//   peak           how big it was, in g
//   gyro_peak_dps  fastest head rotation during it
//   gap_before_s   quiet before it (1e9 for the very first burst)
//   gap_after_s    quiet after it, CAPPED at 2 s
//
// What separates them on the throat:
//   swallow   one clear lift of the larynx, about 0.3 to 1 s, head still
//   talking   many small fast vibrations close together
//   chewing   jaw bursts repeating every ~0.7 s
//   nodding / turning the head   big gyro reading: the sensor moved, the larynx did not
//
// Decisions that are yours, and that you defend to the judges:
//   - the gyro limit. Too low rejects swallows taken while slightly moving;
//     too high lets head nods count as swallows (and silences the cue).
//   - the quiet rule. Your Python rule needed quiet on BOTH sides; here
//     gap_after never exceeds 2 s, so any limit above 2 s never passes.
//
// Tune it live: every burst prints a "B," line with all five numbers.
// Swallow ten times, talk for 20 s, nod ten times, and read the columns.
bool is_swallow(const Burst& b) {
  (void)b;
  return false;  // until you write it, nothing counts and the cue fires every T s
}
