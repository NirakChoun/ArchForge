#!/bin/bash
# Re-parse every archived sweep with the current parser so all results CSVs
# share one column set. Unpacks each archive into $AF_SCRATCH/runs, runs
# collect.py (which rewrites that experiment's rows), and re-archives it.
# Parsing only; no simulation. Run from the repo root after sourcing env.sh.
set -euo pipefail
cd "$AF_ROOT"
for t in "$AF_SCRATCH"/archive/*.tar.gz; do
  id=$(basename "$t" .tar.gz)
  tar -xzf "$t" -C "$AF_SCRATCH/runs"
  python scripts/collect.py "$id" --archive | head -1
done
