#!/usr/bin/env python3
"""Expand an experiment YAML into a manifest and submit it as a capped array.

  run_sweep.py experiments/<exp>.yaml [--dry-run] [--pilot 0,5,9] [--chunk K]

Experiment file (see experiments/README.md for the full schema):
  id, study, description, config, time, mem, base (options for every run),
  workloads (list), hardware ({list: [...]} and/or {grid: {opt: [values]}}),
  or blocks: a list of {workloads, hardware} sets expanded one after another.
Runs are the cross product workloads x hardware. Every run gets its own
output directory under $AF_SCRATCH/runs/<id>/. Workload binaries are copied
into the sweep directory first, so a later rebuild cannot change a sweep
that is still running; each run records the binary's sha256.

Cluster rules enforced here (handoff Section 3): one CPU per task, at most
8 concurrent tasks (%8), at most 200 tasks per submission, and no
submission while another ArchForge array is queued or running.
"""
import argparse
import itertools
import json
import os
import shutil
import subprocess
import sys

import yaml

MAX_TASKS = 200
CONCURRENCY = 8
DEFAULT_CFLAGS = "-O2 -march=x86-64 -static"


def expand(exp):
    # `blocks` lets one experiment hold several (workloads x hardware) sets,
    # e.g. one per cache parameter, each a one-variable sweep of its own.
    if exp.get("blocks"):
        runs = []
        for b in exp["blocks"]:
            sub = {k: v for k, v in exp.items() if k != "blocks"}
            sub.update(b)
            runs += expand(sub)
        return runs
    hw = exp.get("hardware", {}) or {}
    configs = [dict(c) for c in hw.get("list", [])]
    grid = hw.get("grid")
    if grid:
        keys = list(grid)
        for combo in itertools.product(*(grid[k] for k in keys)):
            configs.append(dict(zip(keys, combo)))
    if not configs:
        configs = [{}]
    runs = []
    for w in exp["workloads"]:
        for c in configs:
            opts = dict(exp.get("base", {}) or {})
            opts.update(w.get("options", {}) or {})
            opts.update(c)
            runs.append({"workload": w, "options": opts, "hw": c})
    return runs


def run_name(w, hw):
    parts = [w["name"], w.get("variant", "default"), str(w.get("input", ""))]
    parts += [f"{k}={v}" for k, v in sorted(hw.items())]
    return "|".join(p for p in parts if p)


def build_manifest(exp, root, sweep_dir):
    bin_dir = os.path.join(sweep_dir, "bin")
    os.makedirs(bin_dir, exist_ok=True)
    manifest = {"id": exp["id"], "study": exp["study"],
                "config": os.path.join(root, exp["config"]), "runs": []}
    for i, r in enumerate(expand(exp)):
        w = r["workload"]
        src = os.path.join(root, "workloads", "bin", w["binary"])
        dst = os.path.join(bin_dir, w["binary"])
        if not os.path.exists(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        argv = ["--binary", dst]
        if w.get("args"):
            argv += ["--args", str(w["args"])]
        for k, v in sorted(r["options"].items()):
            argv += [f"--{k}", str(v)]
        manifest["runs"].append({
            "index": i,
            "name": run_name(w, r["hw"]),
            "outdir": os.path.join(sweep_dir, f"r{i:04d}"),
            "argv": argv,
            "workload": w["name"],
            "variant": w.get("variant", "default"),
            "input_size": str(w.get("input", "")),
            "workload_args": str(w.get("args", "")),
            "cflags": w.get("cflags", DEFAULT_CFLAGS),
            "compiler": w.get("compiler", "gcc 11.4.0"),
            "options": r["options"],
        })
    return manifest


def active_arrays():
    out = subprocess.run(["squeue", "--me", "-h", "-o", "%j|%T"],
                         capture_output=True, text=True, check=True).stdout
    return [l for l in out.splitlines() if l.startswith("af-sw")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("experiment")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--pilot", default="", help="comma-separated run indices")
    ap.add_argument("--chunk", type=int, default=0, help="which 200-task chunk")
    a = ap.parse_args()
    root = os.environ["AF_ROOT"]
    exp = yaml.safe_load(open(a.experiment))
    sweep_dir = os.path.join(os.environ["AF_SCRATCH"], "runs", exp["id"])
    os.makedirs(sweep_dir, exist_ok=True)
    manifest = build_manifest(exp, root, sweep_dir)
    mpath = os.path.join(sweep_dir, "manifest.json")
    json.dump(manifest, open(mpath, "w"), indent=1)
    n = len(manifest["runs"])
    print(f"{exp['id']}: {n} runs -> {mpath}")
    if a.dry_run:
        for r in manifest["runs"]:
            print(r["index"], r["name"])
        return 0
    if active_arrays():
        print("refusing: another ArchForge array is queued or running:",
              active_arrays())
        return 1
    if a.pilot:
        idx = [int(x) for x in a.pilot.split(",")]
        spec, offset = ",".join(map(str, idx)) + f"%{CONCURRENCY}", 0
    else:
        offset = a.chunk * MAX_TASKS
        m = min(MAX_TASKS, n - offset)
        if m <= 0:
            print("chunk out of range")
            return 1
        spec = f"0-{m - 1}%{CONCURRENCY}"
    cmd = ["sbatch", "--parsable", f"--array={spec}", f"--time={exp['time']}",
           f"--mem={exp.get('mem', '4G')}", f"--job-name=af-sw-{exp['id']}",
           os.path.join(root, "scripts", "array_task.sh"), mpath, str(offset)]
    print(" ".join(cmd))
    jid = subprocess.run(cmd, capture_output=True, text=True,
                         check=True).stdout.strip()
    print("submitted", jid)
    with open(os.path.join(sweep_dir, "submissions.log"), "a") as f:
        f.write(f"{jid} {spec} offset={offset}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
