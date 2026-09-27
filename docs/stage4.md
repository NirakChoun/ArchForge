# Stage 4: mechanism studies

Results pending. Hypotheses and predictions below were written before any Stage 4 simulation ran.

## Study: CPU model

Question: which mechanisms explain the IPC gap between TimingSimpleCPU, MinorCPU, and O3CPU on compute, streaming, and pointer-chase code?
Suspected mechanism: TimingSimple executes one instruction at a time and stalls for every memory access; Minor is an in-order pipeline that overlaps independent instructions but blocks on a load miss's consumer; O3 issues out of order up to 8 wide and overlaps independent misses.
Hypothesis and prediction: compute: TimingSimple IPC at or below 1, Minor about 1 to 2 (in-order, dual issue by default), O3 highest (3 or more) because the four multiply chains are independent. Streaming at 32 KiB (L1-resident): O3 well above Minor. Streaming at 16 MiB: O3's advantage grows because it keeps many line misses in flight; Minor and TimingSimple pay most of each miss latency. Pointer chase at 16 MiB: all three near the same cycles per step (DRAM latency per step), because no model can overlap dependent misses. Random branches: O3 loses the most relative to its compute IPC, since each mispredict flushes a deep, wide window.
Stage 2 follow-up (added before running): the 9- and 16-line conflict sets at 4 KiB spacing, which missed far less than cyclic LRU predicts on O3, miss on every access (L1D line misses per load 1.0) on TimingSimple, which has one access outstanding at a time. Minor, in order but pipelined, is expected close to 1.0 as well.
Independent variable: `--cpu`. Controlled variables: binaries, inputs, caches, memory. Validation adds: ROI committed instructions identical across the three models for each binary.
Metrics: IPC, cycles, L1D/L2 misses, DRAM reads, branch mispredictions, O3 ROB/IQ/LSQ full events.

## Study: memory-level parallelism

Question: does a larger ROB help only when independent misses exist?
Suspected mechanism: with one chain each load's address depends on the previous load, so at most one miss is outstanding whatever the window size; with k chains up to k misses can overlap if the ROB and load queue hold instructions from k chains' next steps.
Hypothesis and prediction: 1 chain: cycles per step equal to memory latency plus hierarchy overhead and flat across ROB 32 to 256. 2, 4, 8 chains: cycles fall with chain count as long as the ROB holds one step of every chain (about 3 to 4 instructions per step, so ROB 32 covers 8 chains); beyond that ROB size has little effect. The benefit of more chains scales with memory latency, so the 200 ns column shows the largest absolute savings. The load queue does not bind at 8 or more entries for up to 8 chains; LQ 8 may limit 8 chains slightly.
Independent variables: ROB {32, 64, 128, 192, 256} x chains {1, 2, 4, 8} x latency {50, 100, 200 ns}; LQ {8, 16, 32, 64} at ROB 192, 100 ns.
Controlled: 16 MiB footprint, 512K total steps, SimpleMemory at 19.2e9 B/s.

## Study: cache capacity, associativity, and line size

Question: does each parameter move the miss rate of the workload built to expose it, and by the mechanism expected?
Hypothesis and prediction:
- L1D capacity: 24 KiB footprints hit in 32 and 64 KiB and miss in 16 KiB (LRU with a cyclic sweep larger than the cache misses on nearly every line); 48 KiB footprints hit only in 64 KiB. Misses go to L2 in every case.
- L2 capacity: 768 KiB fits in 1 and 2 MiB and misses in 256 and 512 KiB; 1.5 MiB fits only in 2 MiB. The pointer chase converts each extra L2 miss into full DRAM latency; the sequential sum hides much of it.
- L1D associativity (6 and 12 lines in one set): 6 lines hit with 8 and 16 ways and miss with 2 and 4; 12 lines hit only with 16 ways.
- L2 associativity (12 and 24 lines in one L2 set, always missing in L1D): 12 lines hit in L2 with 16 and 32 ways; 24 lines hit only with 32 ways.
- Line size: sequential sum and stride 2 (16 B) gain from longer lines (fewer misses per byte used); stride 16 (128 B) gains nothing from 128 B lines over 64 B beyond fetching the unused half; the pointer chase is indifferent in misses but moves more DRAM bytes with longer lines.
Controlled: all other parameters at baseline; ROI work fixed per workload.

## Study: prefetching

Question: what does gem5's StridePrefetcher do for sequential, strided, and pointer-chase access, at L1D and at L2?
Suspected mechanism: a PC-indexed stride table detects constant address deltas per load instruction and issues prefetches ahead of the demand stream.
Hypothesis and prediction: sequential and strided loads: high accuracy (useful/issued above 0.8) and high coverage, L1D demand misses fall sharply, IPC rises; at stride 16 (128 B) prefetches still help but each covers one access. Pointer chase: the address deltas are random, so few or no prefetches are issued; if any are, they are useless and add DRAM traffic. Prefetching at L2 cuts L2 misses but not L1D misses, so its IPC gain is smaller than at L1D for streams.
Metrics: pfIssued, pfUseful, accuracy, coverage (gem5 statistics), L1D/L2 demand misses, DRAM bytes read versus the no-prefetch run.
