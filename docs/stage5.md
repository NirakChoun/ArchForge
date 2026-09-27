# Stage 5: workloads and software variants

Results pending. Predictions below were written before any Stage 5 simulation ran.

Workloads in `workloads/apps/`, all self-checking (exact integer checksums; matrix multiply uses small-integer doubles so every variant produces bit-identical results). Experiment `experiments/s5_workloads.yaml` runs each variant once on the baseline O3 system.

## Study: matrix multiply loop order and tiling

Question: how do loop order and tiling change matrix multiply's memory behaviour at N = 320 (three 800 KiB matrices, 2.4 MiB total, larger than the 1 MiB L2)?
Suspected mechanism: naive ijk walks a column of B in the inner loop (stride N x 8 = 2560 B), touching a new line on every iteration; ikj streams rows of B and C with unit stride; tiling keeps a 32 x 32 block of B (8 KiB) and a row segment of C in L1D while it is reused.
Hypothesis and prediction: ijk has an L1D line miss on nearly every inner iteration and the lowest IPC; ikj has about 1/8 line misses per B access, but B (800 KiB) plus C rows do not stay in L2 across i iterations, so L2 misses remain; tiled 32 has the fewest L1D and L2 misses and the fewest cycles. Instruction counts differ by variant (tiled adds loop overhead), so cycles, not IPC, is the comparison metric.
Independent variable: variant (ijk, ikj, tiled 32). Controlled: N = 320, inputs, baseline hardware.
Metrics: cycles, IPC, L1D and L2 line misses per inner iteration, DRAM bytes, MLP.

## Study: array of structs vs struct of arrays

Question: how much does data layout change the cost of summing one field versus all fields?
Suspected mechanism: summing one field of a 64-byte record fetches a whole line per record in AoS, but only 8 bytes per record in SoA.
Hypothesis and prediction: one field: AoS moves 8x the DRAM bytes of SoA (64 vs 8 bytes per record) and is several times slower; all 8 fields: both layouts move the same bytes and run at similar speed (SoA streams 8 arrays, AoS one), with the loop-carried floating-point add chain limiting both.
Independent variable: layout x fields summed. Controlled: 128K records (8 MiB), baseline hardware.

## Study: contrast workloads (reduction and sort)

Question: where do a streaming reduction and a comparison sort sit on locality, branching, memory intensity, and MLP?
Hypothesis and prediction: reduction over 4 MiB: sequential, DRAM-bound like the Stage 2 sequential sum beyond L2, near-zero mispredictions. Sort of 256K keys (1 MiB): mostly L2-resident, branch-bound, with a misprediction rate near the 50 percent expected of partition comparisons on random keys for the inner comparison branches.

## Characterization table

Filled in from results: locality (L1D and L2 line misses per 1000 instructions), branching (mispredictions per 1000 instructions), memory intensity (DRAM bytes per instruction), and MLP (average outstanding L2 misses).
