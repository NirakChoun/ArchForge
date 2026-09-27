# Parsed statistics

Each results CSV column below comes from one gem5 v25.1 statistic in the region-of-interest dump (dump 0) of `stats.txt`, resolved from runs of `configs/archforge_se.py` with one core. `scripts/parse_stats.py` holds the mapping. Absent statistics are 0 when their owning SimObject exists (gem5 omits zeros) and empty otherwise.

Prefixes: `CORE` = `board.processor.cores.core`, `L1D` = `board.cache_hierarchy.l1dcaches` (likewise `L1I`, `L2`), `MEM` = `board.memory.mem_ctrl` (DDR4), `SMEM` = `board.memory.module` (SimpleMemory). One tick is 1 ps; one cycle at 3 GHz is 333 ticks.

| Column | gem5 statistic | Meaning |
|---|---|---|
| sim_ticks | `simTicks` | Simulated time of the ROI, ticks |
| sim_insts / sim_ops | `simInsts` / `simOps` | Committed instructions / micro-ops in the ROI |
| cycles | `CORE.numCycles` | Core cycles in the ROI |
| ipc | `CORE.ipc` | Committed instructions per cycle |
| l1i/l1d/l2_demand_accesses | `<cache>.demandAccesses::total` | Demand (non-prefetch) reads and writes reaching the cache |
| l1i/l1d/l2_demand_misses | `<cache>.demandMisses::total` | Demand misses, including those merged into an outstanding MSHR |
| l1d_demand_mshr_misses | `L1D.demandMshrMisses::total` | Demand misses that allocated a new MSHR |
| l1d/l2_writebacks | `<cache>.writebacks::total` | Dirty lines written back to the next level |
| l2_overall_misses | `L2.overallMisses::total` | Demand plus prefetch misses at L2 |
| l1d/l2_demand_miss_latency | `<cache>.demandMissLatency::total` | Sum over demand misses of miss-to-fill time, ticks |
| dram_read_reqs / dram_write_reqs | `MEM.readReqs` / `MEM.writeReqs` | Requests accepted by the DDR4 controller |
| dram_bytes_read / dram_bytes_written | `MEM.dram.bytesRead::total` / `bytesWritten::total` | Bytes moved by the DRAM interface |
| dram_avg_mem_acc_lat_ticks | `MEM.dram.avgMemAccLat` | Mean controller access latency including queueing, ticks |
| smem_reads / smem_bytes_read | `SMEM.numReads::total` / `bytesRead::total` | SimpleMemory reads and bytes |
| br_cond_predicted / br_cond_incorrect | `CORE.branchPred.condPredicted` / `condIncorrect` | Conditional branches predicted / mispredicted (includes wrong-path branches on O3) |
| o3_rob_full_events, o3_iq_full_events, o3_lq_full_events, o3_sq_full_events | `CORE.rename.{ROB,IQ,LQ,SQ}FullEvents` | Times rename stalled because that structure was full |
| o3_lsq_full_events | `CORE.iew.lsqFullEvents` | Dispatch stalls on a full load/store queue |
| o3_lq_avg_occupancy | `CORE.lsq0.lqAvgOccupancy` | Mean load-queue occupancy |
| o3_iew_branch_mispredicts | `CORE.iew.branchMispredicts` | Mispredicted branches resolved at execute |
| o3_commit_squashed_insts | `CORE.commit.commitSquashedInsts` | Instructions squashed (wrong path) |
| pf_l1d_*, pf_l2_* | `<cache>.prefetcher.{pfIssued,pfUseful,pfUnused,accuracy,coverage}` | Stride prefetcher: issued, prefetched lines found in the cache by a later demand access, evicted unused, useful/issued, useful/(useful + demand misses). A prefetch still in flight when the demand arrives is counted as late, not useful, so accuracy and coverage understate prefetches that were issued in time to shorten the miss but not to complete before it |
| pf_*_identified, pf_*_late, pf_*_removed_demand | `<cache>.prefetcher.{pfIdentified,pfLate,pfRemovedDemand}` | Candidates generated; prefetches the demand access caught in flight (MSHR or write buffer); candidates dropped from the queue because a demand request for the line came first |

Derived columns: `cpi` = cycles / sim_insts; `l1d_miss_rate`, `l2_miss_rate` = demand misses / demand accesses; `l1d_mpki`, `l2_mpki`, `br_mpki` = per 1000 instructions; `br_mispredict_rate` = incorrect / predicted; `mem_read_bytes` = DRAM or SimpleMemory bytes read; `l1d_mlp`, `l2_mlp` = demand miss latency sum / sim_ticks, the average number of demand misses outstanding (Little's law).

Host-dependent statistics, never used: `hostSeconds`, `hostTickRate`, `hostInstRate`, `hostOpRate`, `hostMemory` (`docs/stage0.md`).
