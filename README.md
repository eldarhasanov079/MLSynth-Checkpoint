# MLSynth + Checkpointing

[MLSynth](https://github.com/NVIDIA/MLSynth) extended with **CheckpointWrapper** to model checkpoint save overhead in ET (Execution Trace) workloads. Produces Chakra ET traces for simulation in [ASTRA-sim](https://astrasim.org), enabling comparison of sync/async and local/remote checkpoint strategies.

## Structure

| Path | Description |
|------|-------------|
| [MLSynth/](MLSynth/) | Modified MLSynth (trace synthesis) |
| [MLSynth/Wrapper/](MLSynth/Wrapper/) | [CheckpointWrapper](MLSynth/Wrapper/README.md) and config |
| [experiment/](experiment/) | [Experiments](experiment/README.md) and ASTRA-sim configs |

## Setup

1. **param** — [param](https://github.com/astra-sim/param). Dependency for MLSynth trace format.
2. **HolisticTraceAnalysis** — [HolisticTraceAnalysis](https://github.com/astra-sim/HolisticTraceAnalysis). Provides Chakra/ET tooling used by MLSynth.
3. **Chakra** — [docs](https://github.com/astra-sim/chakra). Python package for ET schema; required for MLSynth synthesis.
4. **ASTRA-sim** — [docs](https://astrasim.org). Build analytical (Congestion Aware) backend.
5. **Variables**
   - `ASTRA_SIM_DIR` — path to ASTRA-sim clone (e.g. `../astra-sim`)
   - Binary: `$ASTRA_SIM_DIR/build/astra_analytical/build/bin/AstraSim_Analytical_Congestion_Aware`
   - For `remote_sweep`: Docker image `astra-sim:latest` (see ASTRA-sim for build)

## Experiments

| Experiment | Run | Description |
|------------|-----|-------------|
| [run_all_modes](experiment/run_all_modes/) | `./experiment/run_all_modes/run.sh` | Runs ASTRA-sim on all 5 checkpoint modes (BASE, SYNC, ASYNC, REMOTE_SYNC, REMOTE_ASYNC) with identical workload; compares wall/comm time. |
| [remote_sweep](experiment/remote_sweep/) | `./experiment/remote_sweep/run.sh` | Sweeps `state_multiplier` (0.01–3.0) for REMOTE_SYNC vs REMOTE_ASYNC; Part 1 (scale=1) and Part 2 (scale=2) show frequency vs compute-slack effects. |

Generate traces first: `./experiment/gen_traces.sh` (for run_all_modes).
