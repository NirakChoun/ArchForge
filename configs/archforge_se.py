"""ArchForge single-core SE-mode system (gem5 standard library).

Usage:
  gem5.opt -d <outdir> configs/archforge_se.py --binary <path> [options]

Everything that Section 6 of the handoff asks to record is a command-line
option here. Defaults and their sources are listed in docs/architecture.md.
The cache hierarchy is ArchForge's own subclass because the stdlib
PrivateL1PrivateL2CacheHierarchy hard-codes associativity and silently
attaches a StridePrefetcher to every cache; studies need both controlled.
"""

import argparse
import json
import os
import sys

import m5
from m5.objects import (
    BadAddr,
    Cache,
    L2XBar,
    StridePrefetcher,
    SystemXBar,
)
from m5.params import NULL

from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.cachehierarchies.classic.abstract_classic_cache_hierarchy import (
    AbstractClassicCacheHierarchy,
)
from gem5.components.memory.simple import SingleChannelSimpleMemory
from gem5.components.memory.single_channel import SingleChannelDDR4_2400
from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.isas import ISA
from gem5.resources.resource import BinaryResource
from gem5.simulate.simulator import Simulator
from gem5.utils.requires import requires

CPU_CHOICES = {"timing": CPUTypes.TIMING, "minor": CPUTypes.MINOR, "o3": CPUTypes.O3}


def make_cache(size, assoc, tag, data, resp, mshrs, tgts, prefetch, **extra):
    c = Cache(
        size=size,
        assoc=assoc,
        tag_latency=tag,
        data_latency=data,
        response_latency=resp,
        mshrs=mshrs,
        tgts_per_mshr=tgts,
        writeback_clean=False,
        **extra,
    )
    # Explicit NULL: gem5's Cache has no prefetcher by default, but being
    # explicit keeps config.ini unambiguous for validation.
    c.prefetcher = StridePrefetcher() if prefetch else NULL
    return c


class ArchForgeHierarchy(AbstractClassicCacheHierarchy):
    """Private L1I/L1D and private L2 per core, classic coherent crossbar.

    Mirrors the port wiring of gem5's PrivateL1PrivateL2CacheHierarchy
    (v25.1) but takes every size, associativity, and prefetcher placement
    as a parameter. Latencies and MSHR counts are the stdlib L1DCache and
    L2Cache defaults.
    """

    def __init__(self, a):
        AbstractClassicCacheHierarchy.__init__(self=self)
        self._a = a
        self.membus = SystemXBar(width=64)
        self.membus.badaddr_responder = BadAddr()
        self.membus.default = self.membus.badaddr_responder.pio

    def get_mem_side_port(self):
        return self.membus.mem_side_ports

    def get_cpu_side_port(self):
        return self.membus.cpu_side_ports

    def incorporate_cache(self, board):
        a = self._a
        board.connect_system_port(self.membus.cpu_side_ports)
        for _, port in board.get_mem_ports():
            self.membus.mem_side_ports = port
        cores = board.get_processor().get_cores()
        self.l2buses = [L2XBar() for _ in cores]
        self.l1icaches = [
            make_cache(a.l1i_size, a.l1i_assoc, 1, 1, 1, 16, 20, False)
            for _ in cores
        ]
        self.l1dcaches = [
            make_cache(a.l1d_size, a.l1d_assoc, 1, 1, 1, 16, 20,
                       a.prefetcher == "stride" and a.prefetch_level == "l1d")
            for _ in cores
        ]
        self.l2caches = [
            make_cache(a.l2_size, a.l2_assoc, 10, 10, 1, 20, 12,
                       a.prefetcher == "stride" and a.prefetch_level == "l2",
                       clusivity="mostly_incl")
            for _ in cores
        ]
        for i, cpu in enumerate(cores):
            self.l2buses[i].mem_side_ports = self.l2caches[i].cpu_side
            self.membus.cpu_side_ports = self.l2caches[i].mem_side
            self.l1icaches[i].mem_side = self.l2buses[i].cpu_side_ports
            self.l1dcaches[i].mem_side = self.l2buses[i].cpu_side_ports
            cpu.connect_icache(self.l1icaches[i].cpu_side)
            cpu.connect_dcache(self.l1dcaches[i].cpu_side)
            cpu.connect_walker_ports(
                self.l2buses[i].cpu_side_ports, self.l2buses[i].cpu_side_ports
            )
            cpu.connect_interrupt(
                self.membus.mem_side_ports, self.membus.cpu_side_ports
            )


