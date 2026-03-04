#!/usr/bin/env python3
"""
Checkpoint sweep: BASE + state_multiplier × bandwidth × mode.

- BASE: no checkpoint (same model/parallelism/iters); baseline for NIC/compute.
- Sweep state_multiplier (10, 100, 1000, 10000) and bandwidth (100, 50, 10, 1 GB/s).
- Modes: BASE, REMOTE_SYNC, REMOTE_ASYNC.

Compare async vs sync vs no-checkpoint to see if async helps and whether it
causes NIC contention. Traces live under traces/ for Chakra visualizer.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

SWEEP_DIR = Path(__file__).resolve().parent
ROOT = SWEEP_DIR.parent.parent
ML = ROOT / "MLSynth"
TR = SWEEP_DIR / "traces"
CONFIG = SWEEP_DIR / "config"
OUTPUT_NAME = "transformer_8dp_1pp_1tp_64B_2048S_51200V_20480d_2b_100scale_20iter"
STATE_MULTIPLIERS = [10, 100, 1000, 10000]
BANDWIDTHS_GB_S = [100, 50, 10, 1]
LATENCY_NS = 10000.0  # 10 µs, kept fixed when sweeping bandwidth

NETWORK_TEMPLATE = """# 8 NPUs, remote link: bandwidth {bandwidth} GB/s, latency {latency_ns} ns
topology: [ FullyConnected ]
npus_count: [ 8 ]
bandwidth: [ {bandwidth} ]
latency: [ {latency_ns} ]
"""

BASE_YAML = """model:
  name: "transformer"
  num_layers: 24
  sequence_len: 2048
  vocab_size: 51200
  hidden_size: 20480
  batch_size: 64
  num_microbatches: 8
  bytes_per_val: 2
  scale: 1

parallelism:
  dp_size: 8
  pp_size: 1
  tp_size: 1

num_iterations: 20

wrapper:
  type: "checkpoint"
  mode: "{mode}"
  checkpoint_every_n: 1
  state_multiplier: {state_multiplier}
  overhead_multiplier: 10000
  kickoff_cost_micros: 100
  drain_when_backpressure: false
"""

# Same model/parallelism/iters, no checkpoint (for BASE baseline)
BASE_NO_CKPT_YAML = """model:
  name: "transformer"
  num_layers: 24
  sequence_len: 2048
  vocab_size: 51200
  hidden_size: 20480
  batch_size: 64
  num_microbatches: 8
  bytes_per_val: 2
  scale: 1

parallelism:
  dp_size: 8
  pp_size: 1
  tp_size: 1

