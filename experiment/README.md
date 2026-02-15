# Experiments

| Experiment | Description |
|------------|-------------|
| [run_all_modes](run_all_modes/) | Compare 5 modes: BASE, SYNC, ASYNC, REMOTE_SYNC, REMOTE_ASYNC |
| [remote_sweep](remote_sweep/) | 20 iter, ckpt every 5, sweep state_mult; Part 1 (scale=1) + Part 2 (scale=2) |

## Setup

1. **ASTRA-sim:** [astrasim.org](https://astrasim.org) — build analytical (Congestion Aware) backend.
2. **Chakra:** see ASTRA-sim docs — submodule for ET format.
3. Set `ASTRA_SIM_DIR` to your ASTRA-sim clone (e.g. `../astra-sim`). The binary is expected at:
   `$ASTRA_SIM_DIR/build/astra_analytical/build/bin/AstraSim_Analytical_Congestion_Aware`

## Trace generation (run_all_modes)

```bash
./experiment/gen_traces.sh
```
