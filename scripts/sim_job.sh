#!/bin/bash
#SBATCH --job-name=af-sim
#SBATCH --account=publicgrp
#SBATCH --partition=high
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --output=/home/%u/af_scratch/logs/slurm-%j.out
# Template for one gem5 simulation (gem5 is single-threaded: one CPU).
#   sbatch [--time=HH:MM:SS] scripts/sim_job.sh <outdir> <config.py> [config args...]
# Sweeps use run_sweep.py, which submits array_task.sh with the same body.
set -uo pipefail
cd ~/ArchForge
source scripts/env.sh
echo "host: $(hostname) job: ${SLURM_JOB_ID:-none} date: $(date -Is)"
scripts/run_sim.sh "$@"
