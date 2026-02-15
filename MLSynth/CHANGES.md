# MLSynth Checkpoint Wrapper – Change Log

## Overview

This document records changes made to add **local synchronous checkpointing overhead modelling** to MLSynth. The implementation follows the design: pause at iteration boundary, save state to local disk, wait for write completion, then resume.

---

## New Files

### `Wrapper/CheckpointWrapper.py`

- **Purpose**: Wrapper that injects checkpoint save overhead nodes at end-of-iteration boundaries.
- **Behavior**:
  - Passes through `fwd()` and `bckwd()` without modification (no per-layer changes).
  - Implements `get_checkpoint_nodes(npu_id, parents, iteration)` for the orchestrator to call at iteration end.
  - Models overhead as a `COMP_NODE` with:
    - `tensor_size` = bytes written (model + optimizer + step/RNG state per rank)
    - `num_ops` = 0 (I/O-bound; simulators interpret `tensor_size` for write latency).
- **Config** (under `wrapper:`):
  - `type: "checkpoint"` – enables this wrapper.
  - `checkpoint_every_n` (default: 1) – checkpoint every N iterations.
  - `state_multiplier` (default: 3.0) – 1× model + 2× optimizer (e.g. Adam) + overhead.

- **ASTRA-sim compatibility**: Checkpoint node uses `num_ops = bytes_to_write` (not 0). With ASTRA-sim roofline enabled, `num_ops=0` causes perf=0 and division-by-zero in elapsed_time; using bytes avoids this.

### `input_checkpoint.yaml`

- Example config that uses the checkpoint wrapper instead of the compute wrapper.

---

## Modified Files

### `Orchestrator/MegatronLM.py`

- **ASTRA-sim compatibility**: Comm groups and `pg_name` use numeric IDs (e.g. `"0"`, `"1"`) instead of semantic names (`"pp_0"`, `"pp_1"`), because ASTRA-sim parses them with `std::stoi`.
- **End-of-iteration checkpoint injection** (around lines 143–154):
  - After the iteration (after DP allreduce if `dp_size > 1`, otherwise after the last backward op).
  - If the model has `get_checkpoint_nodes`, calls it and appends the returned nodes with correct dependencies.
  - `prev_comp` is updated to `dp_comm_node` when DP allreduce is present so checkpoint nodes depend on the last collective.

### `synthesise_workload.py`

- **Checkpoint wrapper support**:
  - Imports `CheckpointWrapper`.
  - Dispatches based on `wrapper.type`: `"compute"` → `ComputeWrapper`, `"checkpoint"` → `CheckpointWrapper`.
  - Raises on unknown `wrapper.type`.

---

## Output Verification

- **Checkpoint config** (`input_checkpoint.yaml`): Each NPU trace ends with a `COMP_NODE_CHECKPOINT_SAVE_iter0_npu{N}` node.
- **Compute config** (`input.yaml`): No checkpoint nodes; compute slowdown behavior is unchanged.

---

## Design Notes

- **Sync boundary**: Checkpoint is placed after the DP allreduce, so all ranks are synchronized before the write.
- **Local storage**: Each rank writes its own shard; no cross-rank communication for checkpointing.
- **State size**: `bytes_to_write = (num_params / tp_size / pp_size) * bytes_per_val * state_multiplier * scale`.
- **Simulator semantics**: The checkpoint node is a `COMP_NODE` with `num_ops=0`, `tensor_size` = bytes. Simulators should treat this as I/O-bound (e.g. time = bytes / bandwidth).
