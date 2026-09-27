# Stage 1: parameterized baseline system

`configs/archforge_se.py` builds the single-core SE-mode system from the gem5 standard library with every Section 6 parameter exposed as an option, and each option has been shown to change `config.ini` as intended. Defaults and their sources are in `docs/architecture.md`.

## Option verification

`scripts/check_options.sh` (one Slurm job, 1 CPU) ran gem5's hello binary 18 times: the baseline and one run per non-default option value. For every run, `scripts/check_options.py` confirmed that (1) hello printed its output, (2) `parse_stats.validate_config` accepts `config.ini` for the requested options, and (3) at least one `config.ini` field differs from the baseline.

| Case | Option | Fields changed | Key field |
|---|---|---|---|
| cpu-timing | `--cpu timing` | 734 | `core.type=BaseTimingSimpleCPU` |
| cpu-minor | `--cpu minor` | 1139 | `core.type=BaseMinorCPU` |
| clock | `--clock 2GHz` | 1 | `board.clk_domain.clock=500` (ps) |
| l1i-size / l1i-assoc | `16KiB` / `4` | 3 / 3 | `l1icaches.size=16384` / `assoc=4` |
| l1d-size / l1d-assoc | `64KiB` / `4` | 3 / 3 | `l1dcaches.size=65536` / `assoc=4` |
| l2-size / l2-assoc | `512KiB` / `8` | 3 / 3 | `l2caches.size=524288` / `assoc=8` |
| line-size | `128` | 10 | `board.cache_line_size=128`, tag block sizes |
| pf-l1d | `--prefetcher stride` | 53 | `l1dcaches.prefetcher` (StridePrefetcher) added |
| pf-l2 | `--prefetcher stride --prefetch-level l2` | 53 | `l2caches.prefetcher` added |
| mem-simple | `--mem-type SimpleMemory --mem-latency 80ns` | 156 | `board.memory.module` SimpleMemory, `latency=80000` |
| mem-size | `--mem-size 1GiB` | 2 | `board.mem_ranges=0:1073741824` |
| rob / lq / sq | `64` / `16` / `16` | 1 each | `numROBEntries`, `LQEntries`, `SQEntries` |

## Issues found and fixed

- `config.ini` records the C++ base class as `type` (`BaseO3CPU`, `DRAMInterface`), not the Python class name. Validation now checks the base class plus the core's `isa` child (`X86ISA`) for the CPU, and `tCK=833` (0.833 ns) to identify the DDR4-2400 timing set.
- `--line-size 128` failed: the stdlib `SingleChannelDDR4_2400` fixes the channel interleave at 64 B and gem5 rejects an interleave smaller than the line. The config now builds the same `ChanneledMemory` with interleave `max(64, line size)`; the 64-byte baseline is unchanged.
- The SimpleMemory bandwidth string `19.2GB/s` is parsed by gem5 with binary units (48.5 ps/byte, 20.6e9 B/s). It is now `17.88GiB/s`, which gem5 stores as 52 ps/byte, 19.2e9 B/s.
