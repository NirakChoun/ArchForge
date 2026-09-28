# ArchForge report

ArchForge asks how software transformations and microarchitectural choices interact to set performance, and whether choosing them jointly beats tuning either alone. In gem5 simulation of one x86 core, loop tiling made matrix multiply almost insensitive to private cache capacity: tiling alone gave a 3.17x speedup, a larger L2 alone 2.50x, and the best joint choice 3.38x, only 6 to 7 percent beyond the best software-only choice. All numbers are from gem5 v25.1.0.1 in syscall-emulation mode, not from real hardware.

Stage documents hold the full evidence: `docs/stage2.md` (simulator validation), `docs/stage4.md` (mechanisms), `docs/stage5.md` (workloads), `docs/stage6.md` (co-design), `docs/stage7.md` (compiler variants), `docs/e1.md`, `docs/e2.md`.

## Research question

How does loop tiling change matrix multiply's sensitivity to private cache capacity, and does choosing tile size and cache configuration jointly beat choosing either alone? Supporting questions: which microarchitectural mechanisms (capacity, associativity, line size, prefetching, out-of-order overlap) set the cost of each access pattern in this simulator, and how compiler-generated code (gcc optimization levels, TensorForge's MLIR pipeline) moves the same trade-offs.

## Hypothesis

Written before the Stage 6 runs (`docs/stage6.md`): the untiled kernel is sensitive to L2 capacity and not to L1D; tiled kernels are much less sensitive to both; the best tile grows with L1D; and the joint optimum beats hardware-only and software-only choices, by a small margin over software-only.

## Workloads

| Workload | Purpose | Source |
|---|---|---|
| Sequential sum, strided loads, pointer chase (1 to 8 independent chains), compute loop, branch patterns, conflict sets | Microbenchmarks that isolate one mechanism each | `workloads/micro/` |
| Matrix multiply: naive ijk, interchanged ikj, tiled ikj (tile 8 to 64), optional row band | Centerpiece workload and software variants | `workloads/apps/matmul.c` |
| Array of structs vs struct of arrays field sums | Data layout | `workloads/apps/aos_soa.c` |
| Reduction, quicksort | Contrast workloads (streaming, branch-bound) | `workloads/apps/reduce.c`, `sort.c` |
| TensorForge f32 matmul kernels | Compiler-generated variants | `scripts/build_tf_kernels.sh`, `workloads/apps/tf_matmul.c` |
| Two-thread counters, shared line vs padded | Multicore false sharing (E2) | `workloads/apps/falseshare.c` |

Every workload marks its region of interest (ROI) with `m5_reset_stats` / `m5_dump_stats` and checks its own output, printing PASS or FAIL.

## Hardware configurations

Baseline (`docs/architecture.md`): O3 core at 3 GHz (gem5 defaults: 8-wide, 192-entry ROB, 32-entry load and store queues, TournamentBP), private 32 KiB 8-way L1I and L1D, private 1 MiB 16-way L2, 64-byte lines, no prefetcher, one DDR4-2400 channel. Studies vary one parameter at a time around it, except the Stage 4 MLP study and the Stage 6 co-design study, which are designed factorials:

| Study | Varied |
|---|---|
| Stage 4 CPU model | TimingSimpleCPU, MinorCPU, O3CPU |
| Stage 4 MLP | ROB 32 to 256 x independent chains 1 to 8 x fixed memory latency 50, 100, 200 ns; load queue 8 to 64 |
| Stage 4 caches | L1D 16 to 64 KiB; L2 256 KiB to 2 MiB; L1D 2 to 16 ways; L2 4 to 32 ways; line 32, 64, 128 B |
| Stage 4 prefetching | none, stride prefetcher at L1D, at L2 |
| Stage 6 co-design | L1D {16, 32, 64 KiB} x L2 {256 KiB, 512 KiB, 1 MiB, 2 MiB} x tile {untiled, 8, 12, 16, 24, 32, 48, 64} x N {416, 448} |

