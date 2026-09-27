#!/usr/bin/env python3
"""Compare gem5 stats.txt files for determinism.

  compare_stats.py a/stats.txt b/stats.txt [c/stats.txt ...]

Prints every statistic whose value differs between the first file and any
other, split into host-dependent (expected to vary) and simulated (must not
vary). Exit status 1 if any simulated statistic differs or the dump counts
differ.
"""
import re
import sys

# Statistics that measure the simulator process rather than the simulated
# machine. Resolved from gem5 v25.1 stats.txt output (docs/stage0.md).
HOST_RE = re.compile(r"^(host[A-Za-z]*)$|\.host[A-Za-z]*$")


def load(path):
    dumps, cur = [], None
    for line in open(path):
        if line.startswith("---------- Begin Simulation Statistics"):
            cur = {}
        elif line.startswith("---------- End Simulation Statistics"):
            dumps.append(cur)
            cur = None
        elif cur is not None and line.strip() and not line.startswith("#"):
            parts = line.split("#")[0].split()
            if len(parts) >= 2:
                cur[parts[0]] = " ".join(parts[1:])
    return dumps


def main(paths):
    ref = load(paths[0])
    bad = False
    host_names = set()
    for p in paths[1:]:
        other = load(p)
        if len(other) != len(ref):
            print(f"DUMP COUNT differs: {paths[0]}={len(ref)} {p}={len(other)}")
            bad = True
            continue
        for d, (ra, rb) in enumerate(zip(ref, other)):
            for k in sorted(set(ra) | set(rb)):
                if ra.get(k) != rb.get(k):
                    if HOST_RE.search(k):
                        host_names.add(k)
                    else:
                        bad = True
                        print(f"SIM DIFF dump{d} {k}: {ra.get(k)} vs {rb.get(k)} ({p})")
    print(f"dumps per file: {len(ref)}; stats in dump0: {len(ref[0]) if ref else 0}")
    print("host-dependent stats that differed:", ", ".join(sorted(host_names)) or "none")
    print("RESULT:", "NONDETERMINISTIC" if bad else "IDENTICAL apart from host stats")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
