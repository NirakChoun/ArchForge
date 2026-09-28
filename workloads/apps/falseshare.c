/* False-sharing microbenchmark for two cores.
 *   falseshare <layout> <iterations>
 * layout 0: the two threads' counters are adjacent 8-byte words of one
 *           64-byte line (false sharing)
 * layout 1: each counter sits in its own 64-byte line (padded)
 * The main thread and one worker each increment their own counter
 * <iterations> times through a volatile pointer, so every increment is a
 * load and a store to memory. With a shared line, every store needs the line
 * in the writer's cache in exclusive state, so the line moves between the
 * two private cache hierarchies. The ROI spans thread creation to join.
 * Build with -pthread; gem5 runs the two threads on two cores in SE mode.
 */
#include <pthread.h>

#include "af.h"

typedef struct {
  volatile uint64_t *ctr;
  long iters;
} arg_t;

static void *work(void *p) {
  arg_t *a = p;
  for (long i = 0; i < a->iters; i++) *a->ctr += 1;
  return NULL;
}

int main(int argc, char **argv) {
  int layout = (int)af_arg(argc, argv, 1, 0);
  long iters = af_arg(argc, argv, 2, 100000);
  /* Two lines, line-aligned: counters at offsets 0 and 8 (shared) or 0 and 64. */
  volatile uint64_t *buf = af_alloc(128);
  for (int i = 0; i < 16; i++) buf[i] = 0;
  arg_t a0 = {&buf[0], iters};
  arg_t a1 = {layout == 0 ? &buf[1] : &buf[8], iters};
  pthread_t t;

  af_roi_begin();
  if (pthread_create(&t, NULL, work, &a1) != 0) {
    printf("FAIL pthread_create\n");
    return 1;
  }
  work(&a0);
  pthread_join(t, NULL);
  af_roi_end();

  printf("falseshare layout=%d iters=%ld c0=%llu c1=%llu\n", layout, iters,
         (unsigned long long)*a0.ctr, (unsigned long long)*a1.ctr);
  return af_report("falseshare", *a0.ctr + *a1.ctr, 2 * (uint64_t)iters);
}
