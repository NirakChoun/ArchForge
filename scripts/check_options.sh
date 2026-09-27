#!/bin/bash
#SBATCH --job-name=af-check-options
#SBATCH --account=publicgrp
#SBATCH --partition=high
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --output=/home/%u/af_scratch/logs/slurm-%j.out
# Stage 1 check: every option of configs/archforge_se.py changes config.ini.
# Runs gem5's hello binary once at the baseline and once per non-default
# option value, then compares each config.ini against the baseline.
set -uo pipefail
cd ~/ArchForge
source scripts/env.sh
HELLO="$GEM5_DIR/tests/test-progs/hello/bin/x86/linux/hello"
BASE="$AF_SCRATCH/runs/stage1-options"
rm -rf "$BASE"; mkdir -p "$BASE"
echo "host: $(hostname) job: ${SLURM_JOB_ID:-none} date: $(date -Is)"
CASES=(
  "baseline|"
  "cpu-timing|--cpu timing"
  "cpu-minor|--cpu minor"
  "clock|--clock 2GHz"
  "l1i-size|--l1i-size 16KiB"
  "l1i-assoc|--l1i-assoc 4"
  "l1d-size|--l1d-size 64KiB"
  "l1d-assoc|--l1d-assoc 4"
  "l2-size|--l2-size 512KiB"
  "l2-assoc|--l2-assoc 8"
  "line-size|--line-size 128"
  "pf-l1d|--prefetcher stride"
  "pf-l2|--prefetcher stride --prefetch-level l2"
  "mem-simple|--mem-type SimpleMemory --mem-latency 80ns"
  "mem-size|--mem-size 1GiB"
  "rob|--rob 64"
  "lq|--lq 16"
  "sq|--sq 16"
)
for c in "${CASES[@]}"; do
  name="${c%%|*}"; args="${c#*|}"
  # shellcheck disable=SC2086
  "$GEM5" -re -d "$BASE/$name" configs/archforge_se.py --binary "$HELLO" $args \
    > /dev/null 2>&1 || echo "run $name exited nonzero"
done
python scripts/check_options.py "$BASE" "${CASES[@]}"
