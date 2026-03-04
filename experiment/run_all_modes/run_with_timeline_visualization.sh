#!/bin/bash
#
# Run all 5 checkpoint modes with ASTRA-sim, capture execution traces, and generate
# Chrome tracing JSON timelines for each mode. Open outputs in chrome://tracing.
#
# Usage: ./experiment/run_all_modes/run_with_timeline_visualization.sh
#   (from repo root; requires ASTRA_SIM_DIR and optionally CHAKRA_DIR)
#
# Outputs:
#   experiment/run_all_modes/timeline_logs/<MODE>.log   - raw simulator output
#   experiment/run_all_modes/timeline_csv/<MODE>.csv    - extracted issue/callback trace
#   experiment/run_all_modes/timeline_json/<MODE>.json  - Chrome tracing format
#
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXPERIMENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT="$(cd "$EXPERIMENT_DIR/.." && pwd)"
WORKSPACE="${WORKSPACE:-$EXPERIMENT_DIR}"
ASTRA_SIM_DIR="${ASTRA_SIM_DIR:-$(cd "$EXPERIMENT_DIR/../astra-sim" 2>/dev/null && pwd)}"
CHAKRA_DIR="${CHAKRA_DIR:-$(cd "$ROOT/chakra" 2>/dev/null && pwd)}"

AWARE="${ASTRA_SIM_DIR}/build/astra_analytical/build/bin/AstraSim_Analytical_Congestion_Aware"
SYSTEM="${WORKSPACE}/astrasim_configs/Switch.json"
NETWORK="${WORKSPACE}/astrasim_configs/network_4.yml"
REMOTE_MEMORY="${ASTRA_SIM_DIR}/examples/remote_memory/analytical/no_memory_expansion.json"

# Timeline visualization params (match ASTRA-sim config)
NUM_NPUS=4
NPU_FREQUENCY_MHZ=1500   # 1.5 GHz

# Output directories
LOGS_DIR="$SCRIPT_DIR/timeline_logs"
CSV_DIR="$SCRIPT_DIR/timeline_csv"
JSON_DIR="$SCRIPT_DIR/timeline_json"
mkdir -p "$LOGS_DIR" "$CSV_DIR" "$JSON_DIR"

# Resolve timeline visualizer (Chakra's Python script)
TIMELINE_VIZ=""
if [[ -n "$CHAKRA_DIR" && -f "$CHAKRA_DIR/src/timeline_visualizer/timeline_visualizer.py" ]]; then
  TIMELINE_VIZ="$CHAKRA_DIR/src/timeline_visualizer/timeline_visualizer.py"
elif command -v chakra_timeline_visualizer &>/dev/null; then
  TIMELINE_VIZ="chakra_timeline_visualizer"
else
  echo "Note: chakra_timeline_visualizer not found. Set CHAKRA_DIR to Chakra repo for timeline JSON generation."
  echo "      Trace CSVs will still be extracted. Timeline JSON will be skipped."
fi

[[ -x "$AWARE" ]] || { echo "Error: ASTRA-sim not found at $AWARE. Set ASTRA_SIM_DIR."; exit 1; }

get_workload() {
  case "$1" in
    BASE) echo "${WORKSPACE}/traces/base/et/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale" ;;
    SYNC) echo "${WORKSPACE}/traces/sync_checkpoint/et/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale" ;;
    ASYNC) echo "${WORKSPACE}/traces/async_checkpoint/et/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale_3iter" ;;
    REMOTE_SYNC) echo "${WORKSPACE}/traces/remote_checkpoint/et/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale_3iter" ;;
    REMOTE_ASYNC) echo "${WORKSPACE}/traces/remote_async_checkpoint/et/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale_3iter" ;;
    *) echo "" ;;
  esac
}

get_comm() {
  case "$1" in
    BASE) echo "${WORKSPACE}/traces/base/comm_groups.json" ;;
    SYNC) echo "${WORKSPACE}/traces/sync_checkpoint/comm_groups.json" ;;
    ASYNC) echo "${WORKSPACE}/traces/async_checkpoint/comm_groups.json" ;;
    REMOTE_SYNC) echo "${WORKSPACE}/traces/remote_checkpoint/comm_groups.json" ;;
    REMOTE_ASYNC) echo "${WORKSPACE}/traces/remote_async_checkpoint/comm_groups.json" ;;
    *) echo "" ;;
  esac
}

# Verify traces exist
for m in BASE SYNC ASYNC REMOTE_SYNC REMOTE_ASYNC; do
  w=$(get_workload "$m")
  [[ -f "${w}.0.et" ]] || { echo "Error: Trace not found: ${w}.0.et. Run ./experiment/gen_traces.sh first."; exit 1; }
done

run_one() {
  local name="$1"
  local workload
  local comm
  workload=$(get_workload "$name")
  comm=$(get_comm "$name")
  local log="$LOGS_DIR/${name}.log"
  local csv="$CSV_DIR/${name}.csv"
  local json="$JSON_DIR/${name}.json"

  echo ""
  echo "═══════════════════════════════════════════════════════════════"
  echo "  $name"
  echo "═══════════════════════════════════════════════════════════════"

  echo "  [1/3] Running ASTRA-sim (output -> $log)..."
  "$AWARE" --workload-configuration="$workload" --system-configuration="$SYSTEM" \
    --network-configuration="$NETWORK" --remote-memory-configuration="$REMOTE_MEMORY" \
    --comm-group-configuration="$comm" 2>&1 | tee "$log" || true

  echo "  [2/3] Extracting trace CSV..."
  python3 "$SCRIPT_DIR/extract_trace_csv.py" "$log" "$csv"
  n=$(wc -l < "$csv" 2>/dev/null || echo 0)
  echo "        -> $n events in $csv"

  if [[ -n "$TIMELINE_VIZ" ]]; then
    echo "  [3/3] Generating Chrome trace JSON..."
    if [[ "$TIMELINE_VIZ" == *.py ]]; then
      python3 "$TIMELINE_VIZ" \
        --input_filename "$csv" \
        --output_filename "$json" \
        --num_npus "$NUM_NPUS" \
        --npu_frequency "$NPU_FREQUENCY_MHZ" \
        --log_filename "$SCRIPT_DIR/timeline_logs/${name}_viz.log" 2>/dev/null || true
    else
      $TIMELINE_VIZ \
        --input_filename "$csv" \
        --output_filename "$json" \
        --num_npus "$NUM_NPUS" \
        --npu_frequency "$NPU_FREQUENCY_MHZ" 2>/dev/null || true
    fi
    if [[ -f "$json" ]]; then
      echo "        -> $json (open in chrome://tracing)"
    else
      echo "        -> (skipped - check ${name}_viz.log)"
    fi
  else
    echo "  [3/3] Skipped (no timeline visualizer)"
  fi
}

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║  Run All Modes + Timeline Visualization                      ║"
echo "╚═══════════════════════════════════════════════════════════════╝"

for mode in BASE SYNC ASYNC REMOTE_SYNC REMOTE_ASYNC; do
  run_one "$mode"
done

echo ""
echo "───────────────────────────────────────────────────────────────"
echo "  Done. Summary:"
echo "    Logs:  $LOGS_DIR/"
echo "    CSV:   $CSV_DIR/"
echo "    JSON:  $JSON_DIR/"
echo ""
echo "  View timelines: open each JSON in chrome://tracing"
echo ""
