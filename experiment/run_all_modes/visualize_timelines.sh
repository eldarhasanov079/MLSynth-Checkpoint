#!/bin/bash
#
# Generate timeline visualizations from existing ASTRA-sim logs.
# Use this if you already ran the simulation and have logs in timeline_logs/.
#
# Usage: ./experiment/run_all_modes/visualize_timelines.sh [log_dir]
#   Default log_dir: experiment/run_all_modes/timeline_logs
#
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${1:-$SCRIPT_DIR/timeline_logs}"
CSV_DIR="$SCRIPT_DIR/timeline_csv"
JSON_DIR="$SCRIPT_DIR/timeline_json"

CHAKRA_DIR="${CHAKRA_DIR:-$(cd "$SCRIPT_DIR/../../chakra" 2>/dev/null && pwd)}"
NUM_NPUS=4
NPU_FREQUENCY_MHZ=1500

mkdir -p "$CSV_DIR" "$JSON_DIR"

TIMELINE_VIZ=""
if [[ -n "$CHAKRA_DIR" && -f "$CHAKRA_DIR/src/timeline_visualizer/timeline_visualizer.py" ]]; then
  TIMELINE_VIZ="$CHAKRA_DIR/src/timeline_visualizer/timeline_visualizer.py"
elif command -v chakra_timeline_visualizer &>/dev/null; then
  TIMELINE_VIZ="chakra_timeline_visualizer"
fi

for mode in BASE SYNC ASYNC REMOTE_SYNC REMOTE_ASYNC; do
  log="$LOG_DIR/${mode}.log"
  csv="$CSV_DIR/${mode}.csv"
  json="$JSON_DIR/${mode}.json"

  if [[ ! -f "$log" ]]; then
    echo "[$mode] Skip: $log not found"
    continue
  fi

  echo "[$mode] Extracting CSV..."
  python3 "$SCRIPT_DIR/extract_trace_csv.py" "$log" "$csv"

  if [[ -n "$TIMELINE_VIZ" ]]; then
    echo "[$mode] Generating JSON..."
    if [[ "$TIMELINE_VIZ" == *.py ]]; then
      python3 "$TIMELINE_VIZ" --input_filename "$csv" --output_filename "$json" \
        --num_npus "$NUM_NPUS" --npu_frequency "$NPU_FREQUENCY_MHZ" 2>/dev/null || true
    else
      $TIMELINE_VIZ --input_filename "$csv" --output_filename "$json" \
        --num_npus "$NUM_NPUS" --npu_frequency "$NPU_FREQUENCY_MHZ" 2>/dev/null || true
    fi
    [[ -f "$json" ]] && echo "        -> $json"
  fi
done

echo ""
echo "Open JSON files in chrome://tracing"
