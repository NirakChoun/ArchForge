# Stage 5: workloads and software variants

On the baseline system, the loop order and tiling of matrix multiply changed L1D misses by 80x but cycles by at most 1.30x, because at N = 320 all of B (800 KiB) fits in the 1 MiB L2 and the O3 core hides L2 hits; data layout changed the cost of a one-field sum by 7.2x; and the reduction and sort sit at opposite corners (DRAM-bound streaming versus branch-bound). All 9 runs passed validation (experiment `s5-workloads`, `results/stage5_workloads.csv`, tables from `analysis/stage5.py`). Predictions were committed (`ee4cb99`) before the runs.

Workloads are in `workloads/apps/`, all self-checking: matrix multiply uses small-integer doubles so every variant produces bit-identical results, AoS/SoA sums are exact in double, the reduction is checked modulo 2^32, and the sort checks order and multiset.

Common controlled variables: baseline O3 system (`docs/architecture.md`), gcc 11.4 `-O2 -march=x86-64 -static`, fixed seeds. Validation: PASS, configuration, ROI dump, clean tree.

## Study: matrix multiply loop order and tiling

Question: how do loop order and tiling change matrix multiply's memory behaviour at N = 320?
Suspected mechanism: naive ijk walks a column of B in the inner loop (one new line per multiply-add); ikj streams rows of B and C; tiling keeps a 32 x 32 block of B in L1D while it is reused.
Hypothesis and prediction (from `ee4cb99`): ijk has an L1D line miss on nearly every inner iteration and the most cycles; ikj about 1/8 line misses per B access with remaining L2 misses; tiled 32 the fewest misses and cycles.
Independent variable: variant. Controlled: N = 320 (three 800 KiB matrices).
Metrics: cycles (instruction counts differ by variant), IPC, L1D and L2 line misses per multiply-add, DRAM bytes, MLP.

Results (unit: one inner multiply-add; 32.8M per run)

| Variant | Instructions | Cycles | Cycles vs ijk | IPC | L1D line misses/MAC | L2 misses/MAC | DRAM B/MAC | ROB-full events |
|---|---|---|---|---|---|---|---|---|
| ijk | 230.2M | 104.1M | 1.00 | 2.210 | 1.021 | 0.0012 | 0.074 | 17.4M |
| ikj | 262.9M | 135.5M | 1.30 | 1.940 | 0.126 | 0.0012 | 0.075 | 18.5M |
| tiled 32 | 240.0M | 105.1M | 1.01 | 2.282 | 0.0125 | 0.0027 | 0.170 | 11.9M |

Observations
- L1D line misses per multiply-add matched the mechanism: about 1 for ijk (column walk), 1/8 for ikj (unit stride), 1/80 for tiled 32.
- L2 misses were near zero for all three: B (800 KiB) fits in the 1 MiB L2, so every L1D miss was an L2 hit.
- Cycles did not follow L1D misses: ijk, with 8x the L1D misses of ikj, was 1.30x faster, and tiling bought nothing over ijk (1.01). The prediction that ijk would be slowest failed.
- ikj retired 8.0 instructions per multiply-add against 7.0 for ijk (a load and a store of `c[j]` per iteration instead of a register accumulator) and hit a full ROB 18.5M times.
- Tiled 32 read 2.3x more DRAM bytes than untiled (0.170 vs 0.074 per MAC) while having fewer L1D misses.

Interpretation: TODO(Nirak)

Competing explanations for ikj being slower than ijk: the extra load and store per multiply-add, and a structural limit on stores (one store per multiply-add must drain to L1D after commit), versus the latency of the L2 hits being fully hidden for ijk because its loads are independent. For tiled 32's extra DRAM traffic: re-reading C's row segments once per kk block.
Follow-up: Stage 6 (hardware sweep where B no longer fits in L2).

## Study: array of structs vs struct of arrays

