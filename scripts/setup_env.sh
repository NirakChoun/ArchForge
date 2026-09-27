#!/bin/bash
#SBATCH --job-name=af-env
#SBATCH --account=publicgrp
#SBATCH --partition=high
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:45:00
#SBATCH --output=/home/%u/af_scratch/logs/slurm-%j.out
# Create ~/archforge-env from environment.yml. Runs in Slurm to keep the
# solver and package extraction off the login node.
set -euo pipefail
export MAMBA_ROOT_PREFIX="$HOME/.mamba"
MM="$HOME/.local/bin/micromamba"
cd ~/ArchForge
echo "host: $(hostname)  job: ${SLURM_JOB_ID:-none}  date: $(date -Is)"
du -sh ~ 2>/dev/null
if [[ ! -d "$HOME/archforge-env" ]]; then
  "$MM" create -y -p "$HOME/archforge-env" -f environment.yml
fi
# The package cache counts against the 20 GB home quota.
"$MM" clean -y --all >/dev/null
"$MM" env export -p "$HOME/archforge-env" > "$HOME/af_scratch/logs/archforge-env.export.yml"
source scripts/env.sh
python --version; scons --version | head -2
python -c "import yaml, numpy, pandas, matplotlib, pytest; print('imports ok')"
du -sh "$HOME/archforge-env" ~
