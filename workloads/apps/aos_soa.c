/* Array-of-structs vs struct-of-arrays field sums.
 *   aos_soa <layout> <records> <fields_summed> <passes>
 * layout 0: AoS, each record is 8 doubles (one 64-byte line)
 * layout 1: SoA, 8 separate arrays of doubles
 * The ROI sums the first <fields_summed> fields (1..8) of every record,
 * <passes> times. With one field, AoS brings a full line per record into
 * the cache to use 8 bytes of it, while SoA uses every byte it fetches;
 * with all 8 fields both layouts touch the same bytes.
 */
#include "af.h"

#define NF 8
typedef struct { double f[NF]; } rec_t;

int main(int argc, char **argv) {
  int layout = (int)af_arg(argc, argv, 1, 0);
  long n = af_arg(argc, argv, 2, 1 << 16);
  int nf = (int)af_arg(argc, argv, 3, 1);
  long passes = af_arg(argc, argv, 4, 1);
  if (nf < 1 || nf > NF) { printf("FAIL fields\n"); return 1; }
  rec_t *aos = NULL;
  double *soa[NF] = {0};
  if (layout == 0) {
    aos = af_alloc((size_t)n * sizeof(rec_t));
    for (long i = 0; i < n; i++)
      for (int f = 0; f < NF; f++) aos[i].f[f] = (double)((i + f) % 16);
  } else {
    for (int f = 0; f < NF; f++) {
      soa[f] = af_alloc((size_t)n * sizeof(double));
      for (long i = 0; i < n; i++) soa[f][i] = (double)((i + f) % 16);
    }
  }

  double s = 0.0;
  af_roi_begin();
  for (long p = 0; p < passes; p++) {
    if (layout == 0) {
      for (long i = 0; i < n; i++)
        for (int f = 0; f < nf; f++) s += aos[i].f[f];
    } else {
      for (int f = 0; f < nf; f++) {
        const double *a = soa[f];
        for (long i = 0; i < n; i++) s += a[i];
      }
    }
    AF_SINKD(s);
  }
  af_roi_end();

  /* Values are small integers; the sum is exact in double below 2^53. */
  uint64_t want = 0;
  for (long i = 0; i < n; i++)
    for (int f = 0; f < nf; f++) want += (uint64_t)((i + f) % 16);
  want *= (uint64_t)passes;
  printf("aos_soa layout=%d records=%ld fields=%d passes=%ld\n", layout, n, nf, passes);
  return af_report("aos_soa", (uint64_t)s, want);
}
