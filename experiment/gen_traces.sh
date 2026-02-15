#!/bin/bash
# Generate traces for run_all_modes. Run from repo root.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ML="$ROOT/MLSynth"
TR="$ROOT/experiment/traces"
cd "$ML"
mkdir -p "$TR"/{base,sync_checkpoint,async_checkpoint,remote_checkpoint,remote_async_checkpoint}
for d in base sync_checkpoint async_checkpoint remote_checkpoint remote_async_checkpoint; do mkdir -p "$TR/$d/et"; done
py() { python3 synthesise_workload.py -c "$1" 2>/dev/null || python synthesise_workload.py -c "$1"; }
py input_base.yaml && cp output/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale/comm_groups.json "$TR/base/" && cp output/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale/et/*.et "$TR/base/et/"
py input_checkpoint.yaml && cp output/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale/comm_groups.json "$TR/sync_checkpoint/" && cp output/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale/et/*.et "$TR/sync_checkpoint/et/"
py input_async_checkpoint.yaml && cp output/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale_3iter/comm_groups.json "$TR/async_checkpoint/" && cp output/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale_3iter/et/*.et "$TR/async_checkpoint/et/"
py input_remote_checkpoint.yaml && cp output/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale_3iter/comm_groups.json "$TR/remote_checkpoint/" && cp output/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale_3iter/et/*.et "$TR/remote_checkpoint/et/"
py input_remote_async_checkpoint.yaml && cp output/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale_3iter/comm_groups.json "$TR/remote_async_checkpoint/" && cp output/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale_3iter/et/*.et "$TR/remote_async_checkpoint/et/"
echo "Traces generated."
