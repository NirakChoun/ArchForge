# Stage 2: microbenchmark suite and simulator validation

Results pending. This section records predictions written before any Stage 2 simulation ran.

Every microbenchmark lives in `workloads/micro/`, marks its region of interest with `m5_reset_stats` / `m5_dump_stats`, checks its own result, and prints PASS or FAIL. All run on the baseline system (`docs/architecture.md`) as experiment `experiments/s2_micro.yaml`. Work per run is fixed within a benchmark, so only locality or branch pattern changes across its rows.

## Study: sequential sum across the hierarchy

Question: does sustained load throughput step down where the array stops fitting in L1D (32 KiB) and in L2 (1 MiB)?
Suspected mechanism: capacity misses; beyond L2 every new line comes from DRAM, but sequential access lets the O3 core overlap many misses.
Hypothesis and prediction: IPC is flat and highest for 8 to 32 KiB (L1D miss rate near 0), drops for 64 KiB to 1 MiB (L1D misses of about 1 per 8 loads, L2 hits), and drops again at 2 MiB and above (L2 misses, DRAM reads about 1 per 8 loads). The DRAM plateau is set by DRAM bandwidth and the 16 L1D MSHRs, not by the full DRAM latency per miss, so its slowdown relative to L2 is well under the latency ratio. The 1 MiB point sits near the edge (the L2 also holds instruction and page-table lines) and may already miss.
Independent variable: array size, 8 KiB to 16 MiB.
Controlled variables: 2M loads per run, baseline hardware, binary.
Metrics: IPC, L1D and L2 demand miss rates, DRAM bytes read per load.

## Study: strided access

Question: how does cycles per load change as the stride grows from 1 to 64 elements (8 B to 512 B)?
Hypothesis and prediction: lines touched per load rise as stride/8 until stride 8 (one line per load), then stay at one. L1D misses per load: 1/8, 1/4, 1/2, 1, 1, 1, 1. Cycles grow with misses up to stride 8 and then flatten, possibly with a further rise at 32 and 64 elements (256 B and 512 B) because consecutive accesses land in different DRAM rows more often.
Independent variable: stride. Controlled: 8 MiB array (8x L2), 1M loads.

## Study: dependent pointer chase

Question: does a single chain of dependent loads expose the full latency of each level?
Hypothesis and prediction: cycles per step approximate the load-to-use latency of the level holding the ring: a few cycles at 16 KiB (L1D), roughly L1 plus L2 latency (about 12 to 25 cycles) at 256 KiB, and DRAM latency (well over 100 cycles at 3 GHz) at 4 MiB and 16 MiB. IPC at 16 MiB is far below the streaming benchmarks because no two misses overlap.
Independent variable: footprint 16 KiB, 256 KiB, 4 MiB, 16 MiB. Controlled: 1M steps, one node per line, one untimed warm-up cycle.

## Study: independent chains (memory-level parallelism)

Question: do independent miss chains overlap in the O3 core?
Hypothesis and prediction: with a 16 MiB footprint, total cycles for 1M steps fall nearly in proportion to the chain count at 2 and 4 chains, and less than proportionally at 8, as the 16 L1D MSHRs, the 32-entry load queue, and DRAM bank parallelism start to bind.
Independent variable: chains 1, 2, 4, 8. Controlled: 16 MiB footprint, 1M total steps.

## Study: compute-bound loop

Question: what IPC does the core reach with no memory traffic?
Hypothesis and prediction: four independent multiply-add chains, each limited by the multiplier latency (3 cycles for a 64-bit multiply in gem5's default O3 functional units is expected), give about 4 multiplies per 3 cycles; with about 10 instructions per iteration the IPC should be roughly 3 to 4. L1D accesses in the ROI are near zero.

## Study: branch patterns

Question: does the default TournamentBP predictor behave as expected on regular and irregular outcome sequences?
Hypothesis and prediction: always taken and alternating: misprediction rate near 0 (alternating is learnable from local history). Random: about 50 percent of the data-dependent branch mispredicts, which is one of about 3 conditional branches per iteration, so about 15 to 17 percent overall and a large IPC drop. Sorted: the same bytes as random but in two runs, so near 0 percent.
Controlled: identical loop, identical bytes for random and sorted, 1M iterations.

## Study: cache conflicts at fixed capacity

Question: does associativity, not capacity, decide hits when lines share a set?
Hypothesis and prediction: at 4 KiB spacing all lines map to one L1D set. Up to 8 lines (the L1D associativity) the loop hits in L1D; at 9 lines and above LRU with round-robin access misses on every access in L1D but hits in L2 (the lines are spread over L2 sets). At 64 B spacing, 9, 16, and 24 lines hit in L1D. At 64 KiB spacing the lines share one L1D set and one L2 set: 16 lines hit in L2, 17 and 24 lines miss in L2 as well and go to DRAM.
Independent variable: lines and spacing. Controlled: 1M loads, footprint at most 24 lines.
