"""E1 tables: AoS vs SoA x line size x stride prefetcher."""
import pandas as pd

from common import load, md_table

FMT = {"cyc_per_val": "{:.2f}", "line_per_val": "{:.4f}", "dram_b_per_val": "{:.2f}",
       "ratio": "{:.2f}", "pf_gain": "{:.2f}", "ipc": "{:.3f}", "l2_mlp": "{:.2f}"}


def main():
    df = load("e1_layout")
    a = df["workload_args"].str.split()
    df["values"] = a.str[1].astype(int) * a.str[2].astype(int) * a.str[3].astype(int)
    df["cyc_per_val"] = df["cycles"] / df["values"]
    df["line_per_val"] = df["l1d_demand_mshr_misses"] / df["values"]
    df["dram_b_per_val"] = df["dram_bytes_read"] / df["values"]
    df["layout"] = df["variant"].str[:3]
    df["fields"] = df["variant"].str[-2:]
    df = df.sort_values(["fields", "layout", "prefetcher", "line_size"])
    print("\n### All runs (unit = one field value summed)\n")
    print(md_table(df, ["variant", "line_size", "prefetcher", "cyc_per_val", "ipc",
                        "line_per_val", "dram_b_per_val", "l2_mlp", "pf_l1d_issued",
                        "pf_l1d_late"], FMT))
    rows = []
    for f in ["f1", "f8"]:
        for pf in ["none", "stride"]:
            for ls in [32, 64, 128]:
                s = df[(df.fields == f) & (df.prefetcher == pf) & (df.line_size == ls)].set_index("layout")
                rows.append({"fields": f, "prefetcher": pf, "line_size": ls,
                             "aos": s.loc["aos", "cyc_per_val"], "soa": s.loc["soa", "cyc_per_val"],
                             "ratio": s.loc["aos", "cyc_per_val"] / s.loc["soa", "cyc_per_val"]})
    t = pd.DataFrame(rows)
    print("\n### AoS / SoA cycle ratio\n")
    print(md_table(t, ["fields", "prefetcher", "line_size", "aos", "soa", "ratio"],
                   {"aos": "{:.2f}", "soa": "{:.2f}", "ratio": "{:.2f}"}))
    g = []
    for (v, ls), s in df.groupby(["variant", "line_size"]):
        s = s.set_index("prefetcher")
        g.append({"variant": v, "line_size": ls,
                  "pf_gain": s.loc["none", "cycles"] / s.loc["stride", "cycles"]})
    print("\n### Prefetcher speedup (none / stride)\n")
    print(md_table(pd.DataFrame(g), ["variant", "line_size", "pf_gain"], FMT))


if __name__ == "__main__":
    main()
