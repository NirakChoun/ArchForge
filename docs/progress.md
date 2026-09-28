# ArchForge progress log

Running log for resuming work: stage reports, commits, core-hours, disk, failures, decisions, and current state. Newest state first under Current state; stage reports below in order.

## Current state

- All Core stages, Extended E1 and E2, and final polish complete. No ArchForge jobs running or pending. Stretch items not started, per the brief.
- Cumulative core-hours: 71.81 of 600.
- Home usage: 7.4 GB of 20 GB (stop threshold 16 GB).
- No ArchForge jobs running or pending.

## Locations

| What | Where |
|---|---|
| Repository (source of truth) | `~/ArchForge` on Hive, pushed to `git@github.com:NirakChoun/ArchForge.git` |
| gem5 source and build | `~/gem5` (tag v25.1.0.1, not in the repo) |
| Environment | `~/archforge-env`, micromamba at `~/.local/bin/micromamba`, root prefix `~/.mamba` |
| Raw simulation output | `~/af_scratch/runs/<experiment>/`, archives in `~/af_scratch/archive/` |
| Slurm logs | `~/af_scratch/logs/` |
| Mac staging copy used for editing | `~/archforge-stage` on the Mac (files are copied to Hive with scp) |

## Core-hour ledger

| Stage | Job IDs | Core-hours | Cumulative |
|---|---|---|---|
| 0 | 24154193 (env), 24154194 (failed build), 24154203 (build), 24154327, 24154329 (determinism) | 3.67 | 3.67 |
| 1 | 24154343, 24154348, 24154351 (option checks, about 45 s each) | 0.02 | 3.69 |
| 2-3 | 24154357 (pilot), 24154374 (sweep), 24154474 (reruns) | 1.16 | 4.85 |
| 4 | s4-cpu 24154521, 24154547; s4-mlp 24154580, 24154606; s4-cache 24154820, 24154840, 24155086; option check 24155085; s4-prefetch 24155102, 24155119 | 10.05 | 14.90 |
| 5-6 | s5 24155330, 24155373 (24155328 cancelled: dirty tree); s6 pilot 24155602, factorial 24155846 (190 tasks) | 48.12 | 63.02 |
| 7, E1, E2, final | s7 24159048, 24159704, 24160498, 24161254; e1 24163988, 24164085; e2 24164211, 24164242; repro 24164311, 24164530, 24164823 | 8.79 | 71.81 |

## Decisions

- gem5 embeds the system Python 3.10 and is compiled with the system gcc 11.4; the conda environment supplies only SCons and analysis tools (Stage 0).
- Account `publicgrp`, partition `high` for every job.
- Never commit or copy tracked files into `~/ArchForge` while an array is running: tasks that start during the change record a dirty tree and fail validation (happened to two Stage 2 runs, which were rerun).
- After any parser change, re-collect every existing study and commit the regenerated CSVs before the next submission (a re-collect rewrote three tracked CSVs and dirtied the tree once; the affected pilot was cancelled and resubmitted).
- Stage 6 uses 128-row bands of C at N = 416 and 448 instead of full N = 320/384 products: the full products exceed the 30-minute per-simulation limit (`docs/stage6.md`).
- The Stage 3 runner (`run_sweep.py`, `collect.py`, `parse_stats.py`) is written before the Stage 2 baseline runs so Stage 2 uses the same validated pipeline instead of a throwaway script.

## Stage 0 report

Toolchain built and determinism confirmed; details in `docs/stage0.md`.

- gem5 v25.1.0.1 (`c8222cc6`), gem5.opt built in 26 min on 8 CPUs; libm5.a built.
- Failure: first build job (24154194) failed at configure because gem5 picked up the environment's `python3-config`; fixed by putting `/usr/bin` first on `PATH` for the SCons step.
- Determinism: gem5's `two_level.py` and ArchForge's `archforge_se.py` (O3) each produced identical stats across three runs apart from `host*` statistics.
- Disk: 4.1 GB before, 7.3 GB after.

## Stage 1 report

Parameterized single-core system verified option by option; details in `docs/stage1.md`, defaults in `docs/architecture.md`.

- 18 option cases, all verified against `config.ini`.
- Fixed: validation of CPU and DRAM type (config.ini uses base-class names), 128-byte lines with DDR4 (interleave granule), SimpleMemory bandwidth units.
- `scripts/parse_stats.py` is committed here because the option check uses its `validate_config`; its statistics extraction is tested in Stage 3.

