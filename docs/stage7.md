# Stage 7: compiler-generated variants

Results pending. Predictions below were written before any Stage 7 simulation ran.

All code stays within gem5's X86 model: no AVX. gcc builds use `-march=x86-64`; TensorForge kernels use `llc -mcpu=x86-64`. `scripts/check_no_avx.sh` and `scripts/build_tf_kernels.sh` verify zero `ymm`/`zmm` uses in every workload object and kernel.

## Study: gcc optimization level

Question: how do `-O1`, `-O2`, `-O3`, and `-O3 -fno-tree-vectorize` change instruction count and memory behaviour for matrix multiply (untiled ikj and tiled 32, a 128-row band of an N = 320 product; the full product took 25 minutes at -O2 in Stage 5, too close to the 30-minute limit for -O1) and the reduction?
Suspected mechanism: at `-O3`, gcc 11 vectorizes the ikj inner loop (`c[j] += a * b[j]`) with SSE2 `mulpd`/`addpd` (2 doubles per instruction) and the reduction with `paddd` (4 integers per instruction); `-O2` in gcc 11 does not vectorize. `-O1` keeps more loads and stores in the loop.
Evidence before running: `objdump` shows `mulpd` in `matmul_O3` and none in `matmul_O2`; `paddd` in the `-O3` reduction kernel and none in `-O3 -fno-tree-vectorize`.
Hypothesis and prediction: `-O3` cuts ROI instructions roughly in half for the vectorized loops (fewer for matmul, whose loop overhead is shared). Cycles fall less than instructions for untiled matmul (memory-bound beyond L2) and for the reduction over 4 MiB (DRAM-bound), and more for tiled 32 (L1-resident inner loops). L1D and L2 line misses and DRAM bytes are nearly unchanged across flags, since vectorization changes how many instructions touch each line, not which lines. `-O3 -fno-tree-vectorize` lands close to `-O2`.
Independent variable: flag set. Controlled: source, inputs, baseline hardware.

## Study: TensorForge kernels on the Stage 6 hardware grid

Question: do TensorForge's CPU-pipeline configurations (scalar, cache-tiled 32, register-tiled and vectorized, both), compiled for SSE2, interact with L1D and L2 capacity the way the hand-written tiled kernels do?
Feasibility: TensorForge's pipeline is target-independent until `llc`; its own backend uses `-mcpu=native` (AVX2 and FMA on Hive). `scripts/build_tf_kernels.sh` runs the unchanged `tensorforge-opt --tforge-cpu-pipeline`, `mlir-translate`, and `opt -O3`, then `llc -O3 -mcpu=x86-64`, and links the object into `workloads/apps/tf_matmul.c`. Kernels are f32 (TensorForge's only element type); N = 320 (1.2 MiB of matrices). All four configurations passed a native functional check at N = 64 and contain no AVX.
Hypothesis and prediction: the vectorized register-tiled kernels (6 x 16 outputs kept in 24 `xmm` registers, 4 floats each) execute several times fewer instructions and cycles than scalar. The scalar untiled kernel is sensitive to L2 capacity (B is 400 KiB); cache tiling (32 x 32) reduces that sensitivity. The register-tiled kernel without cache tiles streams B panels and is sensitive to L2 below 512 KiB.
Independent variables: configuration x L1D {16, 32, 64 KiB} x L2 {256 KiB, 512 KiB, 1 MiB, 2 MiB}.
Controlled: N, inputs, O3 core, other hardware at baseline.
