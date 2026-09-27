/* Strided loads over a uint64 array.
 *   stride <array_bytes> <stride_elements> <total_loads>
 * Each sweep visits every stride-th element; sweeps start at successive
 * offsets (0, 1, ..., stride-1) so the whole array is covered before any
 * line is reused. Total loads are fixed, so only the access stride changes.
 */
#include "af.h"

int main(int argc, char **argv) {
  size_t bytes = (size_t)af_arg(argc, argv, 1, 8 << 20);
  size_t stride = (size_t)af_arg(argc, argv, 2, 1);
  long total = af_arg(argc, argv, 3, 1 << 20);
  size_t n = bytes / sizeof(uint64_t);
  uint64_t *a = af_alloc(n * sizeof(uint64_t));
  for (size_t i = 0; i < n; i++) a[i] = i;

  uint64_t s = 0, want = 0;
  long done = 0;
  size_t off = 0;
  af_roi_begin();
  while (done < total) {
    for (size_t i = off; i < n && done < total; i += stride, done++) s += a[i];
    off = (off + 1) % stride;
  }
  af_roi_end();
  AF_SINK(s);

  /* Reference: same index sequence, computed arithmetically (a[i] == i). */
  done = 0; off = 0;
  while (done < total) {
    for (size_t i = off; i < n && done < total; i += stride, done++) want += i;
    off = (off + 1) % stride;
  }
  printf("stride bytes=%zu stride=%zu loads=%ld\n", bytes, stride, total);
  return af_report("stride", s, want);
}
