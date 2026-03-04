#!/bin/bash
#
# Generate timeline visualizations for base, sync_checkpoint, remote_checkpoint.
# Uses logs from timeline_logs/ (captured by run_capture_logs.sh).
#
# Usage: ./experiment/run_all_modes/visualize_base_sync.sh
#   Run from repo root. Requires logs in timeline_logs/.
#
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOGS_DIR="$SCRIPT_DIR/timeline_logs"
CSV_DIR="$SCRIPT_DIR/timeline_csv"
JSON_DIR="$SCRIPT_DIR/timeline_json"
NUM_NPUS=4
NPU_FREQUENCY_MHZ=1500

mkdir -p "$CSV_DIR" "$JSON_DIR"

TIMELINE_VIZ="python3 $SCRIPT_DIR/timeline_visualizer.py"
[[ -f "$SCRIPT_DIR/timeline_visualizer.py" ]] || { echo "Error: timeline_visualizer.py not found."; exit 1; }

do_mode() {
  local name="$1"
  local log_src="$LOGS_DIR/${name}.log"
  local csv="$CSV_DIR/${name}.csv"
  local json="$JSON_DIR/${name}.json"

  if [[ ! -f "$log_src" ]]; then
    echo "[$name] Skip: no log at $log_src"
    return 1
  fi
  if ! grep -q "issue,sys->id=" "$log_src" 2>/dev/null; then
    echo "[$name] Skip: log has no trace data (run ASTRA-sim with $name workload)"
    return 1
  fi

  echo "[$name] Extracting CSV..."
  python3 "$SCRIPT_DIR/extract_trace_csv.py" "$log_src" "$csv"
  n=$(wc -l < "$csv" 2>/dev/null || echo 0)
  echo "       -> $n events"

  echo "[$name] Generating timeline JSON..."
  $TIMELINE_VIZ --input_filename "$csv" --output_filename "$json" \
    --num_npus "$NUM_NPUS" --npu_frequency "$NPU_FREQUENCY_MHZ"

  if [[ -f "$json" ]]; then
    echo "       -> $json"
  else
    echo "       -> FAILED"
    return 1
  fi
}

echo ""
echo "Timeline visualization: base, sync_checkpoint, remote_checkpoint"
echo "---------------------------------------------------------------"

for mode in base sync_checkpoint remote_checkpoint; do
  do_mode "$mode" || true
  echo ""
done

echo "---------------------------------------------------------------"
echo "Open in chrome://tracing:"
for mode in base sync_checkpoint remote_checkpoint; do
  [[ -f "$JSON_DIR/${mode}.json" ]] && echo "  $JSON_DIR/${mode}.json"
done
echo ""
