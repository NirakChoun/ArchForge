# Experiment files

One YAML file per sweep. `scripts/run_sweep.py` expands it into runs (every workload crossed with every hardware configuration), writes `$AF_SCRATCH/runs/<id>/manifest.json`, and submits a capped Slurm array; `scripts/collect.py <id>` parses and validates the runs into `results/<study>.csv`.

| Key | Meaning |
|---|---|
| `id` | Experiment ID; names the sweep directory and the Slurm job (`af-sw-<id>`) |
| `study` | Results CSV name (`results/<study>.csv`); several experiments can share one |
| `description` | Free text |
| `config` | gem5 config script, relative to the repo root |
| `time`, `mem` | Per-task Slurm limits; `time` is at most 2x the slowest pilot, rounded up to 15 min |
| `base` | Config options applied to every run (option names without `--`) |
| `hardware.list` | Explicit list of option dicts, one configuration each |
| `hardware.grid` | `{option: [values]}`; the cross product is appended to the list |
| `blocks` | Optional list of `{workloads, hardware}` sets, each expanded as above and concatenated (one experiment, several one-variable sweeps) |
| `workloads` | List of `{name, binary, variant, input, args, cflags, compiler, options}`; `binary` is a file in `workloads/bin/`, `options` are per-workload config options |

Commands:

```
source scripts/env.sh
python scripts/run_sweep.py experiments/<file>.yaml --dry-run      # list runs with indices
python scripts/run_sweep.py experiments/<file>.yaml --pilot 3,9    # pilot runs (any index list;
                                                                   # also used to submit the rest)
python scripts/run_sweep.py experiments/<file>.yaml [--chunk K]    # tasks 200K..200K+199
python scripts/collect.py <id> [--archive]
```
