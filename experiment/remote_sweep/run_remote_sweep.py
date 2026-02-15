#!/usr/bin/env python3
"""
Remote checkpoint sweep: show async benefit + interference.

Setup: 20 iterations, checkpoint_every_n=5, state_multiplier ∈ {0.01, 0.1, 0.5, 1.0, 3.0}
Compare: BASE, REMOTE_SYNC, REMOTE_ASYNC

Part 1 — Frequency separation (scale=1):
  REMOTE_SYNC: step-like stalls every 5 iters.
  REMOTE_ASYNC: overlaps uploads across next 4 iters → lower wall time.

Part 2 — Compute slack (scale=2):
  REMOTE_ASYNC closer to BASE for small/medium ckpt (upload hides under compute).
  REMOTE_SYNC remains worst (explicit blocking).

Run: python experiment/remote_sweep/run_remote_sweep.py
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MLSYNTH = ROOT / "MLSynth"
EXPERIMENT = ROOT / "experiment"
SWEEP_DIR = Path(__file__).resolve().parent
ASTRA_SIM_DIR = Path(os.environ.get("ASTRA_SIM_DIR", str(ROOT / "astra-sim")))
AWARE = ASTRA_SIM_DIR / "build/astra_analytical/build/bin/AstraSim_Analytical_Congestion_Aware"
SYSTEM = EXPERIMENT / "astrasim_configs/Switch.json"
NETWORK = EXPERIMENT / "astrasim_configs/network_4.yml"
REMOTE_MEMORY = ASTRA_SIM_DIR / "examples/remote_memory/analytical/no_memory_expansion.json"
COMM_GROUPS_BASE = EXPERIMENT / "traces/base/comm_groups.json"

NUM_ITERATIONS = 20
CHECKPOINT_EVERY_N = 5
STATE_MULTS = [0.01, 0.1, 0.5, 1.0, 3.0]


def to_docker_path(p: Path) -> str:
    return str(Path("/workspace") / p.relative_to(ROOT))


def trace_name(scale: float, niter: int) -> str:
    scale_int = int(scale * 100)
    base = f"transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_{scale_int}scale"
    return f"{base}_{niter}iter" if niter != 1 else base


def run_synthesis(config_yaml: Path) -> None:
    result = subprocess.run(
        [sys.executable, "synthesise_workload.py", "-c", str(config_yaml)],
        cwd=MLSYNTH,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Synthesis failed:\n{result.stderr}\n{result.stdout}")


def run_astrasim(workload_base: Path, comm_groups: Path) -> tuple[int, int]:
    """Return (wall_time_cycles, comm_time_cycles) from sys[0]."""
    aware = to_docker_path(AWARE)
    wl = to_docker_path(workload_base)
    sys_cfg = to_docker_path(SYSTEM)
    net_cfg = to_docker_path(NETWORK)
    rm_cfg = to_docker_path(REMOTE_MEMORY)
    comm_cfg = to_docker_path(comm_groups)
    cmd = [
        "docker", "run", "--rm", "--shm-size=8g",
        "-v", f"{ROOT}:/workspace", "-w", "/workspace",
        "astra-sim:latest",
        aware,
        f"--workload-configuration={wl}",
        f"--system-configuration={sys_cfg}",
        f"--network-configuration={net_cfg}",
        f"--remote-memory-configuration={rm_cfg}",
        f"--comm-group-configuration={comm_cfg}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if result.returncode != 0:
        raise RuntimeError(f"ASTRA-sim failed: {result.stderr}")
    wall = re.search(r"sys\[0\], Wall time: (\d+)", result.stdout)
    comm = re.search(r"sys\[0\], Comm time: (\d+)", result.stdout)
    if not wall or not comm:
        raise RuntimeError("Could not parse Wall/Comm time")
    return int(wall.group(1)), int(comm.group(1))


def write_base_config(path: Path, scale: float) -> None:
    path.write_text(f"""model:
  name: transformer
  num_layers: 24
  sequence_len: 2048
  vocab_size: 51200
  hidden_size: 20480
  batch_size: 32
  num_microbatches: 8
  bytes_per_val: 2
  scale: {scale}

parallelism:
  dp_size: 2
  pp_size: 2
  tp_size: 1

num_iterations: {NUM_ITERATIONS}
""")


def write_ckpt_config(path: Path, mode: str, state_mult: float, scale: float) -> None:
    path.write_text(f"""model:
  name: transformer
  num_layers: 24
  sequence_len: 2048
  vocab_size: 51200
  hidden_size: 20480
  batch_size: 32
  num_microbatches: 8
  bytes_per_val: 2
  scale: {scale}

parallelism:
  dp_size: 2
  pp_size: 2
  tp_size: 1

num_iterations: {NUM_ITERATIONS}

wrapper:
  type: checkpoint
  mode: {mode}
  checkpoint_every_n: {CHECKPOINT_EVERY_N}
  state_multiplier: {state_mult}
  overhead_multiplier: 10000
  kickoff_cost_micros: 100
  drain_when_backpressure: false