def parse_args(argv):
    p = argparse.ArgumentParser(description="ArchForge SE-mode system")
    p.add_argument("--binary", required=True, help="static x86-64 workload")
    p.add_argument("--args", default="", help="workload arguments, one string")
    p.add_argument("--cpu", choices=sorted(CPU_CHOICES), default="o3")
    p.add_argument("--num-cores", type=int, default=1)
    p.add_argument("--clock", default="3GHz")
    p.add_argument("--l1i-size", default="32KiB")
    p.add_argument("--l1i-assoc", type=int, default=8)
    p.add_argument("--l1d-size", default="32KiB")
    p.add_argument("--l1d-assoc", type=int, default=8)
    p.add_argument("--l2-size", default="1MiB")
    p.add_argument("--l2-assoc", type=int, default=16)
    p.add_argument("--line-size", type=int, default=64)
    p.add_argument("--prefetcher", choices=["none", "stride"], default="none")
    p.add_argument("--prefetch-level", choices=["l1d", "l2"], default="l1d")
    p.add_argument("--mem-type", choices=["DDR4_2400", "SimpleMemory"],
                   default="DDR4_2400")
    p.add_argument("--mem-latency", default="",
                   help="fixed latency override; only with --mem-type SimpleMemory")
    p.add_argument("--mem-size", default="2GiB")
    # O3-only structure sizes; empty means gem5's BaseO3CPU default.
    p.add_argument("--rob", type=int, default=0)
    p.add_argument("--lq", type=int, default=0)
    p.add_argument("--sq", type=int, default=0)
    a = p.parse_args(argv)
    if a.mem_latency and a.mem_type != "SimpleMemory":
        p.error("--mem-latency requires --mem-type SimpleMemory")
    if (a.rob or a.lq or a.sq) and a.cpu != "o3":
        p.error("--rob/--lq/--sq apply only to --cpu o3")
    return a


def build_memory(a):
    if a.mem_type == "DDR4_2400":
        return SingleChannelDDR4_2400(size=a.mem_size)
    # Bandwidth set to DDR4-2400 single-channel peak (19.2 GB/s) so that a
    # latency sweep changes latency, not bandwidth.
    return SingleChannelSimpleMemory(
        latency=a.mem_latency or "50ns", latency_var="0ns",
        bandwidth="19.2GiB/s", size=a.mem_size,
    )


def main():
    a = parse_args(sys.argv[1:])
    requires(isa_required=ISA.X86)
    processor = SimpleProcessor(
        cpu_type=CPU_CHOICES[a.cpu], num_cores=a.num_cores, isa=ISA.X86
    )
    if a.cpu == "o3":
        for core in processor.get_cores():
            obj = core.get_simobject()
            if a.rob:
                obj.numROBEntries = a.rob
            if a.lq:
                obj.LQEntries = a.lq
            if a.sq:
                obj.SQEntries = a.sq
    board = SimpleBoard(
        clk_freq=a.clock,
        processor=processor,
        memory=build_memory(a),
        cache_hierarchy=ArchForgeHierarchy(a),
    )
    board.cache_line_size = a.line_size
    board.set_se_binary_workload(
        binary=BinaryResource(local_path=os.path.abspath(a.binary)),
        arguments=a.args.split() if a.args else [],
    )
    # The resolved options go next to stats.txt so every run is self-describing.
    with open(os.path.join(m5.options.outdir, "af_options.json"), "w") as f:
        json.dump(vars(a), f, indent=1, sort_keys=True)
    sim = Simulator(board=board)
    sim.run()
    print(f"af: exit tick={sim.get_current_tick()} "
          f"cause={sim.get_last_exit_event_cause()}")


if __name__ == "__m5_main__":
    main()