## Software variants

Loop order (ijk, ikj), tile size (8 to 64), data layout (AoS, SoA), gcc optimization level (`-O1`, `-O2`, `-O3`, `-O3 -fno-tree-vectorize`), and TensorForge pipeline configuration (scalar, cache-tiled, register-tiled and vectorized). All code is built for the SSE2 baseline (`-march=x86-64`, `llc -mcpu=x86-64`) because gem5's X86 model has no AVX; `scripts/check_no_avx.sh` verifies it.

## Metrics

ROI cycles (primary), committed instructions, IPC, L1D and L2 line misses, DRAM bytes, average outstanding misses (MLP, from summed miss latency by Little's law), branch mispredictions, O3 structure-full events, and prefetcher statistics. Definitions and gem5 statistic names are in `docs/stats.md`.

## Methodology

- Determinism: gem5 is deterministic for a given binary and configuration. Three identical runs of gem5's hello program in two configurations produced identical stats apart from host statistics (`docs/stage0.md`), so each configuration was run once.
- Region of interest: statistics are reset before and dumped after the kernel; only that dump is used. Initialization and checking are excluded.
- SE mode: syscall emulation, no operating system, no timer interrupts, no TLB-shootdowns or context switches; physical pages are allocated on first touch.
- Validation (every run): the workload printed PASS; `config.ini` matches the requested CPU, cache sizes and associativities, line size, clock, prefetcher, memory, and O3 sizes; exactly two stats dumps; the source tree was clean at run start; and ROI instruction counts are identical across hardware configurations for the same binary and arguments. Runs failing any check stay in the CSV with the reason and are excluded from analysis; every reported run passed.
- Pipeline: `experiments/*.yaml` to `scripts/run_sweep.py` (capped Slurm arrays) to `scripts/collect.py` (parse, validate, CSV) to `analysis/*.py` (tables and figures). `docs/stage3.md` describes it.
- Inputs sized so each simulation finishes in under 30 minutes; the co-design study therefore uses 128-row bands of C for N = 416 and 448 (`docs/stage6.md`).

## Results

### The co-design question (Stage 6)

| Choice | N = 416 | N = 448 |
|---|---|---|
| Baseline: untiled, L1D 32 KiB, L2 1 MiB | 1.00 | 1.00 |
| Best hardware-only (untiled, L2 2 MiB) | 2.49 | 2.50 |
| Best software-only (t32 on the baseline) | 3.18 | 3.17 |
| Best joint | 3.37 (t32, 64 KiB, 2 MiB) | 3.38 (t24, 64 KiB, 2 MiB) |

Capacity sensitivity (max/min cycles over the 12 cache configurations): 2.49 to 2.50 untiled, 1.09 to 1.23 for every tile. The best tile was t24 or t32 in all 24 hardware configurations, t24 at 16 KiB L1D and t32 at 32 to 64 KiB for mid-size L2, with margins of 0.1 to 5.4 percent over the runner-up.

### Mechanisms (Stages 2 and 4)

- Load-to-use latency exposed by a dependent chain: 2 cycles (L1D), 16 (L2), about 220 (DRAM, 73 ns).
- Independent misses overlap: cycles per step divide exactly by the number of independent chains (1 to 8); a larger ROB helps only when there are independent misses and only from 32 to 64 entries at 8 chains (1.12x to 1.43x depending on memory latency).
- Capacity and associativity behave as step functions at the predicted sizes; beyond the associativity limit, out-of-order issue on O3 keeps miss rates far below cyclic-LRU theory, while in-order models miss on every access.
- 128-byte lines speed sequential access (6.74 to 6.09 cycles per load) and double the cost of 128-byte strides.
- gem5's stride prefetcher doubles sequential-sum speed at no extra DRAM traffic and does nothing for 64- or 128-byte strides, where the O3 core's demand misses are already as early as the prefetcher could be.

### Workloads and compilers (Stages 5 and 7)

- On the baseline at N = 320, B fits in L2: loop order and tiling changed L1D misses 80x but cycles at most 1.30x (ikj slowest).
- A one-field sum over array-of-structs moved 32x the DRAM bytes and took 7.2x the cycles of struct-of-arrays.
- gcc `-O3` SSE2 vectorization halved matrix multiply cycles; the DRAM-bound reduction's instructions fell 3.2x but cycles only 2.1x.
- TensorForge's register-tiled, vectorized f32 kernels, recompiled for SSE2, ran 8x faster than its scalar kernels on every cache configuration; its cache tiling (M and N only) left the scalar kernel's column walk of B in place. Scalar kernels ran slower with 1 to 2 MiB of L2 than with 512 KiB, together with an L1D writeback on nearly every miss (open question, `docs/stage7.md`).

### Extended studies (E1, E2)

- Data layout x hierarchy (E1): a one-field AoS sum stayed 7.2x to 10.7x slower than SoA across 32, 64, and 128-byte lines with and without the stride prefetcher; AoS time was flat across line sizes (window-limited, about 8.5 misses in flight), and the prefetcher helped SoA up to 1.45x but AoS only 1.03x to 1.04x. With all fields summed the layouts were within 10 percent.
- False sharing (E2): two cores incrementing counters in one line took 7.8x (O3) and 5.1x (TimingSimple) longer per increment than padded counters, with one read-exclusive request and one 64-byte snoop per increment on the crossbar between the private L2s.

## Mechanistic explanation

The co-design result follows one causal chain per kernel, each link backed by a statistic (N = 416, per multiply-add; `docs/stage6.md`).

Untiled ikj, baseline to 2 MiB L2: B (1.32 MiB) fits in L2, so L2 misses per multiply-add fall from 0.126 to 0.0016 (`l2caches.demandMisses`), DRAM bytes from 8.04 to 0.10 (`mem_ctrl.dram.bytesRead`), average outstanding L2 misses from 1.75 to 0.07, IPC rises from 0.76 to 1.89 at constant instruction count, and cycles fall 2.49x. L1D size changes nothing (line misses stay at 0.126, one per line of B, because a row of B is streamed per k).

Tiling at t32 on the baseline: each 32 x 32 block of B (8 KiB) is reused across 32 rows while it sits in L1D, so L1D line misses fall from 0.126 to 0.011, L2 misses to 0.0045, DRAM bytes to 0.29, instructions from 8.02 to 7.32 (the register-held `a` and shorter loops), and IPC rises to 2.20; cycles fall 3.18x. The remaining L2 misses re-read B once per ii block.

Tile-size optimum: smaller tiles re-read B more often (L2 misses per multiply-add 0.016 at t8 against 0.0026 at t64) and retire more loop overhead (8.46 against 7.17 instructions); t64's 32 KiB block of B no longer fits beside A and C in a 32 KiB L1D (L1D line misses rise tenfold to 0.076). t24 and t32 balance these; a 16 KiB L1D favours t24 (its B block is 4.5 KiB).

Joint over software-only: the 2 MiB L2 removes the ii-block re-reads of B (L2 misses 0.0045 to 0.0015, DRAM bytes 0.29 to 0.10), worth 5 to 7 percent once tiling has removed the rest.

## Sensitivity

Every headline was checked at neighbouring values. The co-design factorial is its own neighbourhood: both N, every adjacent tile, and every adjacent L1D and L2 size (`docs/stage6.md`); the best tile was t24 or t32 in every configuration, and the untiled kernel's L2 step appeared at both N. The MLP conclusion holds at all three memory latencies and all five ROB sizes. Cache-mechanism conclusions were checked with two footprints or line counts per parameter (`docs/stage4.md`).

## Ablation

| Effect (N = 416) | Speedup over baseline | Source |
|---|---|---|
| Software alone (t32, baseline caches) | 3.18 | tiling removes L1D and most L2 misses |
| Hardware alone (2 MiB L2, untiled) | 2.49 | B fits in L2 |
| Both (t32, 64 KiB L1D, 2 MiB L2) | 3.37 | |
| Interaction: joint / (software x hardware) | 3.37 / (3.18 x 2.49) = 0.43 | the effects overlap: both remove the same DRAM traffic on B |

The interaction term is far below 1: hardware and software solve the same problem, so the second one adds little. The 2 MiB L2 is worth 2.49x to the untiled kernel and 1.06x to the tiled one.

## Alternative explanations

- Fixed cache latencies: gem5's caches here have fixed 1-cycle (L1) and 10-cycle (L2) tag and data latencies at every size. Real larger caches are slower, which would reduce the hardware-only and joint gains; the software-only gain is unaffected.
- Row band: the co-design runs compute 128 rows of C, which reads all of B at least once per run and slightly overstates compulsory DRAM traffic per multiply-add compared with a full product.
- Model quirks found in validation (`docs/stage2.md`, `docs/stage4.md`): 64-bit integer multiplies serialize in gem5's x86 micro-ops, MinorCPU does not consult its branch predictor on these binaries, and O3 out-of-order issue masks LRU conflict behaviour. None affects the double-precision matrix multiply, but they limit how far other results generalize.
- The t24/t32 ordering is within a few percent and could be moved by L1D replacement or bank details not modelled.

## Interpretation

TODO(Nirak)

## Limitations

- Simulation, not measurement: every number comes from gem5's models, and those models were shown to deviate from real cores in places (integer multiply serialization, MinorCPU behaviour).
- SE mode: no operating system, page-table walks without OS effects, no interrupts or other processes.
- No AVX: gem5's X86 model does not implement AVX, so all code is SSE2; modern compilers and TensorForge's own backend would use AVX2 and FMA on real x86 hardware.
- No power or area model: cost is discussed only qualitatively.
- Cache latencies do not scale with capacity (above).
- Single core except E2; private caches only; one DDR4 channel.
- Input sizes were chosen to keep each simulation under 30 minutes (row bands in Stage 6, N = 256 for TensorForge kernels).

## Reproducibility

Everything runs on UC Davis Hive; heavy steps are Slurm jobs.

```
git clone git@github.com:NirakChoun/ArchForge.git ~/ArchForge && cd ~/ArchForge
mkdir -p ~/af_scratch/logs
sbatch scripts/setup_env.sh                                   # ~/archforge-env from environment.yml
git clone --depth 1 --branch v25.1.0.1 https://github.com/gem5/gem5.git ~/gem5
sbatch scripts/build_gem5.sh                                  # gem5.opt (X86) and libm5.a
sbatch scripts/determinism_check.sh                           # Stage 0
sbatch scripts/check_options.sh                               # Stage 1
source scripts/env.sh
make -C workloads -j 2 all variants && make -C workloads check-avx check-avx-variants
scripts/build_tf_kernels.sh 256                               # needs ~/TensorForge built
python -m pytest tests                                        # parser unit tests
python scripts/run_sweep.py experiments/s6_codesign.yaml --pilot 96,108   # pilot
python scripts/run_sweep.py experiments/s6_codesign.yaml                  # full array (repeat with --chunk 1 if > 200 runs)
python scripts/collect.py s6-codesign
python analysis/stage6.py
```

Each experiment file in `experiments/` is run the same way; `analysis/stage<N>.py` regenerates every table and figure in the stage documents from `results/*.csv`. Every CSV row carries the ArchForge commit, the gem5 tag and commit, the binary's sha256, the Slurm job and array task, and the full configuration.

`scripts/repro_clone.sh` (a Slurm job) clones the repository from GitHub into scratch, builds the branch-pattern workload from the clone, reruns the four Stage 2 branch configurations, and checks that every parsed statistic matches the committed CSV exactly.
