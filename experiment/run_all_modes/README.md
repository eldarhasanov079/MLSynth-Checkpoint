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
