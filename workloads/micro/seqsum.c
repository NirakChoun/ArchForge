/* Sequential sum over a uint64 array.
 *   seqsum <array_bytes> <total_elements>
 * The ROI sums the array repeatedly until total_elements loads are done, so
 * work is constant across array sizes and only locality changes. One
 * untimed warm-up pass precedes the ROI so small arrays start cache-resident.
 */
#include "af.h"

int main(int argc, char **argv) {
  size_t bytes = (size_t)af_arg(argc, argv, 1, 32768);
  long total = af_arg(argc, argv, 2, 1 << 20);
  size_t n = bytes / sizeof(uint64_t);
  long passes = total / (long)n;
  if (passes < 1) passes = 1;
  uint64_t *a = af_alloc(n * sizeof(uint64_t));
  for (size_t i = 0; i < n; i++) a[i] = i * 3 + 1;
  uint64_t s = 0;
  for (size_t i = 0; i < n; i++) s += a[i];
  AF_SINK(s);

  s = 0;
  af_roi_begin();
  for (long p = 0; p < passes; p++) {
    for (size_t i = 0; i < n; i++) s += a[i];
    AF_SINK(s);
  }
  af_roi_end();

  /* sum_{i<n} (3i+1) = 3n(n-1)/2 + n, times passes */
  uint64_t want = (uint64_t)passes * ((uint64_t)3 * n * (n - 1) / 2 + n);
  printf("seqsum bytes=%zu n=%zu passes=%ld\n", bytes, n, passes);
  return af_report("seqsum", s, want);
}
