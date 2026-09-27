/* Cache-conflict pattern at fixed capacity.
 *   conflict <lines> <spacing_bytes> <rounds>
 * Loads one word from each of <lines> cache lines placed <spacing_bytes>
 * apart, round-robin, <rounds> times. With spacing equal to a cache's
 * set-mapping period (size / associativity) all lines map to one set, so
 * once lines > associativity LRU replacement misses on every access even
 * though the footprint (lines x 64 B) is far below capacity. Spacing 64
 * spreads the same lines over consecutive sets as the control.
 */
#include <string.h>

#include "af.h"

int main(int argc, char **argv) {
  long lines = af_arg(argc, argv, 1, 16);
  long spacing = af_arg(argc, argv, 2, 4096);
  long rounds = af_arg(argc, argv, 3, 1 << 14);
  size_t words = (size_t)(lines * spacing / 8);
  uint64_t *a = af_alloc(words * 8);
  /* Touch every page in order so SE mode maps the region to consecutive
   * physical frames; set indices above the page offset then follow the
   * virtual spacing, which matters for L2 (set period above 4 KiB). */
  memset(a, 0, words * 8);
  size_t step = (size_t)spacing / 8;
  for (long l = 0; l < lines; l++) a[l * step] = (uint64_t)l + 1;
  for (long l = 0; l < lines; l++) AF_SINK(a[l * step]);

  uint64_t s = 0;
  af_roi_begin();
  for (long r = 0; r < rounds; r++) {
    for (long l = 0; l < lines; l++) s += a[l * step];
  }
  af_roi_end();
  AF_SINK(s);
  uint64_t want = (uint64_t)rounds * (uint64_t)lines * (uint64_t)(lines + 1) / 2;
  printf("conflict lines=%ld spacing=%ld rounds=%ld\n", lines, spacing, rounds);
  return af_report("conflict", s, want);
}
