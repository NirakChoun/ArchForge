#!/usr/bin/env python3
"""Compare each option run's config.ini with the baseline (check_options.sh).

For every case: (1) validate_config must accept it, i.e. config.ini holds
exactly the requested values, and (2) the set of config.ini fields that
differ from the baseline is printed, so an option that silently changes
nothing, or changes something unexpected, is visible.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_stats  # noqa: E402

IGNORE = {"cmd", "executable", "input", "output", "errout"}


def flat(cp):
    return {(s, k): v for s in cp.sections() for k, v in cp.items(s)
            if k not in IGNORE}


def main(base, cases):
    ref = flat(parse_stats.load_config(os.path.join(base, "baseline", "config.ini")))
    bad = 0
    for c in cases:
        name = c.split("|", 1)[0]
        d = os.path.join(base, name)
        opt = json.load(open(os.path.join(d, "af_options.json")))
        cp = parse_stats.load_config(os.path.join(d, "config.ini"))
        probs = parse_stats.validate_config(cp, opt)
        cur = flat(cp)
        diff = sorted(k for k in set(ref) | set(cur) if ref.get(k) != cur.get(k))
        hello = "Hello world!" in open(os.path.join(d, "simout.txt")).read()
        ok = not probs and hello and (name == "baseline" or diff)
        bad += not ok
        shown = ", ".join(f"{s}.{k}={cur.get((s, k))}" for s, k in diff[:4])
        more = f" (+{len(diff) - 4} more)" if len(diff) > 4 else ""
        print(f"{'OK ' if ok else 'BAD'} {name:12s} validate={'ok' if not probs else probs} "
              f"ran={hello} changed={len(diff)}: {shown}{more}")
    print("RESULT:", "all options verified" if not bad else f"{bad} cases failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2:]))
