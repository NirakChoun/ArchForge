"""Stage 5 tables: application workloads and the characterization table."""
from common import load, md_table

FMT = {"ipc": "{:.3f}", "cyc_per_unit": "{:.2f}", "l1d_line_per_unit": "{:.4f}",
       "l2_line_per_unit": "{:.4f}", "dram_b_per_unit": "{:.3f}", "l1d_mpki_line": "{:.2f}",
       "l2_mpki": "{:.2f}", "br_mpki_commit": "{:.2f}", "dram_b_per_inst": "{:.3f}",
       "l2_mlp": "{:.2f}", "l1d_mlp": "{:.2f}", "cycles_rel": "{:.2f}"}


def units(r):
    a = [int(x) for x in str(r["workload_args"]).split()]
    w = r["workload"]
    if w == "matmul":
        return a[1] ** 3          # inner multiply-adds
    if w == "aos_soa":
        return a[1] * a[2] * a[3]  # field values summed
    if w == "reduce":
        return a[0] * a[1]
    if w == "sort":
        return a[0]
    return None


def prep(study):
    df = load(study)
    df["units"] = df.apply(units, axis=1)
    df["cyc_per_unit"] = df["cycles"] / df["units"]
    df["l1d_line_per_unit"] = df["l1d_demand_mshr_misses"] / df["units"]
    df["l2_line_per_unit"] = df["l2_demand_misses"] / df["units"]
    df["dram_b_per_unit"] = df["dram_bytes_read"] / df["units"]
    df["l1d_mpki_line"] = 1000 * df["l1d_demand_mshr_misses"] / df["sim_insts"]
    # Mispredictions resolved at execute on the committed path are not
    # separated by gem5; iew.branchMispredicts counts those that caused a squash.
    df["br_mpki_commit"] = 1000 * df["o3_iew_branch_mispredicts"] / df["sim_insts"]
    df["dram_b_per_inst"] = df["dram_bytes_read"] / df["sim_insts"]
    return df


def main():
    df = prep("stage5_workloads").sort_values("run_index")
    print("\n### Matrix multiply (N = 320; unit = one inner multiply-add)\n")
    mm = df[df.workload == "matmul"].copy()
    mm["cycles_rel"] = mm["cycles"] / mm[mm.variant == "ijk"]["cycles"].iloc[0]
    print(md_table(mm, ["variant", "sim_insts", "cycles", "cycles_rel", "ipc", "cyc_per_unit",
                        "l1d_line_per_unit", "l2_line_per_unit", "dram_b_per_unit", "l2_mlp"], FMT))
    print("\n### AoS vs SoA (unit = one field value summed)\n")
    print(md_table(df[df.workload == "aos_soa"], ["variant", "sim_insts", "cycles", "ipc",
                                                  "cyc_per_unit", "l1d_line_per_unit",
                                                  "dram_b_per_unit", "l2_mlp"], FMT))
    print("\n### Characterization (per 1000 instructions unless noted)\n")
    print(md_table(df, ["workload", "variant", "ipc", "l1d_mpki_line", "l2_mpki",
                        "br_mpki_commit", "dram_b_per_inst", "l2_mlp"], FMT))


if __name__ == "__main__":
    main()
