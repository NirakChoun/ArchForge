#!/bin/bash
#SBATCH --account=publicgrp
#SBATCH --partition=high
#SBATCH --cpus-per-task=1
#SBATCH --output=/home/%u/af_scratch/logs/slurm-%A_%a.out
# One task of a sweep array; submitted only by run_sweep.py, which sets
# --array, --time, --mem, and --job-name. Task i runs manifest entry
# offset+i, so large sweeps can be split into several <=200-task arrays.
#   array_task.sh <manifest.json> <offset>
set -uo pipefail
MANIFEST="$1"; OFFSET="${2:-0}"
cd ~/ArchForge
source scripts/env.sh
IDX=$((OFFSET + SLURM_ARRAY_TASK_ID))
mapfile -t ARGV < <(python -c '
import json, sys
m = json.load(open(sys.argv[1])); r = m["runs"][int(sys.argv[2])]
print(r["outdir"]); print(m["config"])
for a in r["argv"]: print(a)
' "$MANIFEST" "$IDX")
export AF_META_EXTRA=$(python -c '
import json, sys
m = json.load(open(sys.argv[1])); r = m["runs"][int(sys.argv[2])]
print(json.dumps({"experiment_id": m["id"], "run_index": int(sys.argv[2]), "run": r["name"]}))
' "$MANIFEST" "$IDX")
echo "host: $(hostname) task: $IDX date: $(date -Is)"
scripts/run_sim.sh "${ARGV[@]}"