## Stage 2 report

Microbenchmark suite built, validated, and run on the baseline; details in `docs/stage2.md`.

- 40 runs (array 24154374 plus reruns 24154474), all valid. Pilot array 24154357 used for sizing only.
- Matched theory: capacity steps, per-level load-to-use latency (2 / 16 / about 220 cycles), MLP scaling with independent chains (6.6x at 8 chains), branch predictability, the 8-way associativity boundary.
- Did not match: compute loop serialized by gem5's x86 multiply micro-ops; conflict-set miss rates far below cyclic-LRU theory on O3; strided DRAM access faster at larger strides.

## Stage 3 report

Runner, collector, and parser in place and exercised by Stage 2; details in `docs/stage3.md`, statistic definitions in `docs/stats.md`.

- 13 parser unit tests pass against a saved run.
- Validation catches wrong configuration, missing PASS, wrong dump count, dirty tree, and cross-configuration instruction mismatch.

## Stage 4 report

Four mechanism studies, 164 runs, all valid; details in `docs/stage4.md`.

- CPU model: O3 3.6x to 5x TimingSimple on streaming, equal on the pointer chase and on the serialized-multiply compute loop. On in-order models the conflict sets miss on every access, so the Stage 2 conflict deviation is an out-of-order effect.
- MLP: cycles per step divide exactly by the number of independent chains; the ROB matters only at 8 chains and only from 32 to 64 entries; LQ 8 costs 2 percent at 8 chains.
- Caches: capacity and associativity boundaries exactly where predicted; 128-byte lines help sequential access (6.74 to 6.09 cycles per load) and double the cost of 128-byte strides.
- Prefetching: stride prefetcher doubles sequential-sum speed with no extra DRAM traffic; useless on 64- and 128-byte strides because O3 demand misses already lead it; gem5's accuracy/coverage statistics understate late-but-helpful prefetches.
- Failure: 32-byte lines failed on O3 (`fetch buffer size (64 bytes) is greater than the cache block size`). Fixed in the config (fetch buffer follows the line size below 64 B, documented in `docs/architecture.md`), option check extended, four runs rerun.
- Contradicted expectations: MinorCPU slower than TimingSimpleCPU on nearly everything; stride 2 slower with 128-byte lines than with 64-byte lines.

## Stage 5 report

Application workloads characterized on the baseline; details in `docs/stage5.md`.

- 9 runs (pilot 24155330, sweep 24155373), all valid. Matrix multiply ijk N = 320 took 24 min 17 s, the slowest single simulation so far.
- Matrix multiply at N = 320: B fits in the 1 MiB L2, so loop order and tiling changed L1D misses 80x but cycles at most 1.30x; ijk was fastest, contrary to the prediction.
- AoS one-field sum: 32x the DRAM bytes and 7.2x the cycles of SoA; eight fields: within 7 percent.
- Sort: 55 branch mispredictions per 1000 instructions, cache-resident; reduction: DRAM stream.

## Stage 6 report

Tile x L1D x L2 factorial at two sizes, 192 runs, all valid; details in `docs/stage6.md`.

- Untiled matmul is capacity-sensitive only at the 2 MiB L2 (2.5x); tiled kernels vary at most 1.23x over the whole grid.
- Best tile t24 or t32 everywhere; t24 at 16 KiB L1D, t32 at 32 to 64 KiB with 512 KiB to 1 MiB L2; margins 0.1 to 5.4 percent.
- Speedups over the baseline: hardware-only 2.49x to 2.50x, software-only 3.17x to 3.18x, joint 3.37x to 3.38x.
- Design change before running: 128-row bands at N = 416 and 448 replaced full products at 320 and 384 to stay under 30 minutes per simulation.

## Stage 7 report

Compiler variants; details in `docs/stage7.md`.

- Flags (12 runs, pilot 24159048, sweep 24159704): only `-O3` vectorization mattered; matrix multiply cycles about halved; the DRAM-bound reduction's instructions fell 3.2x and cycles 2.1x. Matrix multiply used 128-row bands at N = 320 to keep `-O1` under the time limit.
- TensorForge (48 runs, pilot 24160498, sweep 24161254): TensorForge's pipeline recompiled for SSE2 (`llc -mcpu=x86-64`; its own backend uses `-mcpu=native`); f32 kernels at N = 256. Register-tiled vectorized kernels 8x faster than scalar on every cache configuration; L1D size irrelevant; L2 below 512 KiB costs 2.4x to 3.1x.
- Contradicted expectations: scalar TensorForge kernels slower with 1 to 2 MiB L2 than with 512 KiB (L1D writeback per miss).

