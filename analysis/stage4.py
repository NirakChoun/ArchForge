"""Stage 4 tables and figures (CPU model, MLP, caches, prefetching).

  python analysis/stage4.py [cpu|mlp|cache|prefetch ...]
"""
import sys

import matplotlib.pyplot as plt

from common import line, load, md_table, save, style


def pivot_md(piv, fmt="{:.2f}"):
    cols = list(piv.columns)
    names = list(piv.index.names)
    out = ["| " + " | ".join(names + [f"{c}" for c in cols]) + " |",
           "|" + "---|" * (len(names) + len(cols))]
    for idx, row in piv.iterrows():
        idx = idx if isinstance(idx, tuple) else (idx,)
        out.append("| " + " | ".join([str(i) for i in idx] + [fmt.format(v) for v in row]) + " |")
    return "\n".join(out)
from stage2 import work_units

FMT = {"ipc": "{:.3f}", "cyc_per_unit": "{:.2f}", "l1d_line_miss_per_unit": "{:.3f}",
       "l2_miss_rate": "{:.3f}", "dram_b_per_unit": "{:.2f}", "l1d_mlp": "{:.2f}",
       "l2_mlp": "{:.2f}", "br_mispredict_rate": "{:.4f}", "pf_l1d_accuracy": "{:.3f}",
       "pf_l1d_coverage": "{:.3f}", "pf_l2_accuracy": "{:.3f}", "pf_l2_coverage": "{:.3f}",
       "speedup": "{:.2f}", "mem_b_per_unit": "{:.2f}", "l2_line_miss_per_unit": "{:.3f}"}


def prep(study):
    df = load(study)
    df["units"] = df.apply(work_units, axis=1)
    df["cyc_per_unit"] = df["cycles"] / df["units"]
    df["l1d_line_miss_per_unit"] = df["l1d_demand_mshr_misses"] / df["units"]
    df["l2_line_miss_per_unit"] = df["l2_demand_misses"] / df["units"]
    df["dram_b_per_unit"] = df["dram_bytes_read"] / df["units"]
    df["mem_b_per_unit"] = df["mem_read_bytes"] / df["units"]
    return df


def cpu():
    df = prep("stage4_cpu")
    order = {"timing": 0, "minor": 1, "o3": 2}
    df["o"] = df["cpu"].map(order)
    df = df.sort_values(["run_index"])
    print("\n### CPU model\n")
    print(md_table(df, ["workload", "variant", "input_size", "cpu", "sim_insts", "ipc",
                        "cyc_per_unit", "l1d_line_miss_per_unit", "l2_mlp",
                        "br_mispredict_rate"], FMT))
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    keys = df[["workload", "variant", "input_size"]].drop_duplicates().values.tolist()
    labels = [f"{w} {v if v != 'default' else ''} {s}".replace("  ", " ") for w, v, s in keys]
    width = 0.26
    for i, c in enumerate(["timing", "minor", "o3"]):
        ys = [df[(df.workload == w) & (df.variant == v) & (df.input_size == s) & (df.cpu == c)]["ipc"].squeeze()
              for w, v, s in keys]
        ax.bar([k + (i - 1) * width for k in range(len(keys))], ys, width * 0.92,
               color=["#2a78d6", "#eb6834", "#1baf7a"][i], label=c)
    ax.set_xticks(range(len(keys)), labels, rotation=25, ha="right", fontsize=8)
    style(ax, "IPC by CPU model", "", "IPC")
    ax.legend(frameon=False, ncol=3)
    print(save(fig, "s4_cpu_ipc.png"))


