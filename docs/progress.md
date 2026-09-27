# ArchForge progress log

Running log for resuming work: stage reports, commits, core-hours, disk, failures, decisions, and current state. Newest state first under Current state; stage reports below in order.

## Current state

- Stages 0 to 3 complete. Next: Stage 4 (pilot, then the four studies in `experiments/s4_*.yaml`).
- Cumulative core-hours: 4.85 of 600.
- Home usage: 7.3 GB of 20 GB (stop threshold 16 GB).
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

## Decisions

- gem5 embeds the system Python 3.10 and is compiled with the system gcc 11.4; the conda environment supplies only SCons and analysis tools (Stage 0).
- Account `publicgrp`, partition `high` for every job.
- Never commit or copy tracked files into `~/ArchForge` while an array is running: tasks that start during the change record a dirty tree and fail validation (happened to two Stage 2 runs, which were rerun).
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

## Open questions

- Conflict sets on O3 miss far less often than cyclic LRU predicts (Stage 2). Follow-up in Stage 4 CPU-model study.
- Strided DRAM access gets faster from stride 8 to stride 64 as DRAM mean access latency falls (Stage 2).
- The compute loop is serialized, 3 cycles per 64-bit multiply, with no functional-unit contention (Stage 2); attributed to gem5's x86 IMUL micro-ops, not investigated further.
