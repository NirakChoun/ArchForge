#!/bin/bash
#SBATCH --job-name=af-gem5-build
#SBATCH --account=publicgrp
#SBATCH --partition=high
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=03:00:00
#SBATCH --output=/home/%u/af_scratch/logs/slurm-%j.out
# Build gem5.opt for X86 and the x86 m5 utility library from the checked-out
# release tag in ~/gem5 (cloned on the login node by the Stage 0 procedure).
set -euo pipefail
cd ~/ArchForge
source scripts/env.sh
echo "host: $(hostname)  job: ${SLURM_JOB_ID:-none}  date: $(date -Is)"
echo "disk before: $(du -sh ~ 2>/dev/null | cut -f1)"
cd "$GEM5_DIR"
git describe --tags; git rev-parse HEAD
gcc --version | head -1
# Embed the system Python 3.10 (headers and libpython present on every node)
# rather than the environment's Python, so gem5.opt has no runtime dependency
# on the conda environment's shared libraries.
/usr/bin/python3-config --ldflags --embed
start=$(date +%s)
# gem5 v25.1 finds python3-config on PATH, so /usr/bin goes first for this
# step only; SCons itself still runs from the environment.
rm -rf build/X86
PATH=/usr/bin:$PATH "$AF_ENV/bin/scons" build/X86/gem5.opt -j 8
echo "gem5 build seconds: $(( $(date +%s) - start ))"
ls -la build/X86/gem5.opt
build/X86/gem5.opt --version 2>&1 | head -5 || true

cd util/m5
"$AF_ENV/bin/scons" build/x86/out/m5 -j 8
ls -la build/x86/out/
echo "disk after: $(du -sh ~ 2>/dev/null | cut -f1)"
du -sh "$GEM5_DIR" "$GEM5_DIR/build"
