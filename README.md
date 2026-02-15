# MLSynth + Checkpointing

MLSynth extended with **CheckpointWrapper** for modelling checkpoint save overhead in ET traces.

## Structure

| Path | Description |
|------|-------------|
| [MLSynth/](MLSynth/) | Modified MLSynth (trace synthesis) |
| [MLSynth/Wrapper/](MLSynth/Wrapper/) | [CheckpointWrapper](MLSynth/Wrapper/README.md) and config |
| [experiment/](experiment/) | [Experiments](experiment/README.md) and ASTRA-sim configs |

## Setup

1. **Chakra** — [docs](https://github.com/astra-sim/chakra). Python package for ET schema; required for MLSynth synthesis.
2. **ASTRA-sim** — [docs](https://astrasim.org). Build analytical (Congestion Aware) backend.
3. **Variables:**
   - `ASTRA_SIM_DIR` — path to ASTRA-sim clone (e.g. `../astra-sim`)
   - Binary: `$ASTRA_SIM_DIR/build/astra_analytical/build/bin/AstraSim_Analytical_Congestion_Aware`
   - For `remote_sweep`: Docker image `astra-sim:latest` (see ASTRA-sim for build)

## Experiments

| Experiment | Run | Description |
|------------|-----|-------------|
| [run_all_modes](experiment/run_all_modes/) | `./experiment/run_all_modes/run.sh` | BASE, SYNC, ASYNC, REMOTE_SYNC, REMOTE_ASYNC |
| [remote_sweep](experiment/remote_sweep/) | `./experiment/remote_sweep/run.sh` | Sweep state_mult; scale=1 and scale=2 |

Generate traces first: `./experiment/gen_traces.sh` (for run_all_modes).
