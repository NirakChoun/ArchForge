#!/usr/bin/env python3
"""Parse gem5 stats.txt and config.ini into ArchForge result rows.

  parse_stats.py <outdir>            print the parsed row for one run as JSON

Library use (collect.py): load_dumps, load_config, extract, validate_config,
parse_run.

Statistic names are the ones gem5 v25.1 emits for configs/archforge_se.py
with a single core; docs/stats.md lists each one with its meaning. Only the
first dump is used: the workload calls m5_reset_stats before its region of
interest and m5_dump_stats after it, so dump 0 is exactly the ROI and the
second dump (written at exit) covers the checksum and teardown.

gem5 omits statistics whose value is zero from stats.txt. A statistic that
is absent is therefore recorded as 0 when the SimObject that owns it exists
in config.ini, and left empty (None) when it does not (for example O3-only
statistics on a TimingSimpleCPU run, or prefetcher statistics without a
prefetcher).
"""
import configparser
import json
import os
import re
import sys

CORE = "board.processor.cores.core"
L1I = "board.cache_hierarchy.l1icaches"
L1D = "board.cache_hierarchy.l1dcaches"
L2 = "board.cache_hierarchy.l2caches"
MEM = "board.memory.mem_ctrl"
SMEM = "board.memory.module"

# column -> (gem5 statistic, owning SimObject section in config.ini,
#            required CPU type or None)
STATS = {
    "sim_ticks": ("simTicks", "root", None),
    "sim_insts": ("simInsts", "root", None),
    "sim_ops": ("simOps", "root", None),
    "cycles": (f"{CORE}.numCycles", CORE, None),
    "ipc": (f"{CORE}.ipc", CORE, None),
    "l1i_demand_accesses": (f"{L1I}.demandAccesses::total", L1I, None),
    "l1i_demand_misses": (f"{L1I}.demandMisses::total", L1I, None),
    "l1d_demand_accesses": (f"{L1D}.demandAccesses::total", L1D, None),
    "l1d_demand_misses": (f"{L1D}.demandMisses::total", L1D, None),
    "l1d_demand_mshr_misses": (f"{L1D}.demandMshrMisses::total", L1D, None),
    "l1d_writebacks": (f"{L1D}.writebacks::total", L1D, None),
    "l1d_demand_miss_latency": (f"{L1D}.demandMissLatency::total", L1D, None),
    "l2_demand_accesses": (f"{L2}.demandAccesses::total", L2, None),
    "l2_demand_misses": (f"{L2}.demandMisses::total", L2, None),
    "l2_overall_misses": (f"{L2}.overallMisses::total", L2, None),
    "l2_writebacks": (f"{L2}.writebacks::total", L2, None),
    "l2_demand_miss_latency": (f"{L2}.demandMissLatency::total", L2, None),
    "dram_read_reqs": (f"{MEM}.readReqs", MEM, None),
    "dram_write_reqs": (f"{MEM}.writeReqs", MEM, None),
    "dram_bytes_read": (f"{MEM}.dram.bytesRead::total", f"{MEM}.dram", None),
    "dram_bytes_written": (f"{MEM}.dram.bytesWritten::total", f"{MEM}.dram", None),
    "dram_avg_mem_acc_lat_ticks": (f"{MEM}.dram.avgMemAccLat", f"{MEM}.dram", None),
    "smem_reads": (f"{SMEM}.numReads::total", SMEM, None),
    "smem_bytes_read": (f"{SMEM}.bytesRead::total", SMEM, None),
    "br_cond_predicted": (f"{CORE}.branchPred.condPredicted", f"{CORE}.branchPred", None),
    "br_cond_incorrect": (f"{CORE}.branchPred.condIncorrect", f"{CORE}.branchPred", None),
    # O3 structure-pressure statistics (MLP and CPU-model studies).
    "o3_rob_full_events": (f"{CORE}.rename.ROBFullEvents", CORE, "o3"),
    "o3_iq_full_events": (f"{CORE}.rename.IQFullEvents", CORE, "o3"),
    "o3_lq_full_events": (f"{CORE}.rename.LQFullEvents", CORE, "o3"),
    "o3_sq_full_events": (f"{CORE}.rename.SQFullEvents", CORE, "o3"),
    "o3_lsq_full_events": (f"{CORE}.iew.lsqFullEvents", CORE, "o3"),
    "o3_lq_avg_occupancy": (f"{CORE}.lsq0.lqAvgOccupancy", CORE, "o3"),
    "o3_iew_branch_mispredicts": (f"{CORE}.iew.branchMispredicts", CORE, "o3"),
    "o3_commit_squashed_insts": (f"{CORE}.commit.commitSquashedInsts", CORE, "o3"),
    # Prefetcher accounting (only when a prefetcher is attached).
    "pf_l1d_issued": (f"{L1D}.prefetcher.pfIssued", f"{L1D}.prefetcher", None),
    "pf_l1d_useful": (f"{L1D}.prefetcher.pfUseful", f"{L1D}.prefetcher", None),
    "pf_l1d_unused": (f"{L1D}.prefetcher.pfUnused", f"{L1D}.prefetcher", None),
    "pf_l1d_accuracy": (f"{L1D}.prefetcher.accuracy", f"{L1D}.prefetcher", None),
    "pf_l1d_coverage": (f"{L1D}.prefetcher.coverage", f"{L1D}.prefetcher", None),
    "pf_l2_issued": (f"{L2}.prefetcher.pfIssued", f"{L2}.prefetcher", None),
    "pf_l2_useful": (f"{L2}.prefetcher.pfUseful", f"{L2}.prefetcher", None),
    "pf_l2_accuracy": (f"{L2}.prefetcher.accuracy", f"{L2}.prefetcher", None),
    "pf_l2_coverage": (f"{L2}.prefetcher.coverage", f"{L2}.prefetcher", None),
}
DERIVED = ["cpi", "l1d_miss_rate", "l2_miss_rate", "l1d_mpki", "l2_mpki",
           "br_mispredict_rate", "br_mpki", "mem_read_bytes", "l1d_mlp", "l2_mlp"]

