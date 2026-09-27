"""Shared helpers for ArchForge analysis scripts.

Every script reads results/<study>.csv, keeps only rows with
validation == ok, and writes markdown tables to stdout and figures to
docs/figures/. Numbers in docs come from these scripts, never by hand.
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIG = os.path.join(ROOT, "docs", "figures")

# Categorical slots in fixed order (validated reference palette, light mode).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300",
          "#4a3aa7", "#e34948"]
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def load(study):
    df = pd.read_csv(os.path.join(ROOT, "results", f"{study}.csv"))
    bad = df[df["validation"] != "ok"]
    if len(bad):
        print(f"<!-- {study}: dropping {len(bad)} rows that failed validation -->")
    return df[df["validation"] == "ok"].copy()


def style(ax, title, xlabel, ylabel):
    ax.set_title(title, loc="left", fontsize=11, color=INK)
    ax.set_xlabel(xlabel, color=INK2)
    ax.set_ylabel(ylabel, color=INK2)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2)


def line(ax, x, y, i, label):
    ax.plot(x, y, color=SERIES[i], linewidth=2, marker="o", markersize=6,
            markeredgecolor="white", markeredgewidth=1.5, label=label)


def save(fig, name):
    os.makedirs(FIG, exist_ok=True)
    path = os.path.join(FIG, name)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor="white")
    plt.close(fig)
    return os.path.relpath(path, ROOT)


def md_table(df, cols, fmt=None):
    fmt = fmt or {}
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            cells.append(fmt[c].format(v) if c in fmt and pd.notna(v) else str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)
