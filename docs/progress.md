# ArchForge progress log

Running log for resuming work: stage reports, commits, core-hours, disk, failures, decisions, and current state. Newest state first under Current state; stage reports below in order.

## Current state

- Stage 0 complete. Next: Stage 1 (option verification with `scripts/check_options.sh`).
- Cumulative core-hours: 3.67 of 600.
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

## Decisions

- gem5 embeds the system Python 3.10 and is compiled with the system gcc 11.4; the conda environment supplies only SCons and analysis tools (Stage 0).
- Account `publicgrp`, partition `high` for every job.
- The Stage 3 runner (`run_sweep.py`, `collect.py`, `parse_stats.py`) is written before the Stage 2 baseline runs so Stage 2 uses the same validated pipeline instead of a throwaway script.

## Stage 0 report

Toolchain built and determinism confirmed; details in `docs/stage0.md`.

- gem5 v25.1.0.1 (`c8222cc6`), gem5.opt built in 26 min on 8 CPUs; libm5.a built.
- Failure: first build job (24154194) failed at configure because gem5 picked up the environment's `python3-config`; fixed by putting `/usr/bin` first on `PATH` for the SCons step.
- Determinism: gem5's `two_level.py` and ArchForge's `archforge_se.py` (O3) each produced identical stats across three runs apart from `host*` statistics.
- Disk: 4.1 GB before, 7.3 GB after.
