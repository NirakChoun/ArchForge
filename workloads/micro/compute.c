/* Compute-bound loop: four independent 64-bit LCG recurrences in registers.
 *   compute <iterations>
 * No loads or stores inside the loop. Each recurrence is a multiply-add
 * chain, so the loop exposes execution latency and issue width, not memory.
 * The result is checked with the closed-form LCG jump, which costs O(log n).
 */
#include "af.h"

#define A 6364136223846793005ULL
#define C 1442695040888963407ULL

static uint64_t jump(uint64_t x, uint64_t n) {
  uint64_t am = 1, ap = 0, cm = A, cp = C;
  while (n) {
    if (n & 1) { am *= cm; ap = ap * cm + cp; }
    cp = (cm + 1) * cp;
    cm *= cm;
    n >>= 1;
  }
  return am * x + ap;
}

int main(int argc, char **argv) {
  long iters = af_arg(argc, argv, 1, 1 << 20);
  uint64_t x0 = 1, x1 = 2, x2 = 3, x3 = 4;
  af_roi_begin();
  for (long i = 0; i < iters; i++) {
    x0 = x0 * A + C;
    x1 = x1 * A + C;
    x2 = x2 * A + C;
    x3 = x3 * A + C;
  }
  af_roi_end();
  uint64_t s = x0 ^ (x1 << 1) ^ (x2 << 2) ^ (x3 << 3);
  AF_SINK(s);
  uint64_t want = jump(1, iters) ^ (jump(2, iters) << 1) ^ (jump(3, iters) << 2) ^
                  (jump(4, iters) << 3);
  printf("compute iters=%ld\n", iters);
  return af_report("compute", s, want);
}
