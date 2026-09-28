#!/usr/bin/env python3
"""Parse, validate, and record a finished sweep; then trim its outputs.

  collect.py <experiment_id> [--keep] [--archive]

For every run in $AF_SCRATCH/runs/<id>/manifest.json: parse stats.txt,
validate (handoff Section 5, rule 2), and write one row per run into
results/<study>.csv, replacing earlier rows of the same experiment so the
command is idempotent. Runs that fail validation stay in the CSV with their
problems in `validation`; analysis code keeps only `validation == ok`.

Cross-run check: ROI committed instructions must match across hardware
configurations for the same binary and arguments (same binary_sha256 and
workload args); a mismatch marks every run in the group.

Afterwards each run directory keeps only stats.txt, config.ini,
config.json, and af_meta.json (the resolved options are merged into
af_meta.json first), unless --keep. --archive packs the sweep directory
into $AF_SCRATCH/archive/<id>.tar.gz and removes it.
"""
import argparse
import collections
import csv
import json
import os
import shutil
import sys
import tarfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_stats  # noqa: E402

KEEP = {"stats.txt", "config.ini", "config.json", "af_meta.json"}
ID_COLS = [
    "experiment_id", "run_index", "run_name", "archforge_commit", "archforge_dirty",
    "gem5_tag", "gem5_commit", "workload", "variant", "compiler", "cflags",
    "input_size", "workload_args", "binary_sha256", "cpu", "clock",
    "l1i_size", "l1i_assoc", "l1d_size", "l1d_assoc", "l2_size", "l2_assoc",
    "line_size", "prefetcher", "prefetch_level", "mem_type", "mem_latency",
    "rob", "lq", "sq", "num_cores", "slurm_job_id", "slurm_array_job_id",
    "slurm_array_task_id", "date", "wall_seconds", "validation",
]
META_KEYS = ("archforge_commit", "archforge_dirty", "gem5_tag", "gem5_commit",
             "binary_sha256", "slurm_job_id", "slurm_array_job_id",
             "slurm_array_task_id", "date", "wall_seconds")
OPT_KEYS = ("cpu", "clock", "l1i_size", "l1i_assoc", "l1d_size", "l1d_assoc",
            "l2_size", "l2_assoc", "line_size", "prefetcher", "prefetch_level",
            "mem_type", "mem_latency", "rob", "lq", "sq", "num_cores")


def parse_manifest_runs(man):
    rows = []
    for r in man["runs"]:
        out = r["outdir"]
        row = {"experiment_id": man["id"], "run_index": r["index"], "run_name": r["name"],
               "workload": r["workload"], "variant": r["variant"],
               "compiler": r["compiler"], "cflags": r["cflags"],
               "input_size": r["input_size"], "workload_args": r["workload_args"]}
        if not os.path.exists(os.path.join(out, "stats.txt")):
            row["validation"] = "missing output"
            rows.append(row)
            continue
        stats, probs, meta, opt = parse_stats.parse_run(out)
        if "options" not in meta:
            meta["options"] = opt
            json.dump(meta, open(os.path.join(out, "af_meta.json"), "w"), indent=1)
        row.update({k: meta.get(k, "") for k in META_KEYS})
        row.update({k: opt.get(k, "") for k in OPT_KEYS})
        if meta.get("archforge_dirty"):
            probs.append("archforge tree had uncommitted changes")
        row["validation"] = "; ".join(probs) if probs else "ok"
        row.update(stats)
        rows.append(row)
    return rows


def check_insts(rows):
    groups = collections.defaultdict(list)
    for row in rows:
        if row.get("sim_insts") and int(row.get("num_cores") or 1) == 1:
            groups[(row.get("binary_sha256"), row.get("workload_args"))].append(row)
    for g in groups.values():
        vals = [row["sim_insts"] for row in g]
        if min(vals) != max(vals):
            msg = f"ROI insts differ across configs ({min(vals)}..{max(vals)})"
            for row in g:
                row["validation"] = msg if row["validation"] == "ok" else row["validation"] + "; " + msg


def write_csv(path, exp_id, rows):
    old = []
    if os.path.exists(path):
        with open(path, newline="") as f:
            old = [r for r in csv.DictReader(f) if r["experiment_id"] != exp_id]
    cols = ID_COLS + list(parse_stats.STATS) + parse_stats.DERIVED + list(parse_stats.MULTI)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in old + rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in cols})


def trim(man):
    for r in man["runs"]:
        out = r["outdir"]
        if not os.path.isdir(out):
            continue
        for f in os.listdir(out):
            if f not in KEEP:
                p = os.path.join(out, f)
                shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("experiment_id")
    ap.add_argument("--keep", action="store_true", help="do not trim run dirs")
    ap.add_argument("--archive", action="store_true")
    a = ap.parse_args()
    root = os.environ["AF_ROOT"]
    sweep = os.path.join(os.environ["AF_SCRATCH"], "runs", a.experiment_id)
    man = json.load(open(os.path.join(sweep, "manifest.json")))
    rows = parse_manifest_runs(man)
    check_insts(rows)
    csv_path = os.path.join(root, "results", f"{man['study']}.csv")
    write_csv(csv_path, man["id"], rows)
    n_ok = sum(1 for row in rows if row.get("validation") == "ok")
    print(f"{man['id']}: {len(rows)} runs, {n_ok} valid -> {csv_path}")
    for row in rows:
        if row.get("validation") != "ok":
            print(f"  r{row['run_index']:04d} {row['run_name']}: {row['validation']}")
    if not a.keep:
        trim(man)
    if a.archive:
        adir = os.path.join(os.environ["AF_SCRATCH"], "archive")
        os.makedirs(adir, exist_ok=True)
        tpath = os.path.join(adir, f"{man['id']}.tar.gz")
        # Write to a temporary name and rename, so an interrupted run never
        # leaves a truncated archive in place of a good one (this happened
        # once to s6-codesign; see docs/progress.md).
        with tarfile.open(tpath + ".tmp", "w:gz") as t:
            t.add(sweep, arcname=man["id"])
        os.replace(tpath + ".tmp", tpath)
        shutil.rmtree(sweep)
        print("archived", tpath, os.path.getsize(tpath), "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
