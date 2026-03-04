#!/usr/bin/env python3
"""
Simulate Chakra ET traces and output issue/callback CSV for timeline visualization.
Uses only trace files in /traces — no ASTRA-sim required.

Reads ET files, does topological execution with simplified timing model:
- COMP: duration from num_ops / (peak_perf_TFLOPS * 1e12 / freq_GHz / 1e9)
- COMM: duration from comm_size / bandwidth + latency
"""
import argparse
import sys
from pathlib import Path
from collections import defaultdict

try:
    from chakra.schema.protobuf.et_def_pb2 import Node as ChakraNode, GlobalMetadata
    from chakra.src.third_party.utils.protolib import decodeMessage as decode_message, openFileRd
except ImportError as e:
    print(f"Error: Chakra not installed. pip install chakra. {e}", file=sys.stderr)
    sys.exit(1)

# From Switch.json
PEAK_PERF_TFLOPS = 3
FREQ_GHZ = 1.5
BW_GB_S = 100
LATENCY_NS = 500


def get_attr(node, name, default=None):
    for a in node.attr:
        if a.name == name:
            if a.HasField("int64_val"):
                return a.int64_val
            if a.HasField("uint64_val"):
                return a.uint64_val
            if a.HasField("int32_val"):
                return a.int32_val
    return default


def duration_cycles(node) -> int:
    """Compute execution duration in cycles. COMP_NODE=4, COMM_SEND=5, COMM_RECV=6, COMM_COLL=7."""
    if node.type == 4:  # COMP_NODE
        if node.duration_micros and node.duration_micros > 0:
            return int(node.duration_micros * FREQ_GHZ * 1000)
        num_ops = get_attr(node, "num_ops", 0) or 0
        if num_ops <= 0:
            return 1
        return max(1, int(num_ops / (PEAK_PERF_TFLOPS * 1e12 / (FREQ_GHZ * 1e9))))
    if node.type in (5, 6):  # COMM_SEND, COMM_RECV
        size = get_attr(node, "comm_size", 0) or 0
        time_ns = (size / (BW_GB_S * 1e9)) * 1e9 + LATENCY_NS
        return max(1, int(time_ns * FREQ_GHZ / 1000))
    if node.type == 7:  # COMM_COLL
        size = get_attr(node, "comm_size", 0) or 0
        time_ns = (size / (BW_GB_S * 1e9)) * 1e9 + LATENCY_NS
        return max(1, int(time_ns * FREQ_GHZ / 1000))
    return 1


def load_et_trace(workload_base: str, num_npus: int) -> dict:
    """Load all nodes from workload. Returns {node_id: (node, npu_id)}."""
    base = Path(workload_base)
    nodes = {}
    for npu in range(num_npus):
        et_path = Path(str(base) + f".{npu}.et")
        if not et_path.exists():
            et_path = base.parent / f"{base.name}.{npu}.et"
        if not et_path.exists():
            continue
        try:
            f = openFileRd(str(et_path))
            meta = GlobalMetadata()
            decode_message(f, meta)
            node = ChakraNode()
            while decode_message(f, node):
                n = ChakraNode()
                n.CopyFrom(node)
                nodes[n.id] = (n, npu)
            f.close()
        except Exception as e:
            print(f"Warning: {et_path}: {e}", file=sys.stderr)
    return nodes


def simulate(nodes: dict) -> list:
    """Topological execution. Returns list of (event, npu_id, cycle, node_id, node_name)."""
    callback_cycle = {}
    events = []

    def ready(node_id):
        node, _ = nodes[node_id]
        for dep in node.data_deps:
            if dep not in callback_cycle:
                return False
        return True

    remaining = set(nodes.keys())
    cycle = 0
    max_iter = len(nodes) * 10
    iter_count = 0
    while remaining and iter_count < max_iter:
        iter_count += 1
        scheduled = []
        for nid in list(remaining):
            if not ready(nid):
                continue
            node, npu_id = nodes[nid]
            issue_c = max((callback_cycle.get(d, 0) for d in node.data_deps), default=0)
            dur = duration_cycles(node)
            callback_c = issue_c + dur
            events.append(("issue", npu_id, issue_c, node.id, node.name))
            events.append(("callback", npu_id, callback_c, node.id, node.name))
            callback_cycle[nid] = callback_c
            scheduled.append(nid)
        for nid in scheduled:
            remaining.discard(nid)
        if not scheduled:
            break

    events.sort(key=lambda x: (x[2], 0 if x[0] == "issue" else 1))
    return events


def main() -> int:
    ap = argparse.ArgumentParser(description="Simulate ET traces -> issue/callback CSV")
    ap.add_argument("--workload", "-w", required=True, help="Workload base path (e.g. traces/base/et/transformer_...)")
    ap.add_argument("--output", "-o", required=True, help="Output CSV path")
    ap.add_argument("--num_npus", "-n", type=int, default=4)
    args = ap.parse_args()

    nodes = load_et_trace(args.workload, args.num_npus)
    if not nodes:
        print("Error: No nodes loaded. Check workload path.", file=sys.stderr)
        return 1

    events = simulate(nodes)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        for ev, npu, cyc, nid, name in events:
            f.write(f"{ev},npu_id={npu},curr_cycle={cyc},node_id={nid},node_name={name}\n")

    print(f"Simulated {len(events)//2} nodes -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
