"""Stage 7 tables: gcc optimization levels and TensorForge kernels."""
import matplotlib.pyplot as plt
import numpy as np

from common import INK, INK2, load, md_table, save

FMT = {"ipc": "{:.3f}", "cycles_rel": "{:.3f}", "insts_rel": "{:.3f}",
       "l1d_line_per_unit": "{:.4f}", "l2_per_unit": "{:.4f}", "dram_b_per_unit": "{:.3f}",
       "insts_per_unit": "{:.2f}", "cyc_per_unit": "{:.3f}"}


def units(r):
    a = [int(x) for x in str(r["workload_args"]).split()] if str(r["workload_args"]) not in ("", "nan") else []
    if r["workload"] == "matmul":
        rows = a[3] if len(a) > 3 else a[1]
        return rows * a[1] ** 2
    if r["workload"] == "reduce":
        return a[0] * a[1]
    if r["workload"] == "tf_matmul":
        return int(r["input_size"].split("-")[0][1:]) ** 3
    return None


def prep(study):
    df = load(study)
    df["units"] = df.apply(units, axis=1)
    df["insts_per_unit"] = df["sim_insts"] / df["units"]
    df["cyc_per_unit"] = df["cycles"] / df["units"]
    df["l1d_line_per_unit"] = df["l1d_demand_mshr_misses"] / df["units"]
    df["l2_per_unit"] = df["l2_demand_misses"] / df["units"]
    df["dram_b_per_unit"] = df["dram_bytes_read"] / df["units"]
    return df


def flags():
    df = prep("stage7_flags")
    df["opt"] = df["binary_sha256"].map(lambda _: "")
    df["opt"] = df["cflags"].str.replace(" -march=x86-64 -static", "", regex=False)
    out = []
    for (w, v), g in df.groupby(["workload", "variant"], sort=False):
        base = g[g.opt == "-O2"].iloc[0]
        g = g.copy()
        g["cycles_rel"] = g["cycles"] / base.cycles
        g["insts_rel"] = g["sim_insts"] / base.sim_insts
        out.append(g)
    import pandas as pd
    df = pd.concat(out).sort_values("run_index")
    print("\n### Optimization level (relative to -O2; unit = multiply-add or element)\n")
    print(md_table(df, ["workload", "variant", "opt", "sim_insts", "insts_rel", "cycles",
                        "cycles_rel", "ipc", "insts_per_unit", "cyc_per_unit",
                        "l1d_line_per_unit", "dram_b_per_unit"], FMT))


def tensorforge():
    df = prep("stage7_tensorforge")
    cfgs = ["scalar", "tiled32", "vec", "tiled64vec"]
    l1s = ["16KiB", "32KiB", "64KiB"]
    l2s = ["256KiB", "512KiB", "1MiB", "2MiB"]
    print("\n### TensorForge kernels: cycles per multiply-add\n")
    rows = []
    for c in cfgs:
        for l1 in l1s:
            r = {"config": c, "L1D": l1}
            for l2 in l2s:
                s = df[(df.variant == c) & (df.l1d_size == l1) & (df.l2_size == l2)]
                r[l2] = s["cyc_per_unit"].iloc[0] if len(s) else np.nan
            rows.append(r)
    import pandas as pd
    t = pd.DataFrame(rows)
    print(md_table(t, ["config", "L1D"] + l2s, {l2: "{:.3f}" for l2 in l2s}))
    base = df[(df.l1d_size == "32KiB") & (df.l2_size == "1MiB")].set_index("variant")
    print("\n### TensorForge kernels at the baseline hardware\n")
    base = base.reindex(cfgs).reset_index()
    print(md_table(base, ["variant", "sim_insts", "insts_per_unit", "cycles", "ipc",
                          "l1d_line_per_unit", "l2_per_unit", "dram_b_per_unit"], FMT))
    fig, axes = plt.subplots(1, 4, figsize=(12, 3.4), sharey=True)
    for ax, c in zip(axes, cfgs):
        m = np.array([[t[(t.config == c) & (t.L1D == l1)][l2].iloc[0] for l2 in l2s] for l1 in l1s])
        ax.imshow(m, cmap="Blues", vmin=0, vmax=np.nanmax(t[l2s].values), aspect="auto")
        for i in range(3):
            for j in range(4):
                ax.text(j, i, f"{m[i, j]:.2f}", ha="center", va="center", fontsize=8,
                        color="white" if m[i, j] > 0.6 * np.nanmax(t[l2s].values) else INK)
        ax.set_xticks(range(4), [s.replace("KiB", "K").replace("MiB", "M") for s in l2s], fontsize=8)
        ax.set_title(c, loc="left", fontsize=10, color=INK)
        ax.set_xlabel("L2 size", color=INK2, fontsize=9)
        for s in ax.spines.values():
            s.set_visible(False)
    axes[0].set_yticks(range(3), l1s, fontsize=8)
    axes[0].set_ylabel("L1D size", color=INK2)
    fig.suptitle("TensorForge f32 matmul N = 256, SSE2: cycles per multiply-add", x=0.01,
                 ha="left", fontsize=11, color=INK)
    print(save(fig, "s7_tensorforge.png"))


if __name__ == "__main__":
    import sys
    for w in (sys.argv[1:] or ["flags", "tensorforge"]):
        globals()[w]()
