# All 5 Checkpoint Modes

Runs ASTRA-sim on the same transformer workload (2DP, 2PP, 1TP) with five trace variants: one baseline and four checkpoint modes. Each mode injects different checkpoint overhead (local sync/async, remote sync/async) into the ET trace; the experiment compares wall and comm time across modes.

| Mode | Description |
|------|-------------|
| BASE | No checkpoint; baseline |
| SYNC | Local disk write, stop-the-world |
| ASYNC | Local background write (kickoff, overlap) |
| REMOTE_SYNC | Remote upload via ring COMM, blocking |
| REMOTE_ASYNC | Remote upload, non-blocking (kickoff) |

**Run:** `./experiment/run_all_modes/run.sh` (from repo root; set `ASTRA_SIM_DIR`).  
**Prereq:** `./experiment/gen_traces.sh` first.

---

## Timeline Visualization

Compare execution traces for **base**, **sync_checkpoint**, and **remote_checkpoint** in [Chrome Tracing](chrome://tracing).

See **[COMMANDS.md](COMMANDS.md)** for step-by-step commands.

### Quick overview

1. **Capture logs** — Run ASTRA-sim per mode: `./experiment/run_all_modes/run_capture_logs.sh`
2. **Preprocess** — Extract CSV: `python3 experiment/run_all_modes/extract_trace_csv.py <log> <csv>`
3. **Visualize** — Generate JSON: `python3 experiment/run_all_modes/timeline_visualizer.py ...`
4. **View** — Load JSON in `chrome://tracing`

### Important: base must be from base workload

**base** uses `input_base.yaml` (no checkpoint wrapper). Base traces must **not** contain `CHECKPOINT_*` nodes. Ensure the log comes from simulating `traces/base/...` — do not use a log from a checkpoint workload run.
