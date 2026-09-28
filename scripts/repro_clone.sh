#!/bin/bash
#SBATCH --job-name=af-repro
#SBATCH --account=publicgrp
#SBATCH --partition=high
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:30:00
#SBATCH --output=/home/%u/af_scratch/logs/slurm-%j.out
# Clean-clone reproduction of one small study: the Stage 2 branch-pattern
# study (4 simulations). Clones the repository from GitHub into scratch,
# builds the workload from the clone, runs the four configurations with the
# clone's config and scripts, and compares every parsed statistic with the
# committed row in results/stage2_micro.csv. gem5 is deterministic, so the
# simulated statistics must match exactly.
set -euo pipefail
source ~/ArchForge/scripts/env.sh
DIR="$AF_SCRATCH/repro"
rm -rf "$DIR"; mkdir -p "$DIR"
git clone -q git@github.com:NirakChoun/ArchForge.git "$DIR/ArchForge"
export AF_ROOT="$DIR/ArchForge"
cd "$AF_ROOT"
echo "clone commit: $(git rev-parse --short=12 HEAD)  host: $(hostname)  job: ${SLURM_JOB_ID:-none}"
make -C workloads bin/branch >/dev/null
for p in 0 1 2 3; do
  scripts/run_sim.sh "$DIR/runs/branch$p" configs/archforge_se.py \
    --binary workloads/bin/branch --args "$p 1048576" >/dev/null
done
python - "$DIR/runs" <<'EOF'
import csv, os, sys
sys.path.insert(0, "scripts")
import parse_stats
ref = {r["workload_args"]: r for r in csv.DictReader(open("results/stage2_micro.csv"))
       if r["workload"] == "branch"}
bad = 0
for p in range(4):
    row, probs, meta, opt = parse_stats.parse_run(os.path.join(sys.argv[1], f"branch{p}"))
    r = ref[f"{p} 1048576"]
    # Compare every statistic the committed CSV has a column for (the Stage 2
    # CSV predates a few later parser columns).
    diffs = [k for k in parse_stats.STATS
             if k in r and r[k] != ("" if row[k] is None else str(row[k]))]
    print(f"pattern {p}: validation={'ok' if not probs else probs} cycles={row['cycles']} "
          f"committed={r['cycles']} differing_stats={diffs}")
    bad += bool(probs) or bool(diffs)
print("RESULT:", "reproduced exactly" if not bad else f"{bad} runs differ")
sys.exit(1 if bad else 0)
EOF
