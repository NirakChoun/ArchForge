#!/bin/bash
#SBATCH --job-name=af-determinism
#SBATCH --account=publicgrp
#SBATCH --partition=high
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --output=/home/%u/af_scratch/logs/slurm-%j.out
# Stage 0 determinism check: gem5's provided x86 hello binary, three
# identical runs per configuration, compared stat by stat.
# Configurations: gem5's own learning_gem5 two_level.py (TimingSimpleCPU,
# no ArchForge code involved) and ArchForge's archforge_se.py with O3.
set -uo pipefail
cd ~/ArchForge
source scripts/env.sh
HELLO="$GEM5_DIR/tests/test-progs/hello/bin/x86/linux/hello"
BASE="$AF_SCRATCH/runs/stage0-determinism"
rm -rf "$BASE"; mkdir -p "$BASE"
echo "host: $(hostname) job: ${SLURM_JOB_ID:-none} date: $(date -Is)"
sha256sum "$HELLO"
for i in 1 2 3; do
  (cd "$GEM5_DIR" && "$GEM5" -re -d "$BASE/two_level_$i" \
      configs/learning_gem5/part1/two_level.py "$HELLO") || echo "two_level run $i failed"
  "$GEM5" -re -d "$BASE/af_o3_$i" configs/archforge_se.py --binary "$HELLO" \
      || echo "af_o3 run $i failed"
done
for c in two_level af_o3; do
  echo "== $c"; grep -h "Hello" "$BASE/${c}_1/simout.txt"
  python scripts/compare_stats.py "$BASE"/${c}_{1,2,3}/stats.txt
done
