#!/bin/bash
# Verify that workload code contains no AVX (ymm/zmm) instructions.
#   check_no_avx.sh <binary> [binary ...]
# Two checks per binary:
#  1. The workload's own object file (<binary>.o) must have zero ymm/zmm uses.
#  2. The static binary is scanned too. Static glibc carries ifunc variants
#     (memcpy, strlen, ...) written for AVX2/AVX-512 that are selected at
#     runtime from CPUID. gem5's X86 CPUID does not report AVX, so those
#     variants are never called; they are counted and reported, not failed.
#     If one ever executed, gem5 would stop on an unimplemented instruction.
set -u
fail=0
for b in "$@"; do
  obj="$b.o"
  n_obj=$(objdump -d "$obj" | grep -cE '%[yz]mm[0-9]')
  n_bin=$(objdump -d "$b" | grep -cE '%[yz]mm[0-9]')
  # Functions in the binary that use ymm/zmm, to show they are libc ifunc variants.
  fns=$(objdump -d "$b" | awk '/^[0-9a-f]+ <.*>:$/ {f=$2} /%[yz]mm[0-9]/ {print f}' \
        | sort -u | grep -vE 'avx|evex|AVX|EVEX' | head -5 | tr '\n' ' ')
  status=OK
  [[ "$n_obj" -ne 0 ]] && { status=FAIL; fail=1; }
  [[ -n "$fns" ]] && { status="FAIL(non-avx-named fn: $fns)"; fail=1; }
  printf '%-28s object_ymm_zmm=%-4s binary_ymm_zmm=%-6s %s\n' "$(basename "$b")" "$n_obj" "$n_bin" "$status"
done
exit $fail