## Stage 8 report

`docs/report.md` written (research question through reproducibility), `docs/index.md` links every document. `scripts/repro_clone.sh` added for the clean-clone reproduction (run during final polish).

## E1 report

AoS vs SoA x line size x prefetcher, 24 runs (pilot 24163988, sweep 24164085), all valid; `docs/e1.md`.

- One-field AoS 7.2x to 10.7x slower than SoA at every line size, with or without prefetching; AoS time flat across line sizes (window-limited). Contradicted the prediction that AoS would slow with longer lines.
- Eight fields: layouts within 10 percent.

## E2 report

Two-core false sharing, 4 runs (pilot 24164211, rest 24164242), all valid; `docs/e2.md`.

- Shared line 7.8x (O3) and 5.1x (TimingSimple) slower per increment than padded; one read-exclusive and one 64-byte snoop per increment on O3; load miss plus upgrade on TimingSimple.
- Parser extended with multicore columns (`mc_*`), which sum per-core statistics and read crossbar coherence traffic.

## Final polish report

- README rewritten (summary, gem5 vs ArchForge, pipeline diagram, build and reproduce, worked example, results); `docs/index.md` links every document; `docs/report.md` complete including E1 and E2.
- All results CSVs regenerated with the final parser from the archived raw outputs (`scripts/recollect_all.sh`); every analysis script re-run with no change to any figure.
- Incident: a re-collect of `s6-codesign` was interrupted by a command timeout while it rewrote that sweep's archive, leaving a truncated `.tar.gz`; the unpacked copy was then removed. The Stage 6 CSV had already been rewritten from the complete data and matches the committed one in every existing column. 84 of 192 Stage 6 run directories were recovered into a new, valid archive; the raw outputs of the other 108 are lost. `collect.py` now writes archives under a temporary name and renames them.
- Clean-clone reproduction (`scripts/repro_clone.sh`): the first attempt (job 24164311) rebuilt the branch workload from the current tree, whose `workloads/common/af.h` changed after Stage 2; the binary differed and 3 of 4 runs differed by up to 0.02 percent in cycles. The script now rebuilds the workload from the commit recorded in the CSV, checks the sha256 against the recorded one, and then simulates. Job 24164530 rebuilt the identical binary and still differed the same way: the difference came from the program path, which is copied onto the simulated stack (the sweep ran the binary from `runs/s2-micro/bin/`, the clone from `workloads/bin/`). The script now runs the binary from the sweep's path; job 24164823 reproduced all four runs exactly (every parsed statistic identical).
- Commit prefixes: Extended and final-polish commits use `e1:`, `e2:`, and `final:` instead of `stageN:`.

## Open questions

- Conflict sets on O3 miss far less often than cyclic LRU predicts (Stage 2). Resolved in part by Stage 4: in-order models miss on every access, so out-of-order issue is the cause; the exact reordering was not traced.
- Strided DRAM access gets faster from stride 8 to stride 64 as DRAM mean access latency falls (Stage 2).
- Scalar TensorForge f32 kernels at N = 256 run faster with a 512 KiB L2 than with 1 or 2 MiB; the L1D writes back a line on nearly every miss only with the larger L2s. Candidate cause: input lines left dirty in L2 by initialization and handed to the L1D dirty (Stage 7).
- MinorCPU in gem5 v25.1 is slower than TimingSimpleCPU on these x86 workloads. Resolved (follow-up after final polish): the predictor is instantiated but never consulted, because Minor's Fetch2 predicts on x86 macro-ops and gem5 marks only the last micro-op as a control instruction (`docs/stage4.md`). Configuration correct; no runs changed.
- Stride-2 loads run slower with 128-byte than with 64-byte lines (Stage 4).
- Untiled ikj matrix multiply is 1.30x slower than naive ijk at N = 320 on the baseline, with frequent ROB-full stalls (Stage 5). Follow-up after final polish: the assembly shows gcc did not interchange, vectorize, or otherwise transform either kernel (7 and 8 instructions per multiply-add, as written); the gap is a core effect, and the exhausted O3 resource was not isolated (`docs/stage5.md`).
- The compute loop is serialized, 3 cycles per 64-bit multiply, with no functional-unit contention (Stage 2); attributed to gem5's x86 IMUL micro-ops, not investigated further.
