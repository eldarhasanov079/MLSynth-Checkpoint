#!/usr/bin/env python3
"""
Re-run AstraSim Analytical Congestion-Aware on existing checkpoint_sweep traces.

Assumes traces already exist under experiment/checkpoint_sweep/traces:
- sweep_base/et/                         (BASE, no checkpoint)
- sweep_sm{10,100,1000,10000}_sync/et/  (REMOTE_SYNC)
- sweep_sm{10,100,1000,10000}_async/et/ (REMOTE_ASYNC)

Uses the same docker invocation as run_sweep.py, but does NOT resynthesize
workloads (no Chakra dependency). Writes results to:
- experiment/checkpoint_sweep/results/checkpoint_sweep_rerun.json
"""
import json
import re
from pathlib import Path
import subprocess
import sys

import run_sweep as rs


def run_astrasim(trace_dir: Path, network_yml: Path) -> tuple[str, int]:
    """Run AstraSim in Docker. Return (stdout+stderr, returncode)."""
    workload = f"/workspace/{trace_dir.relative_to(rs.ROOT)}/et/{rs.OUTPUT_NAME}"
    system = "/workspace/experiment/checkpoint_sweep/config/Switch.json"
    network = f"/workspace/{network_yml.relative_to(rs.ROOT)}"
    remote_mem = "/workspace/astra-sim/examples/remote_memory/analytical/no_memory_expansion.json"
    comm = f"/workspace/{trace_dir.relative_to(rs.ROOT)}/comm_groups.json"
    binary = "/workspace/astra-sim/build/astra_analytical/build/bin/AstraSim_Analytical_Congestion_Aware"

    cmd = [
        "docker", "run", "--rm", "--shm-size=8g",
        "-v", f"{rs.ROOT}:/workspace", "-w", "/workspace",
        "astra-sim:latest", binary,
        f"--workload-configuration={workload}",
        f"--system-configuration={system}",
        f"--network-configuration={network}",
        f"--remote-memory-configuration={remote_mem}",
        f"--comm-group-configuration={comm}",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return (r.stdout + r.stderr), r.returncode


def parse_astrasim_output(out: str) -> dict:
    """Extract wall_time, gpu_time, comm_time, overlap from AstraSim log."""
    wall = re.search(r"sys\[0\][^\n]*Wall time: (\d+)", out)
    gpu = re.search(r"sys\[0\][^\n]*GPU time: (\d+)", out)
    comm = re.search(r"sys\[0\][^\n]*Comm time: (\d+)", out)
    overlap = re.search(r"sys\[0\][^\n]*Total compute-communication overlap: (\d+)", out)
    return {
        "wall_time_cycles": int(wall.group(1)) if wall else None,
        "gpu_time_cycles": int(gpu.group(1)) if gpu else None,
        "comm_time_cycles": int(comm.group(1)) if comm else None,
        "overlap_cycles": int(overlap.group(1)) if overlap else 0,
    }


def main() -> int:
    results = []
    dumped_failure = False

    # Ensure network configs exist
    for bw in rs.BANDWIDTHS_GB_S:
        rs.ensure_network_config(bw)

    # Helper to run one (label, trace_dir, mode, state_mult or None)
    def run_one(label: str, trace_dir: Path, mode: str, state_mult):
        nonlocal dumped_failure, results
        if not trace_dir.exists():
            print(f"Skip {label}: trace dir {trace_dir} not found", file=sys.stderr)
            return
        for bw in rs.BANDWIDTHS_GB_S:
            network_yml = rs.CONFIG / f"network_8_remote_bw{int(bw)}.yml"
            print(f"Running AstraSim: {label}, bandwidth={bw} GB/s...")
            out, returncode = run_astrasim(trace_dir, network_yml)
            parsed = parse_astrasim_output(out)
            context = f"{label} bw={bw}"
            if parsed.get("wall_time_cycles") is None and not dumped_failure:
                # Print tail of output once to help debug
                tail = out.strip()[-2000:] if len(out) > 2000 else out.strip()
                print(f"  [WARN] No stats parsed (returncode={returncode}) for {context}", file=sys.stderr)
                print("  Last 2000 chars of AstraSim output:", file=sys.stderr)
                print("-" * 40, file=sys.stderr)
                print(tail, file=sys.stderr)
                print("-" * 40, file=sys.stderr)
                dumped_failure = True
            row = {
                "state_multiplier": state_mult,
                "bandwidth_gb_s": bw,
                "mode": mode,
                **parsed,
            }
            results.append(row)
            print(f"  -> Wall: {row['wall_time_cycles']}, GPU: {row['gpu_time_cycles']}, "
                  f"Comm: {row['comm_time_cycles']}, Overlap: {row['overlap_cycles']}")

    # BASE
    base_dir = rs.TR / "sweep_base"
    run_one("BASE", base_dir, "BASE", None)

    # REMOTE_SYNC / REMOTE_ASYNC
    for sm in rs.STATE_MULTIPLIERS:
        for mode in ("sync", "async"):
            label = f"REMOTE_{mode.upper()}_sm{sm}"
            trace_dir = rs.TR / f"sweep_sm{sm}_{mode}"
            mode_name = f"REMOTE_{mode.upper()}"
            run_one(label, trace_dir, mode_name, sm)

    out_dir = rs.SWEEP_DIR / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / "checkpoint_sweep_rerun.json"
    with out_json.open("w") as f:
        json.dump(results, f, indent=2)

    print(f"\nRerun results written to {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