def mlp():
    df = prep("stage4_mlp")
    df["chains"] = df["variant"].str[1:].astype(int)
    df["lat"] = df["mem_latency"].str.replace("ns", "").astype(int)
    # lq = 0 means the gem5 default (32); nonzero rows are the LQ sweep.
    grid = df[df["lq"] == 0]
    base = grid[grid.chains == 1].set_index(["rob", "lat"])["cycles"]
    grid = grid.copy()
    grid["speedup"] = grid.apply(lambda r: base[(r.rob, r.lat)] / r.cycles, axis=1)
    print("\n### MLP: cycles per step (ROB x chains x latency)\n")
    piv = grid.pivot_table(index=["lat", "rob"], columns="chains", values="cyc_per_unit")
    print(pivot_md(piv))
    print("\n### MLP: average outstanding L2 misses\n")
    print(pivot_md(grid.pivot_table(index=["lat", "rob"], columns="chains", values="l2_mlp")))
    print("\n### MLP: ROB-full events per step\n")
    grid["robfull_per_step"] = grid["o3_rob_full_events"] / grid["units"]
    print(pivot_md(grid.pivot_table(index=["lat", "rob"], columns="chains", values="robfull_per_step"), "{:.3f}"))
    lqs = df[df["lq"] != 0].copy()
    if len(lqs):
        print("\n### LQ sweep (ROB 192, 100 ns)\n")
        extra = grid[(grid.rob == 192) & (grid.lat == 100)].copy()
        extra["lq"] = 32
        both = __import__("pandas").concat([lqs, extra]).sort_values(["chains", "lq"])
        print(md_table(both, ["chains", "lq", "cyc_per_unit", "l2_mlp", "o3_lq_full_events"],
                       FMT))
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.6), sharey=True)
    for ax, lat in zip(axes, [50, 100, 200]):
        for i, ch in enumerate([1, 2, 4, 8]):
            s = grid[(grid.lat == lat) & (grid.chains == ch)].sort_values("rob")
            line(ax, s["rob"], s["cyc_per_unit"], i, f"{ch} chain{'s' if ch > 1 else ''}")
        ax.set_xscale("log", base=2)
        ax.set_yscale("log")
        ax.set_xticks([32, 64, 128, 256], ["32", "64", "128", "256"])
        ax.set_yticks([25, 50, 100, 200, 400], ["25", "50", "100", "200", "400"])
        ax.minorticks_off()
        style(ax, f"memory latency {lat} ns", "ROB entries", "cycles per step" if lat == 50 else "")
    axes[0].legend(frameon=False, fontsize=8)
    print(save(fig, "s4_mlp.png"))


def cache():
    df = prep("stage4_cache")
    for param, label in (("l1d_size", "L1D capacity"), ("l2_size", "L2 capacity"),
                         ("l1d_assoc", "L1D associativity"), ("l2_assoc", "L2 associativity"),
                         ("line_size", "line size")):
        exp_col = {"l1d_size": "l1d-size", "l2_size": "l2-size", "l1d_assoc": "l1d-assoc",
                   "l2_assoc": "l2-assoc", "line_size": "line-size"}[param]
        sub = df[df["run_name"].str.contains(exp_col + "=")].sort_values("run_index")
        print(f"\n### {label}\n")
        print(md_table(sub, ["workload", "variant", "input_size", param, "ipc", "cyc_per_unit",
                             "l1d_line_miss_per_unit", "l2_line_miss_per_unit",
                             "dram_b_per_unit"], FMT))


def prefetch():
    df = prep("stage4_prefetch")
    df["pf"] = df.apply(lambda r: "none" if r.prefetcher == "none" else f"stride@{r.prefetch_level}", axis=1)
    base = df[df.pf == "none"].set_index("workload_args")
    df["speedup"] = df.apply(lambda r: base.loc[r.workload_args, "cycles"] / r.cycles, axis=1)
    df["extra_dram"] = df.apply(
        lambda r: r.dram_bytes_read / base.loc[r.workload_args, "dram_bytes_read"] - 1, axis=1)
    FMT["extra_dram"] = "{:+.3f}"
    print("\n### Prefetching\n")
    print(md_table(df.sort_values("run_index"),
                   ["workload", "variant", "pf", "speedup", "cyc_per_unit", "l1d_line_miss_per_unit",
                    "l2_line_miss_per_unit", "pf_l1d_issued", "pf_l1d_useful", "pf_l1d_accuracy",
                    "pf_l1d_coverage", "pf_l2_issued", "pf_l2_useful", "pf_l2_accuracy",
                    "pf_l2_coverage", "extra_dram"], FMT))
    print("\n### Prefetch timeliness\n")
    print(md_table(df.sort_values("run_index"),
                   ["workload", "variant", "pf", "pf_l1d_identified", "pf_l1d_issued",
                    "pf_l1d_late", "pf_l1d_removed_demand", "pf_l2_identified", "pf_l2_issued",
                    "pf_l2_late", "pf_l2_removed_demand"], FMT))


if __name__ == "__main__":
    which = sys.argv[1:] or ["cpu", "mlp", "cache", "prefetch"]
    for w in which:
        globals()[w]()