num_iterations: 20
"""


def generate_base_traces() -> Path:
    """Generate traces with no checkpoint (BASE). Return trace dir."""
    trace_dir = TR / "sweep_base"
    trace_dir.mkdir(parents=True, exist_ok=True)
    (trace_dir / "et").mkdir(exist_ok=True)

    yaml_path = ML / "_sweep_base.yaml"
    yaml_path.write_text(BASE_NO_CKPT_YAML)

    py = "python3" if sys.version_info >= (3, 0) else "python"
    subprocess.run(
        [py, "synthesise_workload.py", "-c", str(yaml_path)],
        cwd=ML,
        check=True,
        capture_output=True,
    )

    out = ML / "output" / OUTPUT_NAME
    (trace_dir / "comm_groups.json").write_bytes((out / "comm_groups.json").read_bytes())
    for et in (out / "et").glob("*.et"):
        (trace_dir / "et" / et.name).write_bytes(et.read_bytes())

    yaml_path.unlink(missing_ok=True)
    return trace_dir


def generate_traces(state_multiplier: int, mode: str) -> Path:
    """Generate traces for given state_multiplier and mode. Return trace dir."""
    trace_dir = TR / f"sweep_sm{state_multiplier}_{mode}"
    trace_dir.mkdir(parents=True, exist_ok=True)
    (trace_dir / "et").mkdir(exist_ok=True)

    yaml_path = ML / f"_sweep_sm{state_multiplier}_{mode}.yaml"
    mode_val = "remote_sync" if mode == "sync" else "remote_async"
    yaml_content = BASE_YAML.format(
        mode=mode_val,
        state_multiplier=float(state_multiplier),
    )
    yaml_path.write_text(yaml_content)

    py = "python3" if sys.version_info >= (3, 0) else "python"
    subprocess.run(
        [py, "synthesise_workload.py", "-c", str(yaml_path)],
        cwd=ML,
        check=True,
        capture_output=True,
    )

    out = ML / "output" / OUTPUT_NAME
    (trace_dir / "comm_groups.json").write_bytes((out / "comm_groups.json").read_bytes())
    for et in (out / "et").glob("*.et"):
        (trace_dir / "et" / et.name).write_bytes(et.read_bytes())

    yaml_path.unlink(missing_ok=True)
    return trace_dir


def ensure_network_config(bandwidth_gb_s: float) -> Path:
    """Write network config for given bandwidth (GB/s). Return path for Docker."""
    CONFIG.mkdir(parents=True, exist_ok=True)
    path = CONFIG / f"network_8_remote_bw{int(bandwidth_gb_s)}.yml"
    path.write_text(
        NETWORK_TEMPLATE.format(bandwidth=bandwidth_gb_s, latency_ns=LATENCY_NS)
    )
    return path


def run_astrasim(trace_dir: Path, network_yml: Path) -> tuple[str, int]:
    """Run AstraSim in Docker. Return (stdout+stderr, returncode)."""
    workload = f"/workspace/{trace_dir.relative_to(ROOT)}/et/{OUTPUT_NAME}"
    system = "/workspace/experiment/checkpoint_sweep/config/Switch.json"
    network = f"/workspace/{network_yml.relative_to(ROOT)}"
    remote_mem = "/workspace/astra-sim/examples/remote_memory/analytical/no_memory_expansion.json"
    comm = f"/workspace/{trace_dir.relative_to(ROOT)}/comm_groups.json"
    binary = "/workspace/astra-sim/build/astra_analytical/build/bin/AstraSim_Analytical_Congestion_Aware"

    cmd = [
        "docker", "run", "--rm", "--shm-size=8g",
        "-v", f"{ROOT}:/workspace", "-w", "/workspace",
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
    """Extract wall_time, gpu_time, comm_time, overlap from AstraSim log.
    AstraSim prints lines like: [statistics] [info] sys[0], Wall time: 12345
    """
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


def _write_traces_doc(path: Path) -> None:
    """Write TRACES_FOR_VISUALIZER.md with ET/JSON paths for Chakra visualizer."""
    try:
        tr_rel = TR.relative_to(ROOT)
    except ValueError:
        tr_rel = TR
    base_name = OUTPUT_NAME
    lines = [
        "# Trace paths for Chakra visualizer",
        "",
        "All paths are relative to repo root.",
        "",
        "## ET traces (Chakra execution traces, one per NPU)",
        "",
        "Use these with Chakra ET viewers or converters that read `.et` (protobuf) files.",
        "",
        "### BASE (no checkpoint)",
        f"- Directory: `{tr_rel}/sweep_base/et/`",
        f"- Workload base name: `{base_name}`",
        f"- Files: `{base_name}.0.et`, `{base_name}.1.et`, ... `{base_name}.7.et` (8 NPUs)",
        f"- Comm groups: `{tr_rel}/sweep_base/comm_groups.json`",
        "",
        "### REMOTE_SYNC / REMOTE_ASYNC (per state_multiplier)",
        "",
    ]
    for sm in STATE_MULTIPLIERS:
        for mode in ("sync", "async"):
            rel = tr_rel / f"sweep_sm{sm}_{mode}" / "et"
            lines.append(f"- `{rel}/` — mode=REMOTE_{mode.upper()}, state_mult={sm}")
    lines.extend([
        "",
        "Same workload base name and `.0.et` … `.7.et` pattern in each directory.",
        "",
        "## Chakra visualizer commands (typical)",
        "",
        "1. **ET → JSON (if your tool needs JSON):**",
        "   - Chakra Python: load ET with `chakra` and export, or use `et_to_timeline_csv.py`-style pipeline.",
        "2. **Chrome tracing JSON (from simulation timeline):**",
        "   - Run AstraSim with trace enabled (Switch.json `trace-enabled`), then use",
        "   - `experiment/run_all_modes/timeline_visualizer.py` with the issue/callback CSV to get Chrome tracing JSON.",
        "3. **Direct ET paths (examples, from repo root):**",
        f"   - BASE: `experiment/checkpoint_sweep/traces/sweep_base/et/{base_name}.0.et` (and .1.et … .7.et)",
        f"   - REMOTE_SYNC sm=10: `experiment/checkpoint_sweep/traces/sweep_sm10_sync/et/{base_name}.0.et` (and .1–.7)",
        f"   - REMOTE_ASYNC sm=10: `experiment/checkpoint_sweep/traces/sweep_sm10_async/et/{base_name}.0.et` (and .1–.7)",
        "",
    ])
    path.write_text("\n".join(lines))


def _dump_on_parse_failure(parsed: dict, raw: str, returncode: int, context: str) -> None:
    """Print a short hint and tail of raw output when parsing failed."""
    if parsed.get("wall_time_cycles") is not None:
        return
    tail = raw.strip()[-2000:] if len(raw) > 2000 else raw.strip()
    print(f"    [WARN] No stats parsed (returncode={returncode}) for {context}", file=sys.stderr)
    print("    Last 2000 chars of AstraSim output:", file=sys.stderr)
    print("-" * 40, file=sys.stderr)
    print(tail, file=sys.stderr)
    print("-" * 40, file=sys.stderr)


def main():
    results = []
    dumped_failure = False  # dump raw output only on first parse failure

    # Ensure network configs exist for all bandwidths (for Docker mount)
    for bw in BANDWIDTHS_GB_S:
        ensure_network_config(bw)

    # --- BASE (no checkpoint): one trace, run for each bandwidth ---
    print("\n=== BASE (no checkpoint) ===")
    print("  Generating traces: BASE...")
    generate_base_traces()
    trace_dir_base = TR / "sweep_base"
    for bw in BANDWIDTHS_GB_S:
        network_yml = CONFIG / f"network_8_remote_bw{int(bw)}.yml"
        print(f"  Running AstraSim: BASE, bandwidth={bw} GB/s...")
        out, returncode = run_astrasim(trace_dir_base, network_yml)
        parsed = parse_astrasim_output(out)
        context = f"base bw={bw}"
        if parsed.get("wall_time_cycles") is None and not dumped_failure:
            _dump_on_parse_failure(parsed, out, returncode, context)
            dumped_failure = True
        row = {
            "state_multiplier": None,
            "bandwidth_gb_s": bw,
            "mode": "BASE",
            **parsed,
        }
        results.append(row)
        print(f"    Wall: {row['wall_time_cycles']}, GPU: {row['gpu_time_cycles']}, Comm: {row['comm_time_cycles']}, Overlap: {row['overlap_cycles']}")

    # --- Checkpoint modes: sweep state_multiplier × (sync, async) × bandwidth ---
    for sm in STATE_MULTIPLIERS:
        print(f"\n=== state_multiplier={sm} ===")
        for mode in ("sync", "async"):
            print(f"  Generating traces: REMOTE_{mode.upper()}...")
            generate_traces(sm, mode)

        for mode in ("sync", "async"):
            trace_dir = TR / f"sweep_sm{sm}_{mode}"
            for bw in BANDWIDTHS_GB_S:
                network_yml = CONFIG / f"network_8_remote_bw{int(bw)}.yml"
                print(f"  Running AstraSim: REMOTE_{mode.upper()}, bandwidth={bw} GB/s...")
                out, returncode = run_astrasim(trace_dir, network_yml)
                parsed = parse_astrasim_output(out)
                context = f"sm={sm} {mode} bw={bw}"
                if parsed.get("wall_time_cycles") is None and not dumped_failure:
                    _dump_on_parse_failure(parsed, out, returncode, context)
                    dumped_failure = True
                row = {
                    "state_multiplier": sm,
                    "bandwidth_gb_s": bw,
                    "mode": f"REMOTE_{mode.upper()}",
                    **parsed,
                }
                results.append(row)
                print(f"    Wall: {row['wall_time_cycles']}, GPU: {row['gpu_time_cycles']}, Comm: {row['comm_time_cycles']}, Overlap: {row['overlap_cycles']}")

    out_dir = SWEEP_DIR / "results"
    out_dir.mkdir(parents=True, exist_ok=True)

    def _sm_str(r):
        return "" if r["state_multiplier"] is None else str(r["state_multiplier"])

    headers = ["state_multiplier", "bandwidth_gb_s", "mode", "wall_time_cycles", "gpu_time_cycles", "comm_time_cycles", "overlap_cycles"]
    with open(out_dir / "checkpoint_sweep.csv", "w") as f:
        f.write(",".join(headers) + "\n")
        for r in results:
            f.write(f"{_sm_str(r)},{r['bandwidth_gb_s']},{r['mode']},{r['wall_time_cycles'] or ''},{r['gpu_time_cycles'] or ''},{r['comm_time_cycles'] or ''},{r['overlap_cycles']}\n")

    with open(out_dir / "checkpoint_sweep.json", "w") as f:
        json.dump(results, f, indent=2)

    with open(out_dir / "checkpoint_sweep.md", "w") as f:
        f.write("# Checkpoint Sweep: BASE + state_multiplier × bandwidth × mode\n\n")
        f.write("state_multiplier: (none for BASE), " + ", ".join(map(str, STATE_MULTIPLIERS)) + "\n")
        f.write("bandwidth (GB/s): " + ", ".join(map(str, BANDWIDTHS_GB_S)) + "\n")
        f.write("modes: BASE, REMOTE_SYNC, REMOTE_ASYNC\n\n")
        f.write("| state_mult | bandwidth_gb_s | mode | wall_time (cycles) | gpu_time | comm_time | overlap |\n")
        f.write("|------------|----------------|------|--------------------|----------|------------|--------|\n")
        for r in results:
            f.write(f"| {_sm_str(r) or '-'} | {r['bandwidth_gb_s']} | {r['mode']} | {r['wall_time_cycles'] or '-'} | {r['gpu_time_cycles'] or '-'} | {r['comm_time_cycles'] or '-'} | {r['overlap_cycles']} |\n")

    # Write trace paths for Chakra visualizer
    traces_doc = SWEEP_DIR / "TRACES_FOR_VISUALIZER.md"
    _write_traces_doc(traces_doc)

    print(f"\nResults written to {out_dir}/")
    print(f"  - checkpoint_sweep.csv")
    print(f"  - checkpoint_sweep.json")
    print(f"  - checkpoint_sweep.md")
    print(f"\nTrace paths for Chakra visualizer: {traces_doc}")


if __name__ == "__main__":
    main()
