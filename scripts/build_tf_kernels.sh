#!/bin/bash
# Build TensorForge-generated f32 matmul kernels for the gem5 x86 baseline
# (SSE2, no AVX) and link each into a self-checking workload.
#   build_tf_kernels.sh <N>
# Uses TensorForge's installed tools read-only (~/TensorForge/build/bin and
# ~/tforge-env); nothing in ~/TensorForge is modified. Outputs go to
# workloads/bin/tf/. Runs on the login node: each compile takes seconds.
#
# TensorForge's own backend uses `llc -mcpu=native`, which on Hive emits AVX2
# and FMA. Here the same pipeline output is compiled with -mcpu=x86-64
# (SSE2 baseline) instead; that flag is the only backend change.
set -euo pipefail
N="$1"
AF="$HOME/ArchForge"
OUT="$AF/workloads/bin/tf"
TFOPT="$HOME/TensorForge/build/bin/tensorforge-opt"
TFENV="$HOME/tforge-env/bin"
mkdir -p "$OUT"
declare -A CFG=(
  [scalar]=""
  [tiled32]="tile-sizes=32,32"
  [vec]="reg-tile=6,16,4 vectorize=1"
  [tiled64vec]="tile-sizes=64,64 reg-tile=6,16,4 vectorize=1"
)
cat > "$OUT/matmul_$N.mlir" <<EOF
func.func @entry(%a: tensor<${N}x${N}xf32>, %b: tensor<${N}x${N}xf32>) -> tensor<${N}x${N}xf32> {
  %0 = tforge.matmul %a, %b : tensor<${N}x${N}xf32>, tensor<${N}x${N}xf32> -> tensor<${N}x${N}xf32>
  return %0 : tensor<${N}x${N}xf32>
}
EOF
for name in "${!CFG[@]}"; do
  opts="${CFG[$name]}"
  d="$OUT/$name-N$N"; mkdir -p "$d"
  if [[ -n "$opts" ]]; then flag="--tforge-cpu-pipeline=$opts"; else flag="--tforge-cpu-pipeline"; fi
  "$TFOPT" "$OUT/matmul_$N.mlir" "$flag" -o "$d/llvm.mlir"
  "$TFENV/mlir-translate" --mlir-to-llvmir "$d/llvm.mlir" -o "$d/k.ll"
  "$TFENV/opt" -O3 -mtriple=x86_64-unknown-linux-gnu -mcpu=x86-64 -S "$d/k.ll" -o "$d/k.opt.ll"
  "$TFENV/llc" -O3 -mtriple=x86_64-unknown-linux-gnu -mcpu=x86-64 -relocation-model=static \
    -filetype=obj "$d/k.opt.ll" -o "$d/k.o"
  gcc -O2 -march=x86-64 -static -Wall -I"$AF/workloads/common" -I"$M5_INC" -DAF_TF_N="$N" \
    -o "$OUT/tf_matmul_${name}_N$N" "$AF/workloads/apps/tf_matmul.c" "$d/k.o" "$M5_LIB/libm5.a"
  # Kernel-only AVX check: the object from llc, and the linked kernel symbol.
  n_k=$(objdump -d "$d/k.o" | grep -cE '%[yz]mm[0-9]' || true)
  n_sse=$(objdump -d "$d/k.o" | grep -cE 'mulps|addps' || true)
  echo "$name N=$N options='$opts' kernel_ymm_zmm=$n_k packed_sse_mul_add=$n_sse"
  [[ "$n_k" -eq 0 ]] || { echo "AVX found in $name"; exit 1; }
done
