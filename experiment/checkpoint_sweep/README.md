# Checkpoint Size Sweep

Sweeps checkpoint size (`state_multiplier`) from 10 → 100 → 1000 → 10000, comparing **REMOTE_SYNC** vs **REMOTE_ASYNC** behavior as checkpoint transfer cost grows.

## Setup

- **MLSynth** – trace synthesis (repo root)
- **astra-sim** – with analytical congestion-aware binary
- **Docker** + `astra-sim:latest` image
- **chakra_env** – for MLSynth (optional, `python3` works)

## Run

From repo root:

```bash
cd /path/to/iso_code
python3 experiment/checkpoint_sweep/run_sweep.py
```

Or use the wrapper script:

```bash
./experiment/checkpoint_sweep/run.sh
```

Runtime: ~20–25 minutes (8 trace generations + 8 AstraSim runs).

## Outputs

All outputs are under `experiment/checkpoint_sweep/`:

| Path | Description |
|------|-------------|
| `traces/` | Generated ET traces per `(state_mult, mode)` |
| `results/checkpoint_sweep.csv` | Results for spreadsheets/plotting |
| `results/checkpoint_sweep.json` | Results for programmatic use |
| `results/checkpoint_sweep.md` | Summary table in Markdown |

### CSV format

```csv
state_multiplier,mode,wall_time_cycles,gpu_time_cycles,comm_time_cycles,overlap_cycles
10,REMOTE_SYNC,6008842093160,35360,6008842057800,0
10,REMOTE_ASYNC,6008844058568,2015360,6008844057800,2014592
...
```

### JSON format

```json
[
  {"state_multiplier": 10, "mode": "REMOTE_SYNC", "wall_time_cycles": ..., ...},
  {"state_multiplier": 10, "mode": "REMOTE_ASYNC", ...}
]
```

## Config

- **config/Switch.json** – AstraSim system config
- **config/network_8_remote.yml** – 8 NPUs, 10µs latency, 10 GB/s

Workload: 8dp×1pp×1tp, 20 iterations, transformer (64B, 2048S, 51200V, 20480d).
