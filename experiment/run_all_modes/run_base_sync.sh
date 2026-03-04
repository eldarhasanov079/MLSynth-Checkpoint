#!/bin/bash
#
# Run ASTRA-sim for BASE and SYNC only, capture logs for timeline visualization.
# Then run the timeline visualizer.
#
# Prereqs:
#   - ASTRA_SIM_DIR pointing to ASTRA-sim build
#   - Traces from ./experiment/gen_traces.sh
#
# Usage: ./experiment/run_all_modes/run_base_sync.sh
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

WORKLOAD_BASE="${WORKSPACE}/traces/base/et/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale"
WORKLOAD_SYNC="${WORKSPACE}/traces/sync_checkpoint/et/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale"

# Checks
if [[ ! -x "$AWARE" ]]; then
  echo "Error: ASTRA-sim not found at $AWARE"
  echo "  Set ASTRA_SIM_DIR to your ASTRA-sim repo (e.g. export ASTRA_SIM_DIR=../astra-sim)"
  exit 1
fi

for w in "$WORKLOAD_BASE" "$WORKLOAD_SYNC"; do
  if [[ ! -f "${w}.0.et" ]]; then
    echo "Error: Trace not found: ${w}.0.et"
    echo "  Run: ./experiment/gen_traces.sh"
    exit 1
  fi
done

echo ""
echo "Running ASTRA-sim (BASE + SYNC)..."
echo ""

echo "=== BASE ==="
"$AWARE" --workload-configuration="$WORKLOAD_BASE" --system-configuration="$SYSTEM" \
  --network-configuration="$NETWORK" \
  --remote-memory-configuration="$REMOTE_MEMORY" \
  --comm-group-configuration="${WORKSPACE}/traces/base/comm_groups.json" 2>&1 | tee "$LOGS_DIR/BASE.log"

echo ""
echo "=== SYNC ==="
"$AWARE" --workload-configuration="$WORKLOAD_SYNC" --system-configuration="$SYSTEM" \
  --network-configuration="$NETWORK" \
  --remote-memory-configuration="$REMOTE_MEMORY" \
  --comm-group-configuration="${WORKSPACE}/traces/sync_checkpoint/comm_groups.json" 2>&1 | tee "$LOGS_DIR/SYNC.log"

echo ""
echo "Logs saved to $LOGS_DIR/"
echo "Run timeline visualization: ./experiment/run_all_modes/visualize_base_sync.sh"
echo ""