# config.ini records the C++ base class as `type`; the ISA is checked
# separately through the core's `isa` child (X86ISA).
CPU_TYPES = {"timing": "BaseTimingSimpleCPU", "minor": "BaseMinorCPU",
             "o3": "BaseO3CPU"}


def _num(v):
    try:
        f = float(v)
    except ValueError:
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return int(f) if f.is_integer() and re.fullmatch(r"-?\d+", v) else f


def load_dumps(path):
    """stats.txt -> list of {stat: value-string}, one per dump."""
    dumps, cur = [], None
    with open(path) as fh:
        for line in fh:
            if line.startswith("---------- Begin Simulation Statistics"):
                cur = {}
            elif line.startswith("---------- End Simulation Statistics"):
                dumps.append(cur)
                cur = None
            elif cur is not None:
                body = line.split("#", 1)[0].split()
                if len(body) >= 2:
                    cur[body[0]] = body[1]
    return dumps


def load_config(path):
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    cp.read(path)
    return cp


def extract(dump, cp, cpu):
    """One dump -> {column: number or None}, plus derived ratios."""
    row = {}
    for col, (name, owner, need_cpu) in STATS.items():
        if name in dump:
            row[col] = _num(dump[name])
        elif cp.has_section(owner) and (need_cpu is None or need_cpu == cpu):
            row[col] = 0  # gem5 omits zero-valued statistics
        else:
            row[col] = None

    def ratio(a, b, scale=1.0):
        x, y = row.get(a), row.get(b)
        return scale * x / y if x is not None and y not in (None, 0) else None

    row["cpi"] = ratio("cycles", "sim_insts")
    row["l1d_miss_rate"] = ratio("l1d_demand_misses", "l1d_demand_accesses")
    row["l2_miss_rate"] = ratio("l2_demand_misses", "l2_demand_accesses")
    row["l1d_mpki"] = ratio("l1d_demand_misses", "sim_insts", 1000.0)
    row["l2_mpki"] = ratio("l2_demand_misses", "sim_insts", 1000.0)
    row["br_mispredict_rate"] = ratio("br_cond_incorrect", "br_cond_predicted")
    row["br_mpki"] = ratio("br_cond_incorrect", "sim_insts", 1000.0)
    # Average number of demand misses outstanding: total miss latency (ticks,
    # summed over misses) divided by elapsed ticks (Little's law).
    row["l1d_mlp"] = ratio("l1d_demand_miss_latency", "sim_ticks")
    row["l2_mlp"] = ratio("l2_demand_miss_latency", "sim_ticks")
    # Bytes read from main memory, whichever memory model was used.
    row["mem_read_bytes"] = (row["dram_bytes_read"] if row["dram_bytes_read"] is not None
                             else row["smem_bytes_read"])
    return row


