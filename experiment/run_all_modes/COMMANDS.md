# Timeline Visualization Commands

Compare execution traces for **base**, **sync_checkpoint**, and **remote_checkpoint**.

---

## Option A: From traces only (no ASTRA-sim)

Simulate directly from ET files — works on any platform. **base** has no checkpoint nodes.

**Preprocess** (requires Chakra: `source chakra_env/bin/activate` or similar):

```bash
python3 experiment/run_all_modes/et_to_timeline_csv.py \
  -w experiment/traces/base/et/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale \
  -o experiment/run_all_modes/timeline_csv/base.csv -n 4

python3 experiment/run_all_modes/et_to_timeline_csv.py \
  -w experiment/traces/sync_checkpoint/et/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale \
  -o experiment/run_all_modes/timeline_csv/sync_checkpoint.csv -n 4

python3 experiment/run_all_modes/et_to_timeline_csv.py \
  -w experiment/traces/remote_checkpoint/et/transformer_2dp_2pp_1tp_32B_2048S_51200V_20480d_2b_100scale_3iter \
  -o experiment/run_all_modes/timeline_csv/remote_checkpoint.csv -n 4
```

Then run **Step 3** (visualize) below.

---

## Option B: From ASTRA-sim logs

**Prerequisites:** Traces from `./experiment/gen_traces.sh`

### Step 1: Capture logs

Run ASTRA-sim for each mode and save output to logs:

```bash
./experiment/run_all_modes/run_capture_logs.sh
```

Produces:
- `experiment/run_all_modes/timeline_logs/base.log`
- `experiment/run_all_modes/timeline_logs/sync_checkpoint.log`
- `experiment/run_all_modes/timeline_logs/remote_checkpoint.log`

Uses native binary if available; falls back to Docker (`astra-sim:latest`) when binary cannot execute.

---

### Step 2: Preprocess (extract CSV from logs)

Extract issue/callback events to CSV format:

```bash
# Base (no checkpoint)
python3 experiment/run_all_modes/extract_trace_csv.py \
  experiment/run_all_modes/timeline_logs/base.log \
  experiment/run_all_modes/timeline_csv/base.csv

# Sync checkpoint (local disk, stop-the-world)
python3 experiment/run_all_modes/extract_trace_csv.py \
  experiment/run_all_modes/timeline_logs/sync_checkpoint.log \
  experiment/run_all_modes/timeline_csv/sync_checkpoint.csv

# Remote checkpoint (remote upload, blocking)
python3 experiment/run_all_modes/extract_trace_csv.py \
  experiment/run_all_modes/timeline_logs/remote_checkpoint.log \
  experiment/run_all_modes/timeline_csv/remote_checkpoint.csv
```

---

## Step 3: Visualize (generate Chrome tracing JSON)

```bash
# Base
python3 experiment/run_all_modes/timeline_visualizer.py \
  --input_filename experiment/run_all_modes/timeline_csv/base.csv \
  --output_filename experiment/run_all_modes/timeline_json/base.json \
  --num_npus 4 \
  --npu_frequency 1500

# Sync checkpoint
python3 experiment/run_all_modes/timeline_visualizer.py \
  --input_filename experiment/run_all_modes/timeline_csv/sync_checkpoint.csv \
  --output_filename experiment/run_all_modes/timeline_json/sync_checkpoint.json \
  --num_npus 4 \
  --npu_frequency 1500

# Remote checkpoint
python3 experiment/run_all_modes/timeline_visualizer.py \
  --input_filename experiment/run_all_modes/timeline_csv/remote_checkpoint.csv \
  --output_filename experiment/run_all_modes/timeline_json/remote_checkpoint.json \
  --num_npus 4 \
  --npu_frequency 1500
```

---

## Step 4: View in Chrome

Open `chrome://tracing` and load each JSON:
- `experiment/run_all_modes/timeline_json/base.json`
- `experiment/run_all_modes/timeline_json/sync_checkpoint.json`
- `experiment/run_all_modes/timeline_json/remote_checkpoint.json`

---

## Important: base must use base workload log

**base.json** must be generated from a log captured when simulating the **base** workload (`traces/base/...`). The base config (`input_base.yaml`) has no checkpoint wrapper — no `CHECKPOINT_*` nodes.

Do **not** use `log/log.log` for base if it contains `CHECKPOINT_REMOTE_ASYNC` or similar — that log is from a checkpoint workload run.
