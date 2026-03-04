#!/usr/bin/env python3
"""
Extract issue/callback trace lines from ASTRA-sim log output into CSV format
expected by Chakra's timeline_visualizer (issue/callback,npu_id=...,curr_cycle=...,node_id=...,node_name=...).

Only outputs complete (issue, callback) pairs. Partial logs (e.g. mid-simulation capture)
may have callbacks without matching issues; those are skipped so the visualizer won't error.
"""
import re
import sys
from pathlib import Path
from typing import Optional


def extract_trace_lines(log_path: Path, out_path: Path) -> int:
    """
    Extract issue/callback lines from ASTRA-sim log.
    Input:  [timestamp] [workload] [debug] issue,sys->id=0, tick=123, node->id=1, node->name=FOO, node->type=4
    Output: issue,npu_id=0,curr_cycle=123,node_id=1,node_name=FOO (only complete pairs)
    """
    pattern = re.compile(
        r"\[.*?\]\s+\[.*?\]\s+\[.*?\]\s+"
        r"(issue|callback)\s*,\s*"
        r"sys->id=(\d+)\s*,\s*"
        r"tick=(\d+)\s*,\s*"
        r"node->id=(\d+)\s*,\s*"
        r"node->name=([^,]+?)(?:\s*,\s*node->type=\d+)?\s*$",
        re.IGNORECASE,
    )

    # Collect events: key = (npu_id, node_id) -> {issue: line, callback: line}
    pairs: dict[tuple[int, int], dict[str, tuple[str, int]]] = {}

    with open(log_path, "r", errors="replace") as fin:
        for line in fin:
            line = line.rstrip("\n")
            m = pattern.match(line.strip())
            if not m:
                continue
            event, npu_id, tick, node_id, node_name = m.groups()
            npu_id = int(npu_id)
            node_id = int(node_id)
            tick = int(tick)
            out_line = f"{event},npu_id={npu_id},curr_cycle={tick},node_id={node_id},node_name={node_name.strip()}\n"
            key = (npu_id, node_id)
            if key not in pairs:
                pairs[key] = {}
            pairs[key][event] = (out_line, tick)

    # Output only complete pairs, sorted by issue cycle then callback cycle
    events_out: list[tuple[int, str]] = []
    for (npu_id, node_id), evts in pairs.items():
        if "issue" in evts and "callback" in evts:
            issue_line, issue_tick = evts["issue"]
            callback_line, callback_tick = evts["callback"]
            events_out.append((issue_tick, issue_line))
            events_out.append((callback_tick, callback_line))

    events_out.sort(key=lambda x: (x[0], 0 if "issue" in x[1] else 1))

    with open(out_path, "w") as fout:
        for _, line in events_out:
            fout.write(line)

    return len(events_out)


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: extract_trace_csv.py <input.log> <output.csv>", file=sys.stderr)
        return 1
    log_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    if not log_path.exists():
        print(f"Error: log file not found: {log_path}", file=sys.stderr)
        return 1
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = extract_trace_lines(log_path, out_path)
    print(f"Extracted {n} trace events -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
