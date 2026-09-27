/* Quicksort of uint32 keys (contrast workload: branchy, data-dependent).
 *   sort <elements>
 * Median-of-three quicksort with an explicit stack and insertion sort for
 * short ranges, written here rather than calling libc qsort so the ROI has
 * no indirect comparator calls. The check verifies order and that the
 * multiset is preserved (sum and xor of keys).
 */
#include "af.h"

static void insertion(uint32_t *a, long lo, long hi) {
  for (long i = lo + 1; i <= hi; i++) {
    uint32_t v = a[i];
    long j = i - 1;
    while (j >= lo && a[j] > v) { a[j + 1] = a[j]; j--; }
    a[j + 1] = v;
  }
}

static void quicksort(uint32_t *a, long n) {
  long stack[128];
  int sp = 0;
  stack[sp++] = 0;
  stack[sp++] = n - 1;
  while (sp) {
    long hi = stack[--sp], lo = stack[--sp];
    while (hi - lo > 16) {
      long mid = lo + (hi - lo) / 2;
      uint32_t x = a[lo], y = a[mid], z = a[hi];
      uint32_t p = x < y ? (y < z ? y : (x < z ? z : x)) : (x < z ? x : (y < z ? z : y));
      long i = lo, j = hi;
      while (i <= j) {
        while (a[i] < p) i++;
        while (a[j] > p) j--;
        if (i <= j) { uint32_t t = a[i]; a[i] = a[j]; a[j] = t; i++; j--; }
      }
      /* Push the larger side, loop on the smaller: stack depth O(log n). */
      if (j - lo > hi - i) {
        stack[sp++] = lo; stack[sp++] = j; lo = i;
      } else {
        stack[sp++] = i; stack[sp++] = hi; hi = j;
      }
    }
    insertion(a, lo, hi);
  }
}

int main(int argc, char **argv) {
  long n = af_arg(argc, argv, 1, 1 << 16);
  uint32_t *a = af_alloc((size_t)n * sizeof(uint32_t));
  uint64_t seed = 2024, sum0 = 0, xor0 = 0;
  for (long i = 0; i < n; i++) {
    a[i] = (uint32_t)af_lcg(&seed);
    sum0 += a[i];
    xor0 ^= a[i];
  }
  af_roi_begin();
  quicksort(a, n);
  af_roi_end();
  uint64_t sum1 = 0, xor1 = 0, bad = 0;
  for (long i = 0; i < n; i++) {
    sum1 += a[i];
    xor1 ^= a[i];
    if (i && a[i - 1] > a[i]) bad++;
  }
  printf("sort n=%ld out_of_order=%llu\n", n, (unsigned long long)bad);
  return af_report("sort", (sum1 ^ (xor1 << 32)) + bad, sum0 ^ (xor0 << 32));
}
