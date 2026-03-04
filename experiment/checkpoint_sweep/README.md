# Checkpoint Size Sweep

Sweeps **BASE** (no checkpoint) and checkpoint modes **REMOTE_SYNC** vs **REMOTE_ASYNC** over `state_multiplier` (10, 100, 1000, 10000) and **bandwidth** (100, 50, 10, 1 GB/s). Uses `MLSynth/Wrapper/CheckpointWrapper.py` (`remote_sync` / `remote_async`).

## Setup

- **MLSynth** – trace synthesis (repo root)
- **astra-sim** – with analytical congestion-aware binary
- **Docker** + `astra-sim:latest` image
- **chakra_env** – for MLSynth (optional, `python3` works)

## Run

From repo root. **Trace generation needs the Chakra env; AstraSim needs Docker.**

Full sweep (regenerate traces + run AstraSim):

```bash
cd /path/to/iso_code
./chakra_env/bin/python experiment/checkpoint_sweep/run_sweep.py
```

Or activate the venv first: `source chakra_env/bin/activate` then `python experiment/checkpoint_sweep/run_sweep.py`.

**Docker must be running** or all AstraSim runs will fail (Wall/GPU/Comm will be empty). To re-run only AstraSim on existing traces (no trace regeneration): `./chakra_env/bin/python experiment/checkpoint_sweep/run_astrasim_again.py`.

Runtime: ~20–25 minutes (trace generations + AstraSim runs).

## Outputs

All outputs are under `experiment/checkpoint_sweep/`:

| Path | Description |
|------|-------------|
| **`results/CHECKPOINT_SWEEP_REPORT.md`** | **Full report:** implementation comparison, breakdown, tables, Wall formula, 34,592-cycle analysis |
| `results/figures/` | Plots: wall by strategy, % delta from BASE, sync vs async, GPU/Comm breakdown, heatmaps |
| `traces/` | Generated ET traces per `(state_mult, mode)` and `sweep_base` |
| `results/checkpoint_sweep.csv` | Results for spreadsheets/plotting |
| `results/checkpoint_sweep.json` | Results for programmatic use |
| `results/checkpoint_sweep.md` | Summary table in Markdown |

### CSV format

```csv
state_multiplier,bandwidth_gb_s,mode,wall_time_cycles,gpu_time_cycles,comm_time_cycles,overlap_cycles
,100,BASE,753056955760,15360,753056940400,0
10,100,REMOTE_SYNC,1207122667580,2035360,1207120632220,0
10,100,REMOTE_ASYNC,1207122632988,2015360,1207122632220,2014592
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
- **config/network_8_remote_bw{N}.yml** – 8 NPUs, 10 µs latency, bandwidth N GB/s (N = 100, 50, 10, 1)

Workload: 8dp×1pp×1tp, 20 iterations, transformer (64B, 2048S, 51200V, 20480d). At state_mult=10,000 and 1 GB/s the simulator can report unreleased nodes (no Wall/GPU/Comm).
