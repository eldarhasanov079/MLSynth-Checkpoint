# All 5 Checkpoint Modes

Compares BASE (no checkpoint) vs 4 checkpoint modes over 1–3 iterations.

| Mode | Description |
|------|-------------|
| BASE | No checkpoint |
| SYNC | Local disk write, stop-the-world |
| ASYNC | Local background write |
| REMOTE_SYNC | Remote upload via ring COMM, blocking |
| REMOTE_ASYNC | Remote upload, non-blocking (kickoff) |

**Run:** `./experiment/run_all_modes/run.sh` (from repo root; set `ASTRA_SIM_DIR`).  
**Prereq:** `./experiment/gen_traces.sh` first.