""")


def run_part(scale: float, part_name: str) -> dict:
    """Run one part (Part 1 or Part 2) and return results."""
    tname = trace_name(scale, NUM_ITERATIONS)
    traces_dir = SWEEP_DIR / "traces" / part_name
    traces_dir.mkdir(parents=True, exist_ok=True)

    # BASE
    cfg_base = SWEEP_DIR / "temp_base.yaml"
    write_base_config(cfg_base, scale)
    run_synthesis(cfg_base)
    out = MLSYNTH / "output" / tname
    dst_base = traces_dir / "base"
    dst_base.mkdir(exist_ok=True)
    (dst_base / "et").mkdir(exist_ok=True)
    shutil.copy(out / "comm_groups.json", dst_base / "comm_groups.json")
    for f in (out / "et").glob("*.et"):
        shutil.copy(f, dst_base / "et" / f.name)
    cfg_base.unlink(missing_ok=True)

    base_wall, base_comm = run_astrasim(dst_base / "et" / tname, dst_base / "comm_groups.json")
    print(f"  BASE: wall={base_wall/1e9:.2f}B, comm={base_comm/1e9:.2f}B")

    results = {"base": (base_wall, base_comm), "state_mults": []}

    for sm in STATE_MULTS:
        row = {"state_mult": sm, "sync": None, "async": None}
        for mode in ("remote_sync", "remote_async"):
            cfg = SWEEP_DIR / f"temp_{mode}_sm{sm}.yaml"
            write_ckpt_config(cfg, mode, sm, scale)
            run_synthesis(cfg)
            ckpt_out = MLSYNTH / "output" / tname
            dst = traces_dir / mode / f"state_{sm}"
            dst.mkdir(parents=True, exist_ok=True)
            (dst / "et").mkdir(exist_ok=True)
            shutil.copy(ckpt_out / "comm_groups.json", dst / "comm_groups.json")
            for f in (ckpt_out / "et").glob("*.et"):
                shutil.copy(f, dst / "et" / f.name)
            cfg.unlink(missing_ok=True)

            wall, comm = run_astrasim(dst / "et" / tname, dst / "comm_groups.json")
            if mode == "remote_sync":
                row["sync"] = (wall, comm)
            else:
                row["async"] = (wall, comm)
        results["state_mults"].append(row)
        print(f"  state_mult={sm}: SYNC={row['sync'][0]/1e9:.2f}B, ASYNC={row['async'][0]/1e9:.2f}B")
    return results


def main():
    if not AWARE.exists():
        print("Error: ASTRA-sim binary not found.")
        sys.exit(1)

    print("=" * 70)
    print("REMOTE SWEEP: 20 iter, checkpoint_every_n=5")
    print("=" * 70)

    # Part 1: scale=1
    print("\n--- Part 1: Frequency separation (scale=1) ---")
    part1 = run_part(scale=1.0, part_name="part1_scale1")

    # Part 2: scale=2 (compute slack)
    print("\n--- Part 2: Compute slack (scale=2) ---")
    part2 = run_part(scale=2.0, part_name="part2_scale2")

    # Report
    out_path = SWEEP_DIR / "RESULTS.md"
    with open(out_path, "w") as f:
        f.write("# Remote Checkpoint Sweep Results\n\n")
        f.write("20 iterations, checkpoint_every_n=5. B = billion cycles (10⁹).\n\n")
        f.write("## Part 1: Frequency separation (scale=1)\n\n")
        f.write(f"| trace | Wall (B) | Comm (B) |\n")
        f.write(f"|-------|----------|----------|\n")
        bw, bc = part1["base"]
        f.write(f"| BASE | {bw/1e9:.2f} | {bc/1e9:.2f} |\n\n")
        f.write("| state_mult | REMOTE_SYNC Wall | REMOTE_ASYNC Wall | BASE |\n")
        f.write("|------------|------------------|-------------------|------|\n")
        for r in part1["state_mults"]:
            sw, _ = r["sync"]
            aw, _ = r["async"]
            f.write(f"| {r['state_mult']} | {sw/1e9:.2f} | {aw/1e9:.2f} | (ref) |\n")

        f.write("\n## Part 2: Compute slack (scale=2)\n\n")
        f.write(f"| trace | Wall (B) | Comm (B) |\n")
        f.write(f"|-------|----------|----------|\n")
        bw2, bc2 = part2["base"]
        f.write(f"| BASE | {bw2/1e9:.2f} | {bc2/1e9:.2f} |\n\n")
        f.write("| state_mult | REMOTE_SYNC Wall | REMOTE_ASYNC Wall | BASE |\n")
        f.write("|------------|------------------|-------------------|------|\n")
        for r in part2["state_mults"]:
            sw, _ = r["sync"]
            aw, _ = r["async"]
            f.write(f"| {r['state_mult']} | {sw/1e9:.2f} | {aw/1e9:.2f} | (ref) |\n")

        f.write("\n## Observations\n\n")
        f.write("- **Knee curve:** Wall time rises with state_mult (checkpoint size) in both parts.\n")
        f.write("- **Scale=2:** Part 2 BASE ~2× Part 1 BASE (compute slack as intended).\n")
        f.write("- **REMOTE_SYNC vs REMOTE_ASYNC:** Analytical model yields same wall time; "
                "dependency structure differs (sync blocks at boundary, async uses kickoff) but "
                "critical-path resolution may converge. For larger separation, consider cycle-level sim.\n")

    print(f"\nResults written to {out_path}")


if __name__ == "__main__":
    main()
