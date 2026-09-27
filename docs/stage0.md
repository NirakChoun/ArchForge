# Stage 0: toolchain and reproducible baseline

gem5 v25.1.0.1 builds on Hive and is deterministic: three identical runs of the same binary and configuration produce stats.txt files that differ only in five host-dependent statistics. Every later stage runs each configuration once on the strength of this check.

## Toolchain

| Item | Value |
|---|---|
| gem5 | tag `v25.1.0.1`, commit `c8222cc67a399bfc01e8658dd14b30d5bfd634f9`, shallow clone at `~/gem5` |
| gem5 binary | `~/gem5/build/X86/gem5.opt` (1.0 GB) |
| m5 library | `~/gem5/util/m5/build/x86/out/libm5.a` (x86, `m5ops.h` from `~/gem5/include`) |
| Compiler for gem5 and workloads | system gcc 11.4.0 (Ubuntu 22.04) |
| Python embedded in gem5 | system Python 3.10 (`/usr/bin/python3-config`) |
| Host-side environment | `~/archforge-env` (micromamba, conda-forge; versions pinned in `environment.yml`) with Python 3.12.14, SCons 4.8.1, PyYAML, NumPy, pandas, Matplotlib, pytest |
| `module avail gem5` | no gem5 module on Hive; built from the release tag |

gem5 embeds the system Python rather than the environment's, so `gem5.opt` does not depend on the conda environment's shared libraries at run time. gem5 v25.1 locates `python3-config` through `PATH` and ignores a `PYTHON_CONFIG` argument, so `scripts/build_gem5.sh` puts `/usr/bin` first on `PATH` for the SCons step only. The first build attempt without that failed at configure time (linked against the environment's `libpython3.12`).

### Build record

| Step | Slurm resources | Wall time | Peak memory | Home usage |
|---|---|---|---|---|
| Environment (`scripts/setup_env.sh`) | 2 CPU, 8 GB | 3 min 48 s | 3.4 GB | 4.1 GB before |
| gem5.opt + libm5.a (`scripts/build_gem5.sh`) | 8 CPU, 32 GB, `-j 8` | 26 min 20 s | 14.4 GB | 4.8 GB before, 7.3 GB after |

## Determinism check

`scripts/determinism_check.sh` runs gem5's provided x86 `hello` binary (sha256 `451c59bd...cba2`) three times in each of two configurations inside one single-CPU Slurm job, and `scripts/compare_stats.py` compares the three stats.txt files statistic by statistic.

| Configuration | Code | Statistics per dump | Result |
|---|---|---|---|
| `configs/learning_gem5/part1/two_level.py` (TimingSimpleCPU, two-level cache) | gem5 only | 937 | identical apart from host statistics |
| `configs/archforge_se.py` defaults (O3CPU, ArchForge hierarchy, DDR4-2400) | ArchForge | 1692 | identical apart from host statistics |

Host-dependent statistics in gem5 v25.1 stats.txt: `hostSeconds`, `hostTickRate`, `hostInstRate`, `hostOpRate`, `hostMemory`. The first four differed between runs; `hostMemory` happened to match but measures the simulator process, so it is treated as host-dependent too. `compare_stats.py` excludes any statistic named `host*`.

Workload stdout is written to `simout.txt` (not `simout`) in gem5 v25.1 when run with `-re`; the scripts look for `simout.txt`.

## Scripts added

| File | Purpose |
|---|---|
| `scripts/env.sh` | Activates the environment and exports `GEM5`, `M5_INC`, `M5_LIB`, `AF_SCRATCH` |
| `scripts/setup_env.sh`, `scripts/build_gem5.sh` | Slurm jobs that create the environment and build gem5 |
| `scripts/sim_job.sh` | Slurm template for one simulation (1 CPU, 4 GB, 30 min) |
| `scripts/run_sim.sh` | Runs one simulation and writes `af_meta.json` (provenance, wall time, PASS/FAIL) |
| `scripts/determinism_check.sh`, `scripts/compare_stats.py` | This check |