Question: how much does data layout change the cost of summing one field versus all fields?
Suspected mechanism: a one-field sum over AoS fetches a whole 64-byte record per 8 useful bytes.
Hypothesis and prediction: one field: AoS moves 8x the DRAM bytes of SoA and is several times slower; eight fields: similar bytes and speed.
Independent variable: layout x fields summed. Controlled: 128K records (8 MiB); one field summed 4 times, eight fields once.

Results (unit: one field value summed)

| Case | Cycles/value | L1D line misses/value | DRAM B/value | L2 MLP | IPC |
|---|---|---|---|---|---|
| AoS, 1 field | 22.89 | 1.000 | 64.0 | 8.49 | 0.524 |
| SoA, 1 field | 3.16 | 0.125 | 2.0 | 2.04 | 1.267 |
| AoS, 8 fields | 7.52 | 0.125 | 8.0 | 2.67 | 0.665 |
| SoA, 8 fields | 7.01 | 0.125 | 8.0 | 2.83 | 0.571 |

Observations
- One field: AoS moved 32x the DRAM bytes of SoA (64 vs 2 bytes per value) and took 7.2x the cycles. SoA read only 2 bytes per value from DRAM, not 8: its 1 MiB field array fits in L2, so passes 2 to 4 hit in L2.
- Eight fields: the layouts moved the same bytes and differed by 7 percent, as predicted.
- AoS one-field sustained 8.5 outstanding L2 misses: its misses are independent (one per record), so MLP rose rather than latency being exposed.

Interpretation: TODO(Nirak)

Competing explanations: the factor between 7.2x (cycles) and 32x (bytes) reflects overlap (higher MLP for AoS) and the SoA passes being L2 hits rather than DRAM streams.
Follow-up: E1 (layout x line size x prefetcher).

## Study: contrast workloads

Question: where do a streaming reduction and a comparison sort sit on locality, branching, memory intensity, and MLP?
Hypothesis and prediction: reduction: DRAM-bound like the sequential sum; sort of 256K keys: L2-resident and branch-bound with many mispredictions.

Results and characterization table (per 1000 instructions unless noted)

| Workload | Variant | IPC | L1D line MPKI | L2 MPKI | Branch mispredicts PKI | DRAM bytes/instruction | L2 MLP |
|---|---|---|---|---|---|---|---|
| matmul | ijk | 2.210 | 145.3 | 0.17 | 0.45 | 0.011 | 0.08 |
| matmul | ikj | 1.940 | 15.7 | 0.15 | 0.39 | 0.009 | 0.06 |
| matmul | tiled 32 | 2.282 | 1.7 | 0.36 | 4.41 | 0.023 | 0.13 |
| aos_soa | AoS, 1 field | 0.524 | 83.3 | 83.3 | 0.00 | 5.33 | 8.49 |
| aos_soa | SoA, 1 field | 1.267 | 31.3 | 7.8 | 0.00 | 0.50 | 2.04 |
| aos_soa | AoS, 8 fields | 0.665 | 25.0 | 25.0 | 0.00 | 1.60 | 2.67 |
| aos_soa | SoA, 8 fields | 0.571 | 31.3 | 31.3 | 0.00 | 2.00 | 2.83 |
| reduce | 4 MiB, 2 passes | 0.745 | 15.6 | 15.6 | 0.00 | 1.00 | 1.72 |
| sort | 256K keys | 1.304 | 2.5 | 0.00 | 54.6 | 0.000 | 0.00 |

Branch mispredictions are `iew.branchMispredicts` (mispredictions that caused a squash) per 1000 committed instructions.

Characterization in words: matrix multiply at N = 320 is compute-bound on the baseline (B fits in L2) with high L1D traffic for ijk; the one-field AoS sum is the most memory-intensive workload (5.3 DRAM bytes per instruction) and has the highest MLP; the reduction is a DRAM stream with modest MLP; the sort is cache-resident and branch-bound (55 mispredictions per 1000 instructions).

Observations: the reduction and sort matched the prediction.

Interpretation: TODO(Nirak)