def size_bytes(s):
    m = re.fullmatch(r"(\d+)\s*([KMG]i?B|B)?", str(s))
    if not m:
        raise ValueError(f"bad size {s}")
    mult = {None: 1, "B": 1, "KiB": 1 << 10, "MiB": 1 << 20, "GiB": 1 << 30,
            "KB": 1 << 10, "MB": 1 << 20, "GB": 1 << 30}[m.group(2)]
    return int(m.group(1)) * mult


def freq_hz(s):
    m = re.fullmatch(r"([\d.]+)\s*([KMG]?)Hz", str(s))
    return float(m.group(1)) * {"": 1, "K": 1e3, "M": 1e6, "G": 1e9}[m.group(2)]


def _latency_ticks(s):
    m = re.fullmatch(r"([\d.]+)\s*(ns|ps|us)", s)
    return round(float(m.group(1)) * {"ps": 1, "ns": 1e3, "us": 1e6}[m.group(2)])


def validate_config(cp, opt):
    """Check that config.ini contains what the run asked for.

    Returns a list of problems (empty when the configuration is as intended).
    Single-core runs only; multicore section names carry an index.
    """
    probs = []

    def get(sec, key):
        return cp.get(sec, key, fallback=None)

    def want(sec, key, val):
        got = get(sec, key)
        if got is None or str(got) != str(val):
            probs.append(f"{sec}.{key}={got} expected {val}")

    want(CORE, "type", CPU_TYPES[opt["cpu"]])
    want(f"{CORE}.isa", "type", "X86ISA")
    for sec, pre in ((L1I, "l1i"), (L1D, "l1d"), (L2, "l2")):
        want(sec, "size", size_bytes(opt[f"{pre}_size"]))
        want(sec, "assoc", opt[f"{pre}_assoc"])
    want("board", "cache_line_size", opt["line_size"])
    want("board.clk_domain", "clock", round(1e12 / freq_hz(opt["clock"])))
    for sec, lvl in ((L1D, "l1d"), (L2, "l2")):
        has_pf = cp.has_section(f"{sec}.prefetcher")
        want_pf = opt["prefetcher"] == "stride" and opt["prefetch_level"] == lvl
        if has_pf != want_pf:
            probs.append(f"{sec}.prefetcher present={has_pf} expected {want_pf}")
        if has_pf:
            want(f"{sec}.prefetcher", "type", "StridePrefetcher")
    if opt["mem_type"] == "DDR4_2400":
        # config.ini names the class DRAMInterface; tCK = 0.833 ns
        # identifies the DDR4-2400 timing set.
        want(f"{MEM}.dram", "type", "DRAMInterface")
        want(f"{MEM}.dram", "tCK", 833)
    else:
        want(SMEM, "type", "SimpleMemory")
        want(SMEM, "latency", _latency_ticks(opt.get("mem_latency") or "50ns"))
    if opt["cpu"] == "o3":
        for key, name in (("rob", "numROBEntries"), ("lq", "LQEntries"),
                          ("sq", "SQEntries")):
            if opt.get(key):
                want(CORE, name, opt[key])
    return probs


def parse_run(outdir):
    """One run directory -> (row, problems, meta, options)."""
    probs = []
    meta = json.load(open(os.path.join(outdir, "af_meta.json")))
    opt = meta.get("options")
    if opt is None:
        opt = json.load(open(os.path.join(outdir, "af_options.json")))
    if meta.get("exit_code") != 0:
        probs.append(f"gem5 exit code {meta.get('exit_code')}")
    if meta.get("workload_status") != "PASS":
        probs.append("workload did not print PASS")
    cp = load_config(os.path.join(outdir, "config.ini"))
    dumps = load_dumps(os.path.join(outdir, "stats.txt"))
    # Expect the ROI dump plus the automatic dump at exit.
    if len(dumps) != 2:
        probs.append(f"{len(dumps)} stats dumps, expected 2 (ROI + exit)")
    row = extract(dumps[0], cp, opt["cpu"]) if dumps else {}
    if dumps and not row.get("sim_insts"):
        probs.append("ROI dump has no committed instructions")
    if int(opt.get("num_cores", 1)) == 1:
        probs += validate_config(cp, opt)
    return row, probs, meta, opt


if __name__ == "__main__":
    row, probs, meta, opt = parse_run(sys.argv[1])
    print(json.dumps({"row": row, "problems": probs}, indent=1))
