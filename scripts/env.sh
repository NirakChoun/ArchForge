# Source this file (do not execute it): activates the ArchForge toolchain.
#   source scripts/env.sh
# Requires a login shell on Hive, because `module` is only defined there.

export MAMBA_ROOT_PREFIX="$HOME/.mamba"
export AF_ENV="$HOME/archforge-env"
export AF_ROOT="$HOME/ArchForge"
# gem5 lives outside the repo so it is never committed and can be rebuilt from its tag.
export GEM5_DIR="$HOME/gem5"
export GEM5="$GEM5_DIR/build/X86/gem5.opt"
export M5_INC="$GEM5_DIR/include"
export M5_LIB="$GEM5_DIR/util/m5/build/x86/out"
# Raw simulation output and Slurm logs; never inside the repo.
export AF_SCRATCH="$HOME/af_scratch"
mkdir -p "$AF_SCRATCH/logs" "$AF_SCRATCH/runs"

eval "$("$HOME/.local/bin/micromamba" shell hook -s bash)"
micromamba activate "$AF_ENV"
