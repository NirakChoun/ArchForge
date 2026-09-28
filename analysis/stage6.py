"""Stage 6 co-design analysis: tile x L1D x L2 for matmul at two sizes.

Baseline hardware: L1D 32 KiB, L2 1 MiB. Baseline software: untiled ikj.
Prints markdown tables and writes heat maps to docs/figures/.
"""
import matplotlib.pyplot as plt
import numpy as np

from common import INK, INK2, load, md_table, save

TILES = ["untiled", "t8", "t12", "t16", "t24", "t32", "t48", "t64"]
L1S = ["16KiB", "32KiB", "64KiB"]
L2S = ["256KiB", "512KiB", "1MiB", "2MiB"]
BASE_HW = ("32KiB", "1MiB")
FMT = {"cycles_rel": "{:.3f}", "ipc": "{:.3f}", "speedup": "{:.3f}",
       "l1d_line_per_mac": "{:.4f}", "l2_miss_per_mac": "{:.5f}", "dram_b_per_mac": "{:.4f}",
       "insts_per_mac": "{:.2f}", "l2_mlp": "{:.2f}"}


def prep():
    df = load("stage6_codesign")
    # input_size is "N<n>-R<rows>": a rows x N x N band of the product.
    df["N"] = df["input_size"].str.extract(r"N(\d+)")[0].astype(int)
    df["R"] = df["input_size"].str.extract(r"R(\d+)")[0].astype(int)
    macs = df["R"] * df["N"] ** 2
    df["l1d_line_per_mac"] = df["l1d_demand_mshr_misses"] / macs
    df["l2_miss_per_mac"] = df["l2_demand_misses"] / macs
    df["dram_b_per_mac"] = df["dram_bytes_read"] / macs
    df["insts_per_mac"] = df["sim_insts"] / macs
    return df


def cyc(df, n, tile, l1, l2):
    s = df[(df.N == n) & (df.variant == tile) & (df.l1d_size == l1) & (df.l2_size == l2)]
    return float(s["cycles"].iloc[0]) if len(s) == 1 else np.nan


def heatmaps(df, n):
    base = cyc(df, n, "untiled", *BASE_HW)
    fig, axes = plt.subplots(1, 4, figsize=(12, 4.2), sharey=True)
    vmax = max(cyc(df, n, t, a, b) for t in TILES for a in L1S for b in L2S) / base
    for ax, l2 in zip(axes, L2S):
        m = np.array([[cyc(df, n, t, l1, l2) / base for l1 in L1S] for t in TILES])
        ax.imshow(m, cmap="Blues", vmin=0, vmax=vmax, aspect="auto")
        best = np.unravel_index(np.nanargmin(m), m.shape)
        for i in range(len(TILES)):
            for j in range(len(L1S)):
                txt = f"{m[i, j]:.2f}"
                color = "white" if m[i, j] > 0.6 * vmax else INK
                weight = "bold" if (i, j) == best else "normal"
                ax.text(j, i, txt, ha="center", va="center", fontsize=8, color=color,
                        fontweight=weight)
        ax.set_xticks(range(len(L1S)), [s.replace("KiB", " KiB") for s in L1S], fontsize=8)
        ax.set_title(f"L2 {l2.replace('KiB', ' KiB').replace('MiB', ' MiB')}", loc="left",
                     fontsize=10, color=INK)
        ax.set_xlabel("L1D size", color=INK2, fontsize=9)
        for s in ax.spines.values():
            s.set_visible(False)
    axes[0].set_yticks(range(len(TILES)), TILES, fontsize=8)
    axes[0].set_ylabel("tile", color=INK2)
    fig.suptitle(f"matmul N = {n}: cycles relative to untiled on L1D 32 KiB / L2 1 MiB "
                 f"(bold = best per L2)", x=0.01, ha="left", fontsize=11, color=INK)
    return save(fig, f"s6_heatmap_N{n}.png")


def summary(df, n):
    sub = df[df.N == n]
    base = cyc(df, n, "untiled", *BASE_HW)
    print(f"\n### N = {n}: best tile per hardware configuration\n")
    rows = []
    for l1 in L1S:
        for l2 in L2S:
            h = sub[(sub.l1d_size == l1) & (sub.l2_size == l2)].sort_values("cycles")
            b = h.iloc[0]
            second = h.iloc[1]
            rows.append({"L1D": l1, "L2": l2, "best tile": b.variant,
                         "cycles_rel": b.cycles / base,
                         "runner-up": f"{second.variant} (+{100 * (second.cycles / b.cycles - 1):.1f}%)",
                         "untiled_rel": cyc(df, n, "untiled", l1, l2) / base})
    import pandas as pd
    t = pd.DataFrame(rows)
    print(md_table(t, ["L1D", "L2", "best tile", "cycles_rel", "runner-up", "untiled_rel"],
                   {"cycles_rel": "{:.3f}", "untiled_rel": "{:.3f}"}))

    hw_only = sub[sub.variant == "untiled"].sort_values("cycles").iloc[0]
    sw_only = sub[(sub.l1d_size == BASE_HW[0]) & (sub.l2_size == BASE_HW[1])].sort_values("cycles").iloc[0]
    joint = sub.sort_values("cycles").iloc[0]
    print(f"\n### N = {n}: hardware-only vs software-only vs joint\n")
    comp = pd.DataFrame([
        {"choice": "baseline", "tile": "untiled", "L1D": BASE_HW[0], "L2": BASE_HW[1], "speedup": 1.0},
        {"choice": "best hardware-only", "tile": "untiled", "L1D": hw_only.l1d_size,
         "L2": hw_only.l2_size, "speedup": base / hw_only.cycles},
        {"choice": "best software-only", "tile": sw_only.variant, "L1D": BASE_HW[0],
         "L2": BASE_HW[1], "speedup": base / sw_only.cycles},
        {"choice": "best joint", "tile": joint.variant, "L1D": joint.l1d_size,
         "L2": joint.l2_size, "speedup": base / joint.cycles},
    ])
    print(md_table(comp, ["choice", "tile", "L1D", "L2", "speedup"], FMT))
    return hw_only, sw_only, joint


def chain(df, n, picks):
    """Statistics along the causal chain for selected configurations."""
    rows = []
    for tile, l1, l2 in picks:
        s = df[(df.N == n) & (df.variant == tile) & (df.l1d_size == l1) & (df.l2_size == l2)]
        if len(s):
            rows.append(s.iloc[0])
    import pandas as pd
    t = pd.DataFrame(rows)
    print(f"\n### N = {n}: causal-chain statistics\n")
    print(md_table(t, ["variant", "l1d_size", "l2_size", "insts_per_mac", "l1d_line_per_mac",
                       "l2_miss_per_mac", "dram_b_per_mac", "l2_mlp", "ipc", "cycles"], FMT))


def main():
    df = prep()
    for n in sorted(df.N.unique()):
        print(heatmaps(df, n))
        hw, sw, joint = summary(df, n)
        picks = [("untiled", "32KiB", "1MiB"), ("untiled", hw.l1d_size, hw.l2_size),
                 (sw.variant, "32KiB", "1MiB"), (joint.variant, joint.l1d_size, joint.l2_size)]
        for t in TILES[1:]:
            picks.append((t, "32KiB", "1MiB"))
        seen, uniq = set(), []
        for p in picks:
            if p not in seen:
                seen.add(p)
                uniq.append(p)
        chain(df, n, uniq)


if __name__ == "__main__":
    main()
