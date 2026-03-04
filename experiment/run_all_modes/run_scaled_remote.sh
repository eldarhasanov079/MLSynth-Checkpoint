#!/bin/bash
# Run scaled remote checkpoint experiment (8 NPUs, 20 iter, 10µs/10 GB/s).
# Uses Docker. Run from repo root.
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXPERIMENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT="$(cd "$EXPERIMENT_DIR/.." && pwd)"
WORKSPACE="${WORKSPACE:-$EXPERIMENT_DIR}"
ASTRA_SIM_DIR="${ASTRA_SIM_DIR:-$ROOT/astra-sim}"

AWARE="/workspace/astra-sim/build/astra_analytical/build/bin/AstraSim_Analytical_Congestion_Aware"
SYSTEM="/workspace/experiment/astrasim_configs/Switch.json"
NETWORK="/workspace/experiment/astrasim_configs/network_8_remote.yml"
REMOTE_MEMORY="/workspace/astra-sim/examples/remote_memory/analytical/no_memory_expansion.json"

WORKLOAD_BASE="transformer_8dp_1pp_1tp_64B_2048S_51200V_20480d_2b_100scale_20iter"

run_one() {
  local name="$1"
  local trace_dir="$2"
  echo "=== $name ==="
  docker run --rm --shm-size=8g -v "$ROOT:/workspace" -w /workspace astra-sim:latest \
    "$AWARE" \
    --workload-configuration="/workspace/experiment/traces/$trace_dir/et/$WORKLOAD_BASE" \
    --system-configuration="$SYSTEM" \
    --network-configuration="$NETWORK" \
    --remote-memory-configuration="$REMOTE_MEMORY" \
    --comm-group-configuration="/workspace/experiment/traces/$trace_dir/comm_groups.json"
  echo ""
}

run_one "REMOTE_SYNC (scaled)" "scaled_remote_checkpoint"
run_one "REMOTE_ASYNC (scaled)" "scaled_remote_async_checkpoint"
echo "Done."
