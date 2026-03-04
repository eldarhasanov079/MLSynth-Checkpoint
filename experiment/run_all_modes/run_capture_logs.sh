#!/bin/bash
#
# Run ASTRA-sim for base, sync_checkpoint, and remote_checkpoint.
# Captures execution traces to timeline_logs/ for timeline visualization comparison.
#
# Uses native binary if available; falls back to Docker (astra-sim:latest) when
# binary cannot execute (e.g. Linux binary on macOS). Matches run.sh + remote_sweep.
#
# Prereqs:
#   - ASTRA_SIM_DIR (path to astra-sim repo)
#   - Traces from ./experiment/gen_traces.sh
#   - For Docker fallback: docker, astra-sim:latest image
#
# Usage: ./experiment/run_all_modes/run_capture_logs.sh
#
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXPERIMENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT="$(cd "$EXPERIMENT_DIR/.." && pwd)"
WORKSPACE="${WORKSPACE:-$EXPERIMENT_DIR}"
ASTRA_SIM_DIR="${ASTRA_SIM_DIR:-$(cd "$EXPERIMENT_DIR/../astra-sim" 2>/dev/null && pwd)}"

AWARE="${ASTRA_SIM_DIR}/build/astra_analytical/build/bin/AstraSim_Analytical_Congestion_Aware"
SYSTEM="${WORKSPACE}/astrasim_configs/Switch.json"
NETWORK="${WORKSPACE}/astrasim_configs/network_4.yml"
REMOTE_MEMORY="${ASTRA_SIM_DIR}/examples/remote_memory/analytical/no_memory_expansion.json"

LOGS_DIR="$SCRIPT_DIR/timeline_logs"
mkdir -p "$LOGS_DIR"

to_docker_path() {
  echo "/workspace/$(python3 -c "import os.path; print(os.path.relpath('$1', '$ROOT'))")"
}

get_workload() {
  case "$1" in
    base) echo "${WORKSPACE}/traces/base/et/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale" ;;
    sync_checkpoint) echo "${WORKSPACE}/traces/sync_checkpoint/et/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale" ;;
    remote_checkpoint) echo "${WORKSPACE}/traces/remote_checkpoint/et/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale_3iter" ;;
    *) echo "" ;;
  esac
}

get_comm() {
  case "$1" in
    base) echo "${WORKSPACE}/traces/base/comm_groups.json" ;;
    sync_checkpoint) echo "${WORKSPACE}/traces/sync_checkpoint/comm_groups.json" ;;
    remote_checkpoint) echo "${WORKSPACE}/traces/remote_checkpoint/comm_groups.json" ;;
    *) echo "" ;;
  esac
}

# Prefer native binary; use Docker if binary missing or cannot execute
USE_DOCKER=0
if [[ -x "$AWARE" ]]; then
  if "$AWARE" --help &>/dev/null; then
    :
  else
    USE_DOCKER=1
    echo "Native binary cannot execute (arch mismatch?). Using Docker."
  fi
else
  USE_DOCKER=1
  echo "Native binary not found. Using Docker (astra-sim:latest)."
fi

if [[ "$USE_DOCKER" -eq 1 ]]; then
  if ! command -v docker &>/dev/null; then
    echo "Error: Docker not found. Install Docker or build ASTRA-sim natively for your platform."
    exit 1
  fi
  AWARE=$(to_docker_path "$AWARE")
  SYSTEM=$(to_docker_path "$SYSTEM")
  NETWORK=$(to_docker_path "$NETWORK")
  REMOTE_MEMORY=$(to_docker_path "$REMOTE_MEMORY")
fi

for mode in base sync_checkpoint remote_checkpoint; do
  w=$(get_workload "$mode")
  if [[ ! -f "${w}.0.et" ]]; then
    echo "Error: Trace not found: ${w}.0.et"
    echo "  Run: ./experiment/gen_traces.sh"
    exit 1
  fi
done

echo ""
echo "Capturing execution traces for base, sync_checkpoint, remote_checkpoint..."
echo ""

run_astrasim() {
  local w="$1"
  local c="$2"
  if [[ "$USE_DOCKER" -eq 1 ]]; then
    w=$(to_docker_path "$w")
    c=$(to_docker_path "$c")
    docker run --rm --shm-size=8g -v "${ROOT}:/workspace" -w /workspace astra-sim:latest \
      "$AWARE" --workload-configuration="$w" --system-configuration="$SYSTEM" \
      --network-configuration="$NETWORK" --remote-memory-configuration="$REMOTE_MEMORY" \
      --comm-group-configuration="$c"
  else
    "$AWARE" --workload-configuration="$w" --system-configuration="$SYSTEM" \
      --network-configuration="$NETWORK" --remote-memory-configuration="$REMOTE_MEMORY" \
      --comm-group-configuration="$c"
  fi
}

for mode in base sync_checkpoint remote_checkpoint; do
  echo "=== $mode ==="
  w=$(get_workload "$mode")
  c=$(get_comm "$mode")
  run_astrasim "$w" "$c" 2>&1 | tee "$LOGS_DIR/${mode}.log"
  echo ""
done

echo "Logs saved to $LOGS_DIR/"
echo "Next: run preprocess + visualize (see README or COMMANDS.md)"
echo ""
