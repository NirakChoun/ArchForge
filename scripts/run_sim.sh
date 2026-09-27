#!/bin/bash
# Run one gem5 simulation and write af_meta.json next to stats.txt.
#   run_sim.sh <outdir> <config.py> [config args...]
# Called by sim_job.sh (single job) and array_task.sh (sweeps); expects
# scripts/env.sh to be sourced already. Extra provenance for the metadata
# file can be passed in AF_META_EXTRA (a JSON object string).
set -uo pipefail
OUT="$1"; CFG="$2"; shift 2
rm -rf "$OUT"; mkdir -p "$OUT"
t0=$(date +%s)
"$GEM5" -re -d "$OUT" "$CFG" "$@"
rc=$?
t1=$(date +%s)
status="FAIL"
grep -q '^PASS$' "$OUT/simout.txt" 2>/dev/null && status="PASS"
python - "$OUT" "$rc" "$((t1 - t0))" "$status" "$CFG" "$@" <<'EOF'
import datetime, hashlib, json, os, subprocess, sys
out, rc, wall, status, cfg, *args = sys.argv[1:]
def git(d, *c):
    return subprocess.run(["git", "-C", d, *c], capture_output=True, text=True).stdout.strip()
binary = args[args.index("--binary") + 1] if "--binary" in args else ""
sha = hashlib.sha256(open(binary, "rb").read()).hexdigest() if binary else ""
tail = open(os.path.join(out, "simout.txt")).read().splitlines()[-12:] if os.path.exists(os.path.join(out, "simout.txt")) else []
meta = {
    "slurm_job_id": os.environ.get("SLURM_JOB_ID", ""),
    "slurm_array_job_id": os.environ.get("SLURM_ARRAY_JOB_ID", ""),
    "slurm_array_task_id": os.environ.get("SLURM_ARRAY_TASK_ID", ""),
    "host": os.uname().nodename,
    "date": datetime.datetime.now().isoformat(timespec="seconds"),
    "archforge_commit": git(os.environ["AF_ROOT"], "rev-parse", "--short=12", "HEAD"),
    "archforge_dirty": bool(git(os.environ["AF_ROOT"], "status", "--porcelain", "--untracked-files=no")),
    "gem5_tag": git(os.environ["GEM5_DIR"], "describe", "--tags"),
    "gem5_commit": git(os.environ["GEM5_DIR"], "rev-parse", "HEAD"),
    "config": cfg, "config_args": args, "binary_sha256": sha,
    "exit_code": int(rc), "wall_seconds": int(wall), "workload_status": status,
    "simout_tail": tail,
}
meta.update(json.loads(os.environ.get("AF_META_EXTRA", "{}") or "{}"))
json.dump(meta, open(os.path.join(out, "af_meta.json"), "w"), indent=1)
print(json.dumps({k: meta[k] for k in ("exit_code", "wall_seconds", "workload_status")}))
EOF
exit $rc
