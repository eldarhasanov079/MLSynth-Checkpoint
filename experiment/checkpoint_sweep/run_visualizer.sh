#!/usr/bin/env bash
set -euo pipefail

# Repo root (adjust if you run from elsewhere)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

CSV_DIR="$ROOT/experiment/checkpoint_sweep/timeline_csv"
JSON_DIR="$ROOT/experiment/checkpoint_sweep/timeline_json"
TRACES_DIR="$ROOT/experiment/checkpoint_sweep/traces"
BASE_NAME="transformer_8dp_1pp_1tp_64B_2048S_51200V_20480d_2b_100scale_20iter"
NPUS=8
FREQ=1500   # 1.5 GHz in MHz-like units (cycles per ns)

mkdir -p "$CSV_DIR" "$JSON_DIR"

run_one () {
  local label="$1"        # e.g. base, sm10_sync, sm10_async
  local subdir="$2"       # e.g. sweep_base, sweep_sm10_sync
  local workload="$TRACES_DIR/$subdir/et/$BASE_NAME"

  local csv="$CSV_DIR/${label}.csv"
  local json="$JSON_DIR/${label}.json"

  echo "=== $label ==="
  echo "  ET base: $workload"
  echo "  CSV:     $csv"
  echo "  JSON:    $json"

  python3 "$ROOT/experiment/run_all_modes/et_to_timeline_csv.py" \
    --workload "$workload" \
    --output "$csv" \
    --num_npus "$NPUS"

  chakra_timeline_visualizer \
    --input_filename "$csv" \
    --output_filename "$json" \
    --num_npus "$NPUS" \
    --npu_frequency "$FREQ"
}

# BASE (no checkpoint)
run_one "base" "sweep_base"

# REMOTE_SYNC / REMOTE_ASYNC for each state_multiplier
for sm in 10 100 1000 10000; do
  run_one "sm${sm}_sync"  "sweep_sm${sm}_sync"
  run_one "sm${sm}_async" "sweep_sm${sm}_async"
done

echo
echo "All timelines written under:"
echo "  CSV : $CSV_DIR"
echo "  JSON: $JSON_DIR"