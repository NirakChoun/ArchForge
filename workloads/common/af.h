/* ArchForge workload support: region-of-interest markers and self-check.
 *
 * The region of interest is bracketed by m5_reset_stats and m5_dump_stats,
 * so the first stats dump in stats.txt covers exactly the kernel and not
 * initialization. Build with -DAF_NATIVE to run on a real host (markers
 * become no-ops); used only for functional checks, never for results.
 */
#ifndef AF_H
#define AF_H

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#ifdef AF_NATIVE
static inline void af_roi_begin(void) {}
static inline void af_roi_end(void) {}
#else
#include <gem5/m5ops.h>
static inline void af_roi_begin(void) { m5_reset_stats(0, 0); }
static inline void af_roi_end(void) { m5_dump_stats(0, 0); }
#endif

/* Keeps a value observable so the kernel cannot be optimized away. */
#define AF_SINK(x) __asm__ volatile("" : : "r"(x) : "memory")
/* Same for a double held in an SSE register. */
#define AF_SINKD(x) __asm__ volatile("" : : "x"(x) : "memory")

static inline int af_report(const char *name, uint64_t got, uint64_t want) {
  int ok = got == want;
  printf("%s checksum=%llu expected=%llu\n", name, (unsigned long long)got,
         (unsigned long long)want);
  printf("%s\n", ok ? "PASS" : "FAIL");
  return ok ? 0 : 1;
}

/* Deterministic 64-bit LCG (Knuth MMIX constants); fixed seeds make every
 * input identical across runs and hardware configurations. */
static inline uint64_t af_lcg(uint64_t *s) {
  *s = *s * 6364136223846793005ULL + 1442695040888963407ULL;
  return *s >> 17;
}

static inline long af_arg(int argc, char **argv, int i, long dflt) {
  return argc > i ? strtol(argv[i], NULL, 0) : dflt;
}

static inline void *af_alloc(size_t bytes) {
  void *p = NULL;
  /* Page alignment keeps set mapping independent of malloc's layout. */
  if (posix_memalign(&p, 4096, bytes) != 0) {
    printf("FAIL alloc\n");
    exit(1);
  }
  return p;
}

#endif
