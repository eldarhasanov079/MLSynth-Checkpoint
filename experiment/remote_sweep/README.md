# Remote Sweep: Async Benefit + Interference

Sweeps `state_multiplier` (0.01, 0.1, 0.5, 1.0, 3.0) for remote checkpoint modes at 20 iterations, checkpointing every 5. Compares BASE, REMOTE_SYNC, and REMOTE_ASYNC. Part 1 (scale=1) shows checkpoint overhead with minimal compute slack; Part 2 (scale=2) doubles compute per iteration to observe when upload can hide under compute.

| Part | scale | Purpose |
|------|-------|---------|
| 1 | 1 | Frequency separation; ckpt overhead visible |
| 2 | 2 | Compute slack; ckpt may overlap with compute |

**Run:** `./experiment/remote_sweep/run.sh` (from repo root; needs Docker, Chakra/Python).
