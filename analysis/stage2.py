"""Stage 2 tables and figures from results/stage2_micro.csv."""
import matplotlib.pyplot as plt

from common import line, load, md_table, save, style


def work_units(r):
    """Loads (or steps, or iterations) the ROI performs, from the arguments."""
    a = [int(x) for x in str(r["workload_args"]).split()]
    w = r["workload"]
    if w == "seqsum":
        n = a[0] // 8
        return max(1, a[1] // n) * n
    if w in ("stride",):
        return a[2]
    if w in ("chase", "multistream"):
        return a[2]
    if w == "compute":
        return a[0]
    if w == "branch":
        return a[1]
    if w == "conflict":
        return a[0] * a[2]
    return None


def size_bytes(s):
    s = str(s)
    for suf, m in (("KiB", 1 << 10), ("MiB", 1 << 20)):
        if s.endswith(suf):
            return int(s[:-3]) * m
    return None


def main():
    df = load("stage2_micro")
    df["units"] = df.apply(work_units, axis=1)
    df["cyc_per_unit"] = df["cycles"] / df["units"]
    df["dram_b_per_unit"] = df["dram_bytes_read"] / df["units"]
    df["l1d_miss_per_unit"] = df["l1d_demand_misses"] / df["units"]
    # Line misses (new MSHR allocations); demand_misses also counts accesses
    # that found the line already in flight.
    df["l1d_line_miss_per_unit"] = df["l1d_demand_mshr_misses"] / df["units"]
    fmt = {"ipc": "{:.3f}", "cyc_per_unit": "{:.2f}", "l1d_miss_rate": "{:.3f}",
           "l2_miss_rate": "{:.3f}", "dram_b_per_unit": "{:.2f}",
           "l1d_miss_per_unit": "{:.3f}", "br_mispredict_rate": "{:.4f}",
           "o3_rob_full_events": "{:.0f}", "l1d_line_miss_per_unit": "{:.3f}",
           "l1d_mlp": "{:.2f}", "l2_mlp": "{:.2f}"}
    cols = ["workload", "variant", "input_size", "sim_insts", "cycles", "ipc",
            "cyc_per_unit", "l1d_miss_per_unit", "l1d_line_miss_per_unit",
            "l2_miss_rate", "dram_b_per_unit", "l1d_mlp"]
    for w in ["seqsum", "stride", "chase", "multistream", "compute", "conflict"]:
        sub = df[df["workload"] == w].sort_values("run_index")
        print(f"\n### {w}\n")
        print(md_table(sub, cols, fmt))
    sub = df[df["workload"] == "branch"].sort_values("run_index")
    print("\n### branch\n")
    print(md_table(sub, ["variant", "sim_insts", "cycles", "ipc", "br_cond_predicted",
                         "br_cond_incorrect", "br_mispredict_rate",
                         "o3_commit_squashed_insts"], fmt))

    # Figure: cycles per load/step against footprint for seqsum and chase.
    fig, ax = plt.subplots(figsize=(7, 4))
    for i, w in enumerate(["seqsum", "chase"]):
        sub = df[df["workload"] == w].copy()
        sub["b"] = sub["input_size"].map(size_bytes)
        sub = sub.sort_values("b")
        line(ax, sub["b"] / 1024, sub["cyc_per_unit"], i,
             "sequential sum (cycles/load)" if w == "seqsum" else "pointer chase (cycles/step)")
    for x, lab in ((32, "L1D 32 KiB"), (1024, "L2 1 MiB")):
        ax.axvline(x, color="#8a8984", linewidth=1, linestyle="--")
        ax.text(x * 1.05, ax.get_ylim()[1] * 0.9, lab, color="#52514e", fontsize=8)
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    style(ax, "Cycles per access vs footprint (baseline O3)", "footprint (KiB)",
          "cycles per load or step")
    ax.legend(frameon=False)
    print("\n" + save(fig, "s2_footprint.png"))

    # Figure: memory-level parallelism, cycles per step against chain count.
    fig, ax = plt.subplots(figsize=(6, 3.6))
    sub = df[(df["input_size"] == "16MiB") & df["workload"].isin(["chase", "multistream"])].copy()
    sub["chains"] = sub["variant"].str[1:].astype(int)
    sub = sub.sort_values("chains")
    line(ax, sub["chains"], sub["cyc_per_unit"], 0, "16 MiB rings")
    ax.set_xscale("log", base=2)
    ax.set_xticks([1, 2, 4, 8], ["1", "2", "4", "8"])
    style(ax, "Independent chains overlap misses", "independent chains",
          "cycles per step (all chains)")
    print(save(fig, "s2_chains.png"))


if __name__ == "__main__":
    main()
