# Baseline system architecture

ArchForge simulates one x86-64 core in gem5 syscall-emulation (SE) mode with private L1I, L1D, and L2 caches and a single-channel DDR4-2400 memory controller. Every parameter below is a command-line option of `configs/archforge_se.py`; the default is what a study uses unless it names that parameter as its independent variable.

## What is gem5 and what is ArchForge

| Component | Provided by |
|---|---|
| CPU models (TimingSimpleCPU, MinorCPU, O3CPU for X86), TournamentBP branch predictor | gem5 v25.1.0.1 |
| Classic `Cache`, LRU replacement, `L2XBar`, `SystemXBar`, `StridePrefetcher` | gem5 |
| `DDR4_2400_8x8` DRAM interface, `ChanneledMemory`, `SingleChannelSimpleMemory`, `SimpleBoard`, `SimpleProcessor`, `Simulator` | gem5 standard library |
| `ArchForgeHierarchy` (cache wiring, parameterization, prefetcher placement) | ArchForge, `configs/archforge_se.py` |
| Option parsing, defaults, O3 structure overrides, per-run option record (`af_options.json`) | ArchForge |

`ArchForgeHierarchy` reproduces the port wiring of gem5's `PrivateL1PrivateL2CacheHierarchy`. It exists because that class fixes L1 associativity at 8, ignores the L2 associativity it is given (its `L2Cache` default of 16 wins), and attaches a `StridePrefetcher` to every cache it creates, which a prefetching study must control.

The DDR4 memory is built as `ChanneledMemory(DDR4_2400_8x8, 1 channel, interleave = max(64, line size))`. For 64-byte lines this is exactly the stdlib `SingleChannelDDR4_2400`; the stdlib wrapper fixes the interleave at 64 B and refuses 128-byte lines, and with one channel the interleave does not change address mapping.

## Defaults

| Option | Default | Source |
|---|---|---|
| `--cpu` | `o3` | Handoff: O3 is the centerpiece model |
| `--num-cores` | 1 | Handoff Stage 1 |
| `--clock` | 3GHz | Typical desktop/server core clock |
| `--l1i-size` / `--l1i-assoc` | 32KiB / 8 | Common x86 L1I size; gem5 stdlib `L1ICache` associativity |
| `--l1d-size` / `--l1d-assoc` | 32KiB / 8 | Skylake-family L1D; gem5 stdlib `L1DCache` associativity |
| `--l2-size` / `--l2-assoc` | 1MiB / 16 | Skylake-SP private L2; gem5 stdlib `L2Cache` associativity |
| `--line-size` | 64 | x86 line size; gem5 `System.cache_line_size` default |
| `--prefetcher` | `none` | Baseline without prefetching, so Stage 4 adds exactly one mechanism |
| `--prefetch-level` | `l1d` | Where the stride prefetcher goes when enabled |
| `--mem-type` | `DDR4_2400` | gem5 `DDR4_2400_8x8`, one channel |
| `--mem-latency` | empty (50ns when `--mem-type SimpleMemory`) | Only for DRAM-latency sweeps |
| `--mem-size` | 2GiB | Larger than any workload footprint |
| `--rob` / `--lq` / `--sq` | 192 / 32 / 32 (gem5 `BaseO3CPU` defaults) | gem5 `src/cpu/o3/BaseO3CPU.py` |

Fixed parameters (not options), from the gem5 v25.1 standard library cache classes `L1ICache`, `L1DCache`, `L2Cache`:

| Parameter | L1I | L1D | L2 |
|---|---|---|---|
| tag / data / response latency (cycles) | 1 / 1 / 1 | 1 / 1 / 1 | 10 / 10 / 1 |
| MSHRs / targets per MSHR | 16 / 20 | 16 / 20 | 20 / 12 |
| writeback_clean | False | False | False |
| replacement policy | LRU | LRU | LRU |
| clusivity | mostly inclusive | mostly inclusive | mostly inclusive |

O3 core parameters not listed are gem5 defaults and appear in every run's `config.ini`: fetch, decode, rename, issue, and commit width 8; 256 integer and 256 floating-point physical registers; `TournamentBP` conditional predictor. MinorCPU and TimingSimpleCPU use their gem5 defaults.

With `--line-size` below 64, the O3 core's `fetchBufferSize` (gem5 default 64 B) is set to the line size, because gem5 requires the fetch buffer to fit in one line. Studies that vary line size therefore also change the fetch buffer at 32 B.

`SingleChannelSimpleMemory` bandwidth is set to 19.2e9 B/s (one DDR4-2400 x64 channel; gem5 stores it as 52 ps per byte), so a latency sweep changes latency only.

Cache latencies are fixed in cycles and do not grow with capacity. A larger real cache is slower; this model does not charge for it (see Limitations in `docs/report.md`).

## Verification that options take effect

`scripts/check_options.sh` runs gem5's hello binary once at the baseline and once per non-default option value, and `scripts/check_options.py` checks each `config.ini` against the requested values and lists the fields that changed. Results are in `docs/stage1.md`.
