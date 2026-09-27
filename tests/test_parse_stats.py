"""Unit tests for scripts/parse_stats.py against a saved gem5 v25.1 run.

Fixture tests/data/s2_conflict/: stats.txt, config.ini, af_meta.json, and
af_options.json from the Stage 2 pilot run of `conflict 24 65536 43690` on
the baseline O3 system. Expected values were read from that stats.txt.
Run with: python -m pytest tests
"""
import copy
import os
import shutil
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import parse_stats as ps  # noqa: E402

RUN = os.path.join(HERE, "data", "s2_conflict")


def test_two_dumps_roi_first():
    dumps = ps.load_dumps(os.path.join(RUN, "stats.txt"))
    assert len(dumps) == 2
    # The ROI dump is much shorter than the whole program.
    assert int(dumps[0]["simInsts"]) < int(dumps[1]["simInsts"]) + int(dumps[0]["simInsts"])
    assert dumps[0]["simInsts"] == "5592331"


def test_extract_values():
    dumps = ps.load_dumps(os.path.join(RUN, "stats.txt"))
    cp = ps.load_config(os.path.join(RUN, "config.ini"))
    row = ps.extract(dumps[0], cp, "o3")
    assert row["sim_insts"] == 5592331
    assert row["cycles"] == 3577170
    assert row["ipc"] == pytest.approx(1.563339)
    assert row["l1d_demand_accesses"] == 1048562
    assert row["l1d_demand_misses"] == 839914
    assert row["l2_demand_misses"] == 322011
    assert row["dram_read_reqs"] == 322011
    assert row["dram_bytes_read"] == 20608640
    assert row["cpi"] == pytest.approx(3577170 / 5592331)
    assert row["l1d_miss_rate"] == pytest.approx(839914 / 1048562)
    assert row["mem_read_bytes"] == 20608640


def test_absent_stat_zero_vs_none():
    dumps = ps.load_dumps(os.path.join(RUN, "stats.txt"))
    cp = ps.load_config(os.path.join(RUN, "config.ini"))
    row = ps.extract(dumps[0], cp, "o3")
    # O3 core exists, LQ-full events never happened: gem5 omits the zero.
    assert "board.processor.cores.core.rename.LQFullEvents" not in dumps[0]
    assert row["o3_lq_full_events"] == 0
    # No prefetcher and no SimpleMemory in this configuration.
    assert row["pf_l1d_issued"] is None
    assert row["smem_reads"] is None
    # O3-only statistics are None when the run is declared as another CPU.
    assert ps.extract(dumps[0], cp, "timing")["o3_lq_full_events"] is None


def test_validate_config_accepts_run():
    row, probs, meta, opt = ps.parse_run(RUN)
    assert probs == []
    assert opt["cpu"] == "o3"


@pytest.mark.parametrize("key,val", [
    ("cpu", "minor"), ("l1d_size", "64KiB"), ("l2_assoc", 8), ("line_size", 128),
    ("clock", "2GHz"), ("prefetcher", "stride"), ("mem_type", "SimpleMemory"),
    ("rob", 64),
])
def test_validate_config_detects_mismatch(key, val):
    cp = ps.load_config(os.path.join(RUN, "config.ini"))
    opt = ps.json.load(open(os.path.join(RUN, "af_options.json")))
    bad = copy.deepcopy(opt)
    bad[key] = val
    assert ps.validate_config(cp, bad), f"{key}={val} not detected"


def test_parse_run_flags_fail(tmp_path):
    d = tmp_path / "run"
    shutil.copytree(RUN, d)
    meta = ps.json.load(open(d / "af_meta.json"))
    meta["workload_status"] = "FAIL"
    ps.json.dump(meta, open(d / "af_meta.json", "w"))
    _, probs, _, _ = ps.parse_run(str(d))
    assert "workload did not print PASS" in probs
