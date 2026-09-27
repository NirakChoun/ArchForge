# Stage 3: statistics parser and experiment runner

Every simulation goes through one pipeline: a YAML experiment file becomes a manifest and a capped Slurm array (`run_sweep.py`), each task runs gem5 and records provenance (`array_task.sh`, `run_sim.sh`), and `collect.py` parses, validates, and writes one CSV row per run. The parser is unit-tested against a saved gem5 v25.1 run.

## Pipeline

```
experiments/<exp>.yaml
   |  run_sweep.py      expand workloads x hardware, snapshot binaries, write manifest.json,
   v                    sbatch --array=0-N%8 (<=200 tasks, one array at a time)
array_task.sh -> run_sim.sh   gem5.opt -re -d r<idx> configs/archforge_se.py ...
   |                          af_meta.json: job/array IDs, commits, binary sha256, exit code, PASS/FAIL, wall time
   v
collect.py <id>     parse_stats.parse_run on each run, validation, cross-run instruction check,
   |                results/<study>.csv (rows of this experiment replaced), trim run dirs
   v
results/<study>.csv  -> analysis scripts (analysis/*.py) -> plots and tables in docs
```

## Validation (handoff Section 5, rule 2)

A row has `validation == ok` only if all of the following hold; otherwise the column lists every problem and analysis code drops the row.

| Check | How |
|---|---|
| Workload printed PASS | `run_sim.sh` greps `simout.txt` for a line `PASS` and stores it in `af_meta.json` |
| gem5 exited normally | exit code 0 |
| Intended configuration | `validate_config`: CPU base class and `X86ISA`, L1I/L1D/L2 size and associativity, line size, clock period, prefetcher presence and type at the requested level, DDR4-2400 (`tCK=833`) or SimpleMemory with the requested latency, O3 ROB/LQ/SQ when set |
| Stats from the ROI | exactly two dumps in `stats.txt` (the workload's `m5_dump_stats` and the one at exit); dump 0 is used and must contain committed instructions |
| Same work across hardware | ROI `simInsts` identical for every run of the same binary (sha256) and arguments within an experiment |
| Provenance | the ArchForge tree had no uncommitted changes to tracked files when the run started |

## Parser

`scripts/parse_stats.py` maps CSV columns to gem5 statistics (listed with meanings in `docs/stats.md`). gem5 omits zero-valued statistics from `stats.txt`, so an absent statistic is recorded as 0 when the SimObject that owns it exists in `config.ini`, and left empty when it does not (O3-only columns on other CPU models, prefetcher columns without a prefetcher).

`tests/test_parse_stats.py` (13 tests, `python -m pytest tests`) checks, against the saved Stage 2 pilot run `conflict 24 65536 43690` in `tests/data/s2_conflict/`: the dump count and ROI selection, exact values of the main statistics and derived ratios, the zero-versus-empty rule, acceptance of the correct configuration, detection of eight kinds of configuration mismatch, and rejection of a run whose workload did not print PASS.

## Pilot and sizing rule

Each sweep's `time` is set from a pilot of its heaviest configurations: at most twice the slowest pilot, rounded up to 15 minutes. The Stage 2 pilot (array 24154357: seqsum 16 MiB, stride 64, chase 16 MiB, conflict 24 lines at 64 KiB) took at most 5 min 30 s and 80 MB, so Stage 2 uses 15 minutes and 2 GB per task. The pilot runs were started while one tracked file differed from the commit only in its executable bit; `collect.py` flagged them, so they served only for sizing and were rerun in the full sweep.

## Output retention

After collection each run directory keeps `stats.txt`, `config.ini`, `config.json`, and `af_meta.json` (with the resolved options merged in). `collect.py --archive` packs a finished sweep into `~/af_scratch/archive/<id>.tar.gz`, outside the repo.
