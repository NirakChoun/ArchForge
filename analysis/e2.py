"""E2 table: two-core false sharing (shared line vs padded counters)."""
from common import load, md_table

FMT = {"cyc_per_inc": "{:.2f}", "l1d_miss_per_inc": "{:.3f}", "readex_per_inc": "{:.3f}",
       "snoops_per_inc": "{:.3f}", "snoop_b_per_inc": "{:.1f}", "slowdown": "{:.2f}"}


def main():
    df = load("e2_falseshare")
    iters = df["workload_args"].str.split().str[1].astype(int)
    inc = 2 * iters  # increments over both threads
    df["cyc_per_inc"] = df["mc_cycles_max"] / iters  # per increment of one thread
    df["l1d_miss_per_inc"] = df["mc_l1d_demand_mshr_misses"] / inc
    df["readex_per_inc"] = df["mc_membus_readex_req"] / inc
    df["snoops_per_inc"] = df["mc_membus_snoops"] / inc
    df["snoop_b_per_inc"] = df["mc_membus_snoop_bytes"] / inc
    pad = df[df.variant == "padded"].set_index("cpu")["mc_cycles_max"]
    df["slowdown"] = df.apply(lambda r: r.mc_cycles_max / pad[r.cpu], axis=1)
    df = df.sort_values(["cpu", "variant"])
    print("\n### False sharing (per increment; cycles are the slower core's ROI cycles "
          "per iteration of one thread)\n")
    print(md_table(df, ["cpu", "variant", "mc_insts_sum", "mc_cycles_max", "cyc_per_inc",
                        "slowdown", "l1d_miss_per_inc", "readex_per_inc",
                        "mc_membus_upgrade_req", "snoops_per_inc", "snoop_b_per_inc"], FMT))


if __name__ == "__main__":
    main()
