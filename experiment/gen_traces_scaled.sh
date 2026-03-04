#!/bin/bash
# Generate scaled remote checkpoint traces (8 NPUs, 20 iter, big checkpoint).
# Run from repo root.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ML="$ROOT/MLSynth"
TR="$ROOT/experiment/traces"
cd "$ML"
mkdir -p "$TR"/scaled_remote_checkpoint/et "$TR"/scaled_remote_async_checkpoint/et

OUTPUT_NAME="transformer_8dp_1pp_1tp_64B_2048S_51200V_20480d_2b_100scale_20iter"
py() { python3 synthesise_workload.py -c "$1" 2>/dev/null || python synthesise_workload.py -c "$1"; }

echo "Generating REMOTE_SYNC traces..."
py input_scaled_remote_checkpoint.yaml
cp output/"$OUTPUT_NAME"/comm_groups.json "$TR/scaled_remote_checkpoint/"
cp output/"$OUTPUT_NAME"/et/*.et "$TR/scaled_remote_checkpoint/et/"

echo "Generating REMOTE_ASYNC traces..."
py input_scaled_remote_async_checkpoint.yaml
cp output/"$OUTPUT_NAME"/comm_groups.json "$TR/scaled_remote_async_checkpoint/"
cp output/"$OUTPUT_NAME"/et/*.et "$TR/scaled_remote_async_checkpoint/et/"

echo "Done. Traces in $TR/scaled_remote_checkpoint/ and $TR/scaled_remote_async_checkpoint/"
