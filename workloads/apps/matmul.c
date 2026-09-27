/* Matrix multiply C = A * B, double precision, row-major, N x N.
 *   matmul <variant> <N> [tile] [rows]
 * variant 0: naive ijk      (inner loop strides down a column of B)
 * variant 1: interchanged ikj (inner loop streams rows of B and C)
 * variant 2: tiled ikj with a square tile of <tile> elements; the tile loops
 *            are ii, kk, jj so one T x T block of B is reused across T rows.
 * rows (default N) limits the computation to the first <rows> rows of C,
 * i.e. an R x N x N product that still reads all of B. For the tiled kernel
 * the work is rows/tile whole ii blocks, each identical in access pattern
 * to a block of the full product, so a band shrinks simulation time
 * without changing the per-block reuse that tiling exploits.
 * Inputs are small integers, so every partial sum is exactly representable
 * in double and all variants produce bit-identical C regardless of
 * summation order. C is checked with two O(N^2) checksums: the plain sum
 * and a separable weighted sum w^T C v = (w^T A)(B v).
 */
#include "af.h"

static void mm_ijk(int n, int r, const double *A, const double *B, double *C) {
  for (int i = 0; i < r; i++)
    for (int j = 0; j < n; j++) {
      double s = C[(size_t)i * n + j];
      for (int k = 0; k < n; k++) s += A[(size_t)i * n + k] * B[(size_t)k * n + j];
      C[(size_t)i * n + j] = s;
    }
}

static void mm_ikj(int n, int r, const double *A, const double *B, double *C) {
  for (int i = 0; i < r; i++)
    for (int k = 0; k < n; k++) {
      double a = A[(size_t)i * n + k];
      const double *b = B + (size_t)k * n;
      double *c = C + (size_t)i * n;
      for (int j = 0; j < n; j++) c[j] += a * b[j];
    }
}

static void mm_tiled(int n, int r, int t, const double *A, const double *B,
                     double *C) {
  for (int ii = 0; ii < r; ii += t) {
    int ie = ii + t < r ? ii + t : r;
    for (int kk = 0; kk < n; kk += t) {
      int ke = kk + t < n ? kk + t : n;
      for (int jj = 0; jj < n; jj += t) {
        int je = jj + t < n ? jj + t : n;
        for (int i = ii; i < ie; i++)
          for (int k = kk; k < ke; k++) {
            double a = A[(size_t)i * n + k];
            const double *b = B + (size_t)k * n;
            double *c = C + (size_t)i * n;
            for (int j = jj; j < je; j++) c[j] += a * b[j];
          }
      }
    }
  }
}

int main(int argc, char **argv) {
  int variant = (int)af_arg(argc, argv, 1, 1);
  int n = (int)af_arg(argc, argv, 2, 128);
  int t = (int)af_arg(argc, argv, 3, 32);
  int r = (int)af_arg(argc, argv, 4, n);
  if (r < 1 || r > n) { printf("FAIL rows\n"); return 1; }
  size_t nn = (size_t)n * n;
  double *A = af_alloc(nn * sizeof(double));
  double *B = af_alloc(nn * sizeof(double));
  double *C = af_alloc(nn * sizeof(double));
  uint64_t seed = 42;
  for (size_t i = 0; i < nn; i++) A[i] = (double)(af_lcg(&seed) % 8);
  for (size_t i = 0; i < nn; i++) B[i] = (double)(af_lcg(&seed) % 8);
  for (size_t i = 0; i < nn; i++) C[i] = 0.0;

  af_roi_begin();
  if (variant == 0) mm_ijk(n, r, A, B, C);
  else if (variant == 1) mm_ikj(n, r, A, B, C);
  else mm_tiled(n, r, t, A, B, C);
  af_roi_end();

  /* Weights w_i = i%5+1, v_j = j%7+1; all quantities are exact integers. */
  uint64_t sum = 0, wsum = 0;
  for (int i = 0; i < n; i++)
    for (int j = 0; j < n; j++) {
      uint64_t c = (uint64_t)C[(size_t)i * n + j];
      sum += c;
      wsum += c * (uint64_t)(i % 5 + 1) * (uint64_t)(j % 7 + 1);
    }
  uint64_t want_sum = 0, want_w = 0;
  for (int k = 0; k < n; k++) {
    uint64_t colA = 0, colAw = 0, rowB = 0, rowBv = 0;
    for (int i = 0; i < r; i++) {  /* rows of C beyond r stay zero */
      uint64_t a = (uint64_t)A[(size_t)i * n + k];
      colA += a;
      colAw += a * (uint64_t)(i % 5 + 1);
    }
    for (int j = 0; j < n; j++) {
      uint64_t b = (uint64_t)B[(size_t)k * n + j];
      rowB += b;
      rowBv += b * (uint64_t)(j % 7 + 1);
    }
    want_sum += colA * rowB;
    want_w += colAw * rowBv;
  }
  printf("matmul variant=%d n=%d tile=%d rows=%d\n", variant, n, t, r);
  return af_report("matmul", sum ^ (wsum << 1), want_sum ^ (want_w << 1));
}
