# Remote Sweep: Async Benefit + Interference

20 iter, checkpoint_every_n=5, state_mult ∈ {0.01, 0.1, 0.5, 1.0, 3.0}.  
Compares BASE, REMOTE_SYNC, REMOTE_ASYNC.

| Part | scale | Purpose |
|------|-------|---------|
| 1 | 1 | Frequency separation |
| 2 | 2 | Compute slack |

**Run:** `./experiment/remote_sweep/run.sh` (from repo root; needs Docker, Chakra/Python).
