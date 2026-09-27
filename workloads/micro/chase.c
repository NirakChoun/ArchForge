/* Dependent pointer chase over randomized rings, with 1..8 independent chains.
 *   chase <footprint_bytes> <chains> <total_steps> [warm]
 * Each node fills one 64-byte line. The footprint is split evenly into
 * <chains> disjoint rings, each a single random cycle (Sattolo's algorithm),
 * so every load in a chain depends on the previous one while loads in
 * different chains are independent. chains=1 is the classic pointer chase;
 * chains>1 exposes memory-level parallelism. Total steps are fixed across
 * chain counts and rounded up to whole cycles so the checksum is exact.
 */
#include "af.h"

typedef struct node { struct node *next; uint64_t pad[7]; } node_t;

#define STEP1(k) p##k = p##k->next; s += (uint64_t)(p##k - base);

int main(int argc, char **argv) {
  size_t bytes = (size_t)af_arg(argc, argv, 1, 8 << 20);
  int chains = (int)af_arg(argc, argv, 2, 1);
  long total = af_arg(argc, argv, 3, 1 << 18);
  int warm = (int)af_arg(argc, argv, 4, 1);
  if (chains != 1 && chains != 2 && chains != 4 && chains != 8) {
    printf("FAIL chains must be 1,2,4,8\n");
    return 1;
  }
  size_t n = bytes / sizeof(node_t);
  size_t len = n / chains;           /* nodes per ring */
  node_t *base = af_alloc(len * chains * sizeof(node_t));
  size_t *perm = af_alloc(len * sizeof(size_t));
  uint64_t seed = 12345;
  for (int c = 0; c < chains; c++) {
    for (size_t i = 0; i < len; i++) perm[i] = i;
    for (size_t i = len - 1; i > 0; i--) {  /* Sattolo: one cycle */
      size_t j = af_lcg(&seed) % i;
      size_t t = perm[i]; perm[i] = perm[j]; perm[j] = t;
    }
    node_t *r = base + (size_t)c * len;
    for (size_t i = 0; i < len; i++) r[i].next = &r[perm[i]];
  }
  long per = (total / chains + (long)len - 1) / (long)len;  /* cycles per chain */
  long steps = per * (long)len;
  node_t *p0 = base, *p1 = base + len, *p2 = base + 2 * len, *p3 = base + 3 * len,
         *p4 = base + 4 * len, *p5 = base + 5 * len, *p6 = base + 6 * len,
         *p7 = base + 7 * len;
  uint64_t s = 0;
  if (warm) {  /* one untimed cycle per chain so cache-sized rings start warm */
    for (int c = 0; c < chains; c++) {
      node_t *q = base + (size_t)c * len;
      for (size_t i = 0; i < len; i++) q = q->next;
      AF_SINK(q);
    }
  }

  af_roi_begin();
  switch (chains) {
    case 1:
      for (long i = 0; i < steps; i++) { STEP1(0) }
      break;
    case 2:
      for (long i = 0; i < steps; i++) { STEP1(0) STEP1(1) }
      break;
    case 4:
      for (long i = 0; i < steps; i++) { STEP1(0) STEP1(1) STEP1(2) STEP1(3) }
      break;
    case 8:
      for (long i = 0; i < steps; i++) {
        STEP1(0) STEP1(1) STEP1(2) STEP1(3) STEP1(4) STEP1(5) STEP1(6) STEP1(7)
      }
      break;
  }
  af_roi_end();
  AF_SINK(s);

  /* Each full cycle of chain c visits indices c*len .. c*len+len-1 once. */
  uint64_t want = 0;
  for (int c = 0; c < chains; c++)
    want += (uint64_t)per * ((uint64_t)len * c * len + (uint64_t)len * (len - 1) / 2);
  printf("chase bytes=%zu chains=%d len=%zu steps_per_chain=%ld\n", bytes, chains,
         len, steps);
  return af_report("chase", s, want);
}
