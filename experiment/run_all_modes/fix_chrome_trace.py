#!/usr/bin/env python3
"""
Fix Chrome trace JSON for chrome://tracing:
  1. Convert ts/dur from milliseconds to microseconds (if needed)
  2. Output minimal format: {"traceEvents": [...]} only

Usage: python3 fix_chrome_trace.py <input.json> <output.json>
"""
import json
import sys


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: fix_chrome_trace.py <input.json> <output.json>", file=sys.stderr)
        return 1
    with open(sys.argv[1]) as f:
        data = json.load(f)
    events = data.get("traceEvents", data)
    if not isinstance(events, list):
        events = [data]
    # Chrome tracing expects ts/dur in microseconds; chakra outputs milliseconds
    for e in events:
        if "ts" in e:
            e["ts"] = float(e["ts"]) * 1_000
        if "dur" in e:
            e["dur"] = float(e["dur"]) * 1_000
    with open(sys.argv[2], "w") as f:
        json.dump({"traceEvents": events}, f)
    print(f"Fixed -> {sys.argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
