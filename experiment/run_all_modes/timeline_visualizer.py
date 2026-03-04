#!/usr/bin/env python3
"""
Chakra timeline visualizer - produces Chrome tracing JSON from issue/callback CSV.
Bundled for self-contained workflow; original from mlcommons/chakra.
Expects CSV format: issue/callback,npu_id=X,curr_cycle=Y,node_id=Z,node_name=...
"""
import argparse
import json
import sys
from enum import IntEnum
from typing import Any, Dict, List, Tuple


class TID(IntEnum):
    LOCAL_MEMORY = 1
    REMOTE_MEMORY = 2
    COMP = 3
    COMM = 4


def is_local_mem_node(node_name: str) -> bool:
    return (
        (("MEM_LOAD_NODE" in node_name) and ("LOCAL_MEMORY" in node_name))
        or (("MEM_STORE_NODE" in node_name) and ("LOCAL_MEMORY" in node_name))
    )


def is_remote_mem_node(node_name: str) -> bool:
    return (
        (("MEM_LOAD_NODE" in node_name) and ("REMOTE_MEMORY" in node_name))
        or (("MEM_STORE_NODE" in node_name) and ("REMOTE_MEMORY" in node_name))
    )


def is_comp_node(node_name: str) -> bool:
    return "COMP_NODE" in node_name


def is_comm_node(node_name: str) -> bool:
    return ("COMM_SEND_NODE" in node_name) or ("COMM_RECV_NODE" in node_name) or ("COMM_COLL_NODE" in node_name)


def get_tid(node_name: str) -> TID:
    if is_local_mem_node(node_name):
        return TID.LOCAL_MEMORY
    elif is_remote_mem_node(node_name):
        return TID.REMOTE_MEMORY
    elif is_comp_node(node_name):
        return TID.COMP
    elif is_comm_node(node_name):
        return TID.COMM
    else:
        raise ValueError(f"Node type cannot be identified from {node_name}")


def parse_event(line: str) -> Tuple[str, int, int, int, str]:
    try:
        cols = line.strip().split(",")
        trace_type = cols[0]
        npu_id = int(cols[1].split("=")[1])
        curr_cycle = int(cols[2].split("=")[1])
        node_id = int(cols[3].split("=")[1])
        node_name = cols[4].split("=", 1)[1]
        return (trace_type, npu_id, curr_cycle, node_id, node_name)
    except Exception as e:
        raise ValueError(f'Cannot parse event: "{line}": {e}') from e


def get_trace_events(input_filename: str, num_npus: int, npu_frequency: int) -> List[Dict[str, Any]]:
    trace_dict: Dict[int, Dict[int, List]] = {i: {} for i in range(num_npus)}
    trace_events: List[Dict[str, Any]] = []

    with open(input_filename, "r") as f:
        for line in f:
            if ("issue" not in line) and ("callback" not in line):
                continue
            trace_type, npu_id, curr_cycle, node_id, node_name = parse_event(line)

            if trace_type == "issue":
                trace_dict[npu_id][node_id] = [node_name, curr_cycle]
            elif trace_type == "callback":
                if node_id not in trace_dict[npu_id]:
                    continue
                node_name = trace_dict[npu_id][node_id][0]
                issued_cycle = trace_dict[npu_id][node_id][1]
                try:
                    tid = get_tid(node_name)
                except ValueError:
                    continue
                issued_ms = (issued_cycle / npu_frequency) / 1_000
                duration_in_cycles = curr_cycle - issued_cycle
                duration_in_ms = duration_in_cycles / (npu_frequency * 1_000)
                # Chrome Tracing expects ts/dur in microseconds
                ts_us = issued_ms * 1_000
                dur_us = duration_in_ms * 1_000

                trace_events.append({
                    "pid": npu_id,
                    "tid": int(tid),
                    "ts": ts_us,
                    "dur": dur_us,
                    "ph": "X",
                    "name": node_name,
                    "args": {"ms": round(duration_in_ms, 3)},
                })
                del trace_dict[npu_id][node_id]

    return trace_events


def main() -> int:
    parser = argparse.ArgumentParser(description="Chakra Timeline Visualizer")
    parser.add_argument("-i", "--input_filename", required=True, help="Input CSV (issue/callback format)")
    parser.add_argument("-o", "--output_filename", required=True, help="Output JSON (Chrome tracing)")
    parser.add_argument("-n", "--num_npus", type=int, required=True, help="Number of NPUs")
    parser.add_argument("-f", "--npu_frequency", type=int, required=True, help="NPU frequency in MHz (e.g. 1500 for 1.5GHz)")
    args = parser.parse_args()

    try:
        trace_events = get_trace_events(args.input_filename, args.num_npus, args.npu_frequency)
        output = {"meta_user": "chakra", "traceEvents": trace_events, "meta_cpu_count": args.num_npus}
        with open(args.output_filename, "w") as f:
            json.dump(output, f)
        print(f"Wrote {len(trace_events)} events -> {args.output_filename}")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
