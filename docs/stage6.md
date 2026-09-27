# Stage 6: co-design study, tiling x cache hierarchy

Results pending. Question, hypothesis, and predictions below were written before any Stage 6 simulation ran.

## Study: tiling x private cache capacity for matrix multiply

Question: how does loop tiling change matrix multiply's sensitivity to private cache capacity, and does choosing tile size and cache configuration jointly beat choosing either alone?

Suspected mechanism: in the tiled ikj kernel (`workloads/apps/matmul.c`), the inner two loops reuse one T x T block of B (8T^2 bytes) across T rows of A and C, and each row segment of C (8T bytes) across T values of k. Reuse is captured when the block of B plus the active C segments fit in the level that serves them: for T = 32 the B block is 8 KiB, for T = 64 it is 32 KiB. The untiled ikj kernel streams a full row of B (N x 8 bytes) per k and reuses B only across i, so it needs all of B (800 KiB at N = 320, 1.15 MiB at N = 384) resident in L2 to avoid DRAM traffic.

Hypothesis and prediction:
1. Untiled is the most capacity-sensitive: its cycles fall sharply once L2 holds B (1 MiB at N = 320, 2 MiB at N = 384) and depend little on L1D.
2. Tiled kernels are insensitive to L2 once the B block fits in L1D or L2, so the cycles spread across the four L2 sizes is much smaller than for untiled.
3. The best tile grows with L1D: the largest tile whose B block fits comfortably in L1D (about half of it, leaving room for A and C) should win: T about 16 to 24 at 16 KiB, 32 at 32 KiB, 32 to 48 at 64 KiB. Very small tiles (8) lose to loop overhead (more instructions per multiply-add).
4. Joint optimum: with small caches, tiling recovers most of what a larger cache would buy; the best joint choice beats the best hardware-only change (largest caches, untiled) and the best software-only change (best tile at baseline 32 KiB / 1 MiB), but by a small margin over software-only, because once the tile fits, extra capacity has little left to remove.

Independent variables (designed factorial): tile {untiled, 8, 12, 16, 24, 32, 48, 64} x L1D {16, 32, 64 KiB} x L2 {256 KiB, 512 KiB, 1 MiB, 2 MiB} x N {320, 384}.
Controlled variables: O3 at baseline, 8-way L1D and 16-way L2, 64 B lines, no prefetcher, DDR4-2400, gcc -O2, fixed inputs.
Metrics: ROI cycles (primary; instruction counts differ by tile), IPC, L1D and L2 line misses per multiply-add, DRAM bytes, L2 MLP.
Validation: standard checks; ROI instructions identical across all 12 hardware configurations for each (tile, N).
Cost awareness: qualitative only. Larger caches cost area, energy, and access latency; this model keeps cache latencies fixed, so it overstates the benefit of larger caches.
