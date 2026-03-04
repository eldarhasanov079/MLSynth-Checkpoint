# Trace paths for Chakra visualizer

All paths are relative to repo root.

## ET traces (Chakra execution traces, one per NPU)

Use these with Chakra ET viewers or converters that read `.et` (protobuf) files.

### BASE (no checkpoint)
- Directory: `experiment/checkpoint_sweep/traces/sweep_base/et/`
- Workload base name: `transformer_8dp_1pp_1tp_64B_2048S_51200V_20480d_2b_100scale_20iter`
- Files: `transformer_8dp_1pp_1tp_64B_2048S_51200V_20480d_2b_100scale_20iter.0.et`, `transformer_8dp_1pp_1tp_64B_2048S_51200V_20480d_2b_100scale_20iter.1.et`, ... `transformer_8dp_1pp_1tp_64B_2048S_51200V_20480d_2b_100scale_20iter.7.et` (8 NPUs)
- Comm groups: `experiment/checkpoint_sweep/traces/sweep_base/comm_groups.json`

### REMOTE_SYNC / REMOTE_ASYNC (per state_multiplier)

- `experiment/checkpoint_sweep/traces/sweep_sm10_sync/et/` — mode=REMOTE_SYNC, state_mult=10
- `experiment/checkpoint_sweep/traces/sweep_sm10_async/et/` — mode=REMOTE_ASYNC, state_mult=10
- `experiment/checkpoint_sweep/traces/sweep_sm100_sync/et/` — mode=REMOTE_SYNC, state_mult=100
- `experiment/checkpoint_sweep/traces/sweep_sm100_async/et/` — mode=REMOTE_ASYNC, state_mult=100
- `experiment/checkpoint_sweep/traces/sweep_sm1000_sync/et/` — mode=REMOTE_SYNC, state_mult=1000
- `experiment/checkpoint_sweep/traces/sweep_sm1000_async/et/` — mode=REMOTE_ASYNC, state_mult=1000
- `experiment/checkpoint_sweep/traces/sweep_sm10000_sync/et/` — mode=REMOTE_SYNC, state_mult=10000
- `experiment/checkpoint_sweep/traces/sweep_sm10000_async/et/` — mode=REMOTE_ASYNC, state_mult=10000

Same workload base name and `.0.et` … `.7.et` pattern in each directory.

## Chakra visualizer commands (typical)

1. **ET → JSON (if your tool needs JSON):**
   - Chakra Python: load ET with `chakra` and export, or use `et_to_timeline_csv.py`-style pipeline.
2. **Chrome tracing JSON (from simulation timeline):**
   - Run AstraSim with trace enabled (Switch.json `trace-enabled`), then use
   - `experiment/run_all_modes/timeline_visualizer.py` with the issue/callback CSV to get Chrome tracing JSON.
3. **Direct ET paths (examples, from repo root):**
   - BASE: `experiment/checkpoint_sweep/traces/sweep_base/et/transformer_8dp_1pp_1tp_64B_2048S_51200V_20480d_2b_100scale_20iter.0.et` (and .1.et … .7.et)
   - REMOTE_SYNC sm=10: `experiment/checkpoint_sweep/traces/sweep_sm10_sync/et/transformer_8dp_1pp_1tp_64B_2048S_51200V_20480d_2b_100scale_20iter.0.et` (and .1–.7)
   - REMOTE_ASYNC sm=10: `experiment/checkpoint_sweep/traces/sweep_sm10_async/et/transformer_8dp_1pp_1tp_64B_2048S_51200V_20480d_2b_100scale_20iter.0.et` (and .1–.7)
