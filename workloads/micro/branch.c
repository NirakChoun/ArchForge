/* Branch-pattern microbenchmark.
 *   branch <pattern> <n>
 * pattern: 0 always taken, 1 alternating, 2 random, 3 data-dependent sorted.
 * Every pattern runs the same loop over a byte array d[] and branches on
 * d[i] < 128, so instruction mix and memory behaviour are identical; only
 * the outcome sequence differs. Pattern 2 is random bytes (the branch
 * depends on unpredictable data); pattern 3 is the same bytes sorted, so the
 * same data-dependent branch becomes one long run of taken then not-taken.
 */
#include "af.h"

int main(int argc, char **argv) {
  int pat = (int)af_arg(argc, argv, 1, 0);
  long n = af_arg(argc, argv, 2, 1 << 20);
  uint8_t *d = af_alloc((size_t)n);
  uint64_t seed = 777;
  for (long i = 0; i < n; i++) {
    switch (pat) {
      case 0: d[i] = 0; break;
      case 1: d[i] = (i & 1) ? 255 : 0; break;
      default: d[i] = (uint8_t)af_lcg(&seed); break;
    }
  }
  if (pat == 3) {  /* counting sort keeps the byte multiset identical to pattern 2 */
    long cnt[256] = {0};
    for (long i = 0; i < n; i++) cnt[d[i]]++;
    long k = 0;
    for (int v = 0; v < 256; v++)
      for (long j = 0; j < cnt[v]; j++) d[k++] = (uint8_t)v;
  }
  for (long i = 0; i < n; i++) AF_SINK(d[i]);  /* touch: warms caches, TLB */

  uint64_t s = 0;
  af_roi_begin();
  for (long i = 0; i < n; i++) {
    if (d[i] < 128) {
      s += d[i];
      /* An asm barrier on one side stops gcc from if-converting to cmov,
       * which would remove the branch under study. */
      __asm__ volatile("" ::: "memory");
    } else {
      s ^= (uint64_t)i;
    }
  }
  af_roi_end();
  AF_SINK(s);

  uint64_t want = 0;
  for (long i = 0; i < n; i++) want = d[i] < 128 ? want + d[i] : want ^ (uint64_t)i;
  printf("branch pattern=%d n=%ld\n", pat, n);
  return af_report("branch", s, want);
}
