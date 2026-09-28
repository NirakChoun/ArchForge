# ArchForge

ArchForge is a gem5-based hardware-software co-design study: it measures how software transformations (loop order, tiling, data layout, compiler optimization) and microarchitectural choices (CPU model, window size, cache capacity, associativity, line size, prefetching) interact to set performance, and whether choosing them jointly beats tuning either alone. Every number comes from gem5 v25.1.0.1 simulation of an x86 core in syscall-emulation mode, not from real hardware.

## Results summary

- Co-design (Stage 6): for matrix multiply, tiling alone gave 3.17x to 3.18x over the untiled kernel on the baseline caches, a 2 MiB L2 alone gave 2.49x to 2.50x, and the best joint choice 3.37x to 3.38x. Tiling cut the kernel's sensitivity to cache capacity from 2.5x to at most 1.23x across 12 cache configurations; the best tile was 24 or 32 everywhere.
- Mechanisms (Stages 2 and 4): dependent-load latency of 2, 16, and about 220 cycles for L1D, L2, and DRAM; independent misses overlap almost perfectly up to 8 chains, and a larger ROB helps only when they exist; the stride prefetcher doubles a sequential sum and cannot help strides the O3 core already covers.
- Workloads and compilers (Stages 5 and 7, E1): a one-field array-of-structs sum is 7.2x to 10.7x slower than struct-of-arrays at every line size, with or without prefetching; gcc `-O3` SSE2 vectorization halves matrix multiply time; TensorForge's register-tiled vector kernels, recompiled for SSE2, run 8x faster than its scalar kernels.
- Multicore (E2): false sharing between two cores costs 7.8x per increment on O3, with one read-exclusive and one 64-byte snoop per increment.
- Validation found gem5 model behaviours that differ from real cores (serialized 64-bit integer multiplies, MinorCPU not using its branch predictor on these binaries); they are listed in `docs/report.md` under Alternative explanations.

## gem5 and ArchForge

| gem5 v25.1.0.1 provides | ArchForge provides |
|---|---|
| CPU models (TimingSimple, Minor, O3), branch predictor, classic caches, stride prefetcher, crossbars, DDR4 and SimpleMemory, standard-library boards, processors, simulator | Parameterized system config (`configs/archforge_se.py`, its own cache hierarchy class), microbenchmarks and workloads with software variants (`workloads/`), sweep runner, collector, statistics parser and validation (`scripts/`), analysis and plots (`analysis/`), the studies and their documents (`docs/`) |

## Experiment pipeline

```
experiments/<study>.yaml              workloads x hardware configurations, time/memory from a pilot
        |  scripts/run_sweep.py        manifest, binary snapshot, sbatch --array=0-N%8 (<=200 tasks)
        v
Slurm task: scripts/array_task.sh -> scripts/run_sim.sh -> gem5.opt configs/archforge_se.py ...
        |                              stats.txt, config.ini, af_meta.json (provenance, PASS/FAIL)
        v
scripts/collect.py <id>                parse ROI dump, validate config / PASS / dumps / instruction counts
        |                              results/<study>.csv, trim and archive raw outputs
        v
analysis/<stage>.py                    markdown tables and figures in docs/
```

## Build and reproduce (UC Davis Hive)

```
git clone git@github.com:NirakChoun/ArchForge.git ~/ArchForge && cd ~/ArchForge
mkdir -p ~/af_scratch/logs
sbatch scripts/setup_env.sh                        # ~/archforge-env (conda-forge, pinned)
git clone --depth 1 --branch v25.1.0.1 https://github.com/gem5/gem5.git ~/gem5
sbatch scripts/build_gem5.sh                       # gem5.opt for X86 and libm5.a (8 CPUs, about 30 min)
sbatch scripts/determinism_check.sh                # three identical runs agree
source scripts/env.sh
make -C workloads -j 2 all variants && make -C workloads check-avx
python -m pytest tests
```

Then, for any study: `python scripts/run_sweep.py experiments/<file>.yaml --pilot <indices>`, set `time` from the pilot, submit the rest, `python scripts/collect.py <id>`, and `python analysis/<stage>.py`. `docs/report.md` lists the exact commands; `scripts/repro_clone.sh` reproduces one study from a clean clone inside a Slurm job.

## Worked example

Run the untiled and tiled (t32) matrix multiply band on the baseline and on a 2 MiB L2, as one Slurm job each:

```
source scripts/env.sh
for l2 in 1MiB 2MiB; do
  sbatch scripts/sim_job.sh ~/af_scratch/runs/demo-untiled-$l2 configs/archforge_se.py \
    --binary workloads/bin/matmul --args "1 416 1 128" --l2-size $l2
  sbatch scripts/sim_job.sh ~/af_scratch/runs/demo-t32-$l2 configs/archforge_se.py \
    --binary workloads/bin/matmul --args "2 416 32 128" --l2-size $l2
done
# after the jobs finish (about 25 minutes each):
python scripts/parse_stats.py ~/af_scratch/runs/demo-untiled-1MiB | grep -E '"(cycles|l2_demand_misses|dram_bytes_read)"'
```

The committed rows for these four configurations are in `results/stage6_codesign.csv` (untiled 233.9M and 93.9M cycles, t32 73.6M and 69.6M cycles, for 1 MiB and 2 MiB); gem5 is deterministic, so the parsed values match exactly.

## Documentation

`docs/index.md` links every document; start with `docs/report.md`. `docs/progress.md` is the running log (core-hours, decisions, failures, open questions).
