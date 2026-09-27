/* Harness for a TensorForge-generated single-precision matmul kernel.
 *   tf_matmul_<cfg>  (N fixed at kernel compile time, AF_TF_N)
 * The kernel object comes from TensorForge's CPU pipeline (tensorforge-opt
 * --tforge-cpu-pipeline, mlir-translate, opt -O3, llc -O3 -mcpu=x86-64),
 * built by scripts/build_tf_kernels.sh. Its C interface is
 * _mlir_ciface_entry(A, B, out) over rank-2 memref descriptors; the pipeline
 * turns the result into an out-parameter and zero-fills it itself.
 * Inputs are small integers, so every f32 partial sum is exact (N * 49 is
 * far below 2^24) and the same two O(N^2) checksums as matmul.c apply.
 */
#include <string.h>

#include "af.h"

#ifndef AF_TF_N
#error "AF_TF_N must be defined"
#endif
#define N AF_TF_N

typedef struct {
  float *allocated, *aligned;
  int64_t offset, sizes[2], strides[2];
} memref2d_t;

void _mlir_ciface_entry(memref2d_t *a, memref2d_t *b, memref2d_t *out);

/* Allocation hooks the kernel calls for temporaries (generic memref lowering). */
void *_mlir_memref_to_llvm_alloc(size_t size) { return malloc(size); }
void *_mlir_memref_to_llvm_aligned_alloc(size_t alignment, size_t size) {
  void *p = NULL;
  if (alignment < sizeof(void *)) alignment = sizeof(void *);
  return posix_memalign(&p, alignment, size) == 0 ? p : NULL;
}
void _mlir_memref_to_llvm_free(void *ptr) { free(ptr); }

static memref2d_t desc(float *p) {
  memref2d_t d = {p, p, 0, {N, N}, {N, 1}};
  return d;
}

int main(void) {
  size_t nn = (size_t)N * N;
  float *A = af_alloc(nn * sizeof(float));
  float *B = af_alloc(nn * sizeof(float));
  float *C = af_alloc(nn * sizeof(float));
  uint64_t seed = 42;
  for (size_t i = 0; i < nn; i++) A[i] = (float)(af_lcg(&seed) % 8);
  for (size_t i = 0; i < nn; i++) B[i] = (float)(af_lcg(&seed) % 8);
  memset(C, 0xff, nn * sizeof(float));  /* the kernel must overwrite all of C */
  memref2d_t a = desc(A), b = desc(B), c = desc(C);

  af_roi_begin();
  _mlir_ciface_entry(&a, &b, &c);
  af_roi_end();

  uint64_t sum = 0, wsum = 0;
  for (int i = 0; i < N; i++)
    for (int j = 0; j < N; j++) {
      uint64_t v = (uint64_t)C[(size_t)i * N + j];
      sum += v;
      wsum += v * (uint64_t)(i % 5 + 1) * (uint64_t)(j % 7 + 1);
    }
  uint64_t want_sum = 0, want_w = 0;
  for (int k = 0; k < N; k++) {
    uint64_t colA = 0, colAw = 0, rowB = 0, rowBv = 0;
    for (int i = 0; i < N; i++) {
      uint64_t x = (uint64_t)A[(size_t)i * N + k];
      colA += x;
      colAw += x * (uint64_t)(i % 5 + 1);
    }
    for (int j = 0; j < N; j++) {
      uint64_t y = (uint64_t)B[(size_t)k * N + j];
      rowB += y;
      rowBv += y * (uint64_t)(j % 7 + 1);
    }
    want_sum += colA * rowB;
    want_w += colAw * rowBv;
  }
  printf("tf_matmul n=%d\n", N);
  return af_report("tf_matmul", sum ^ (wsum << 1), want_sum ^ (want_w << 1));
}
