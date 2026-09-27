# ArchForge

ArchForge is a gem5-based study of how software transformations and microarchitectural choices interact to set performance, and whether choosing them jointly beats tuning either alone. All results are from gem5 simulation (syscall-emulation mode, x86), not from real hardware.

Work in progress; see `docs/progress.md` for the current state.

## gem5 and ArchForge

gem5 v25.1.0.1 provides the CPU models, caches, prefetchers, memory controllers, and the standard library. ArchForge provides the parameterized system configuration, the workloads and their software variants, the experiment runner, the statistics parser and analysis, and the studies. `docs/architecture.md` lists which component comes from which.

## Setup on Hive

```
git clone git@github.com:NirakChoun/ArchForge.git ~/ArchForge
cd ~/ArchForge
mkdir -p ~/af_scratch/logs
sbatch scripts/setup_env.sh                       # ~/archforge-env
git clone --depth 1 --branch v25.1.0.1 https://github.com/gem5/gem5.git ~/gem5
sbatch scripts/build_gem5.sh                      # gem5.opt and libm5.a, ~30 min on 8 CPUs
sbatch scripts/determinism_check.sh               # three identical runs per config
```
