#!/bin/bash
# Run ASTRA-sim on all 5 checkpoint modes. Requires traces and ASTRA-sim built.
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXPERIMENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACE="${WORKSPACE:-$EXPERIMENT_DIR}"
ASTRA_SIM_DIR="${ASTRA_SIM_DIR:-$(cd "$EXPERIMENT_DIR/../astra-sim" 2>/dev/null && pwd)}"
AWARE="${ASTRA_SIM_DIR}/build/astra_analytical/build/bin/AstraSim_Analytical_Congestion_Aware"
SYSTEM="${WORKSPACE}/astrasim_configs/Switch.json"
NETWORK="${WORKSPACE}/astrasim_configs/network_4.yml"
REMOTE_MEMORY="${ASTRA_SIM_DIR}/examples/remote_memory/analytical/no_memory_expansion.json"

WORKLOAD_BASE="${WORKSPACE}/traces/base/et/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale"
WORKLOAD_SYNC="${WORKSPACE}/traces/sync_checkpoint/et/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale"
WORKLOAD_ASYNC="${WORKSPACE}/traces/async_checkpoint/et/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale_3iter"
WORKLOAD_REMOTE="${WORKSPACE}/traces/remote_checkpoint/et/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale_3iter"
WORKLOAD_REMOTE_ASYNC="${WORKSPACE}/traces/remote_async_checkpoint/et/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale_3iter"

[[ -x "$AWARE" ]] || { echo "Error: ASTRA-sim not found at $AWARE. Set ASTRA_SIM_DIR and build."; exit 1; }
for w in "$WORKLOAD_BASE" "$WORKLOAD_SYNC" "$WORKLOAD_ASYNC" "$WORKLOAD_REMOTE" "$WORKLOAD_REMOTE_ASYNC"; do
  [[ -f "${w}.0.et" ]] || { echo "Error: Trace not found: ${w}.0.et. Run trace generation first."; exit 1; }
done

run_one() {
  local name="$1"
  local workload="$2"
  local comm="$3"
  echo "=== $name ==="
  "$AWARE" --workload-configuration="$workload" --system-configuration="$SYSTEM" \
    --network-configuration="$NETWORK" --remote-memory-configuration="$REMOTE_MEMORY" \
    --comm-group-configuration="$comm"
  echo ""
}

run_one "BASE" "$WORKLOAD_BASE" "${WORKSPACE}/traces/base/comm_groups.json"
run_one "SYNC" "$WORKLOAD_SYNC" "${WORKSPACE}/traces/sync_checkpoint/comm_groups.json"
run_one "ASYNC" "$WORKLOAD_ASYNC" "${WORKSPACE}/traces/async_checkpoint/comm_groups.json"
run_one "REMOTE_SYNC" "$WORKLOAD_REMOTE" "${WORKSPACE}/traces/remote_checkpoint/comm_groups.json"
run_one "REMOTE_ASYNC" "$WORKLOAD_REMOTE_ASYNC" "${WORKSPACE}/traces/remote_async_checkpoint/comm_groups.json"
echo "Done."
