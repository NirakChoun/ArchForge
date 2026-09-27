/* Integer reduction: sum of a uint32 array, modulo 2^32.
 *   reduce <elements> <passes>
 * Contrast workload with a single streaming read and one loop-carried
 * dependence. At -O3 gcc vectorizes it with SSE2 (paddd), which is what
 * the Stage 7 compiler-flag study looks for; at -O2 it stays scalar.
 */
#include "af.h"

/* noipa: without it gcc proves the call pure and hoists it out of the
 * passes loop, which would remove all but one pass from the ROI. */
__attribute__((noipa)) static uint32_t kernel(const uint32_t *a, long n) {
  uint32_t s = 0;
  for (long i = 0; i < n; i++) s += a[i];
  return s;
}

int main(int argc, char **argv) {
  long n = af_arg(argc, argv, 1, 1 << 20);
  long passes = af_arg(argc, argv, 2, 1);
  uint32_t *a = af_alloc((size_t)n * sizeof(uint32_t));
  uint64_t seed = 99;
  for (long i = 0; i < n; i++) a[i] = (uint32_t)af_lcg(&seed);
  uint32_t want1 = 0;
  for (long i = 0; i < n; i++) want1 += a[i];  /* also warms the array */

  uint32_t s = 0;
  af_roi_begin();
  for (long p = 0; p < passes; p++) s += kernel(a, n);
  af_roi_end();
  AF_SINK(s);
  printf("reduce n=%ld passes=%ld\n", n, passes);
  return af_report("reduce", s, (uint32_t)(want1 * (uint32_t)passes));
}
