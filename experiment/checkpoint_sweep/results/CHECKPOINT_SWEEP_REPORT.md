# Checkpoint Sweep: Report and Deltas

**Experiment:** BASE (no checkpoint) vs REMOTE_SYNC vs REMOTE_ASYNC, sweeping **state_multiplier** (10, 100, 1000, 10000) and **bandwidth** (100, 50, 10, 1 GB/s).  
**Simulator:** AstraSim Analytical Congestion-Aware.  
**Workload:** 8 NPUs, 20 iterations, checkpoint every iteration.

---

## Breakdown of differences (executive summary)

| What differs | BASE | REMOTE_SYNC | REMOTE_ASYNC |
|--------------|------|-------------|--------------|
| **Checkpoint** | None | Every iteration (ring upload) | Every iteration (ring upload, overlapped) |
| **GPU time** | 15,360 | 2,035,360 | 2,015,360 |
| **Overlap** | 0 | 0 | 2,014,592 |
| **Wall formula** | GPU + Comm | GPU + Comm | GPU + Comm − Overlap |
| **Is Wall “real” time?** | Yes (no overlap) | Yes (no overlap) | Yes — Wall already has overlap subtracted |
| **vs BASE (wall)** | — | **+60% to +60,242%** (by sm/bw) | Same ballpark as SYNC |
| **SYNC vs ASYNC (wall)** | — | — | ASYNC **34,592 cycles** faster (constant) |

- **BASE → checkpoint (SYNC or ASYNC):** Adding checkpoint adds **~2M GPU cycles** (kickoff + optional sync_join) and **large comm** (upload size scales with state_mult, time with bandwidth). So **wall time is dominated by communication**; GPU is a tiny fraction. At 100 GB/s, wall goes from ~753×10⁹ (BASE) to ~1,207×10⁹ (sm=10); at 1 GB/s and sm=10,000, wall is orders of magnitude larger and the sim can fail.
- **SYNC vs ASYNC:** Same comm volume; SYNC has **20,000 more GPU cycles** (sync_join each iter) and **no overlap**. ASYNC has **2,014,592 cycles of overlap** and the simulator reports **2M more “Comm”** for ASYNC, so the net wall difference is **34,592** every time (20,000 + 14,592). So **async is only marginally faster** (≈0.003% or less of wall).

**Takeaway:** Checkpoint cost is almost entirely **communication**. REMOTE_ASYNC does not meaningfully reduce wall time vs REMOTE_SYNC in this setup; the constant 34,592-cycle gain is structural (trace DAG), not a function of state_mult or bandwidth.

### Key numbers at a glance (state_mult=10, 100 GB/s)

| Mode | Wall (×10⁹ cycles) | GPU (cycles) | Comm (×10⁹) | Overlap |
|------|--------------------|--------------|-------------|--------|
| BASE | 753.1 | 15,360 | 753.1 | 0 |
| REMOTE_SYNC | 1,207.12 | 2,035,360 | 1,207.12 | 0 |
| REMOTE_ASYNC | 1,207.12 (≈ SYNC − 34.6k) | 2,015,360 | 1,207.12 | 2,014,592 |

BASE wall ≈ 753×10⁹; adding checkpoint (SYNC) → wall ≈ 1,207×10⁹ (**+60.2%**). ASYNC is **34,592 cycles** lower than SYNC (same for every valid (sm, bw)).

---

## Figures

| Figure | Description |
|--------|-------------|
| [wall_by_strategy.png](figures/wall_by_strategy.png) | Wall time (×10⁹ cycles) by strategy and bandwidth; one panel per state_multiplier. |
| [pct_delta_from_base.png](figures/pct_delta_from_base.png) | % increase in wall time vs BASE for REMOTE_SYNC and REMOTE_ASYNC. |
| [sync_vs_async.png](figures/sync_vs_async.png) | Wall time difference (ASYNC − SYNC) in cycles; negative = async faster. |
| [gpu_comm_breakdown.png](figures/gpu_comm_breakdown.png) | GPU vs Comm contribution to wall (sm=10, 100 GB/s) for BASE, SYNC, ASYNC. |
| [heatmap_overhead_remote_sync.png](figures/heatmap_overhead_remote_sync.png) | Heatmap: % wall increase vs BASE for REMOTE_SYNC (state_mult × bandwidth). |
| [heatmap_overhead_remote_async.png](figures/heatmap_overhead_remote_async.png) | Heatmap: % wall increase vs BASE for REMOTE_ASYNC. |

*To regenerate figures:* from repo root, `./chakra_env/bin/python experiment/checkpoint_sweep/plot_results.py` (or `python3` with matplotlib installed).

---

## 1. BASE (no checkpoint) — baseline

Wall time and comm time are identical; GPU time is small and constant.

| Bandwidth | Wall (×10⁹ cycles) | GPU (cycles) | Comm (×10⁹ cycles) |
|-----------|---------------------|--------------|----------------------|
| 100 GB/s  | 753.1               | 15,360       | 753.1                |
| 50 GB/s   | 832.5               | 15,360       | 832.5                |
| 10 GB/s   | 1,468.2             | 15,360       | 1,468.2              |
| 1 GB/s    | 8,619.7             | 15,360       | 8,619.7              |

---

## 2. REMOTE_SYNC vs BASE — % delta (wall time)

**Δ% = (REMOTE_SYNC − BASE) / BASE × 100.** Positive = checkpoint adds that much wall time.

| state_mult | 100 GB/s | 50 GB/s | 10 GB/s | 1 GB/s   |
|------------|----------|---------|---------|----------|
| 10         | +60.2%   | +109.2% | +309.5% | +527.4%  |
| 100        | +602.4%  | +1,091% | +3,092% | +5,268%  |
| 1,000      | +6,024%  | +10,906%| +30,922%| +52,676% |
| 10,000     | +60,242% | +109,062%| +309,224%| *(sim failed)* |

---

## 3. REMOTE_ASYNC vs BASE — % delta (wall time)

**Δ% = (REMOTE_ASYNC − BASE) / BASE × 100.** REMOTE_ASYNC is almost the same as REMOTE_SYNC (no meaningful wall-time benefit).

| state_mult | 100 GB/s | 50 GB/s | 10 GB/s | 1 GB/s   |
|------------|----------|---------|---------|----------|
| 10         | +60.2%   | +109.2% | +309.5% | +527.4%  |
| 100        | +602.4%  | +1,091% | +3,092% | +5,268%  |
| 1,000      | +6,024%  | +10,906%| +30,922%| +52,676% |
| 10,000     | +60,242% | +109,062%| +309,224%| *(sim failed)* |

---

## 4. Sync vs Async — small differences

**Δ Wall = REMOTE_ASYNC wall − REMOTE_SYNC wall** (negative ⇒ async faster).  
**Δ GPU = REMOTE_ASYNC GPU − REMOTE_SYNC GPU.**  
**Overlap:** REMOTE_ASYNC has 2,014,592 cycles; REMOTE_SYNC has 0.

| state_mult | bw (GB/s) | Δ Wall (cycles) | Δ Wall (% of sync) | Δ GPU (cycles) |
|------------|-----------|------------------|---------------------|----------------|
| 10         | 100       | −34,592          | −0.0029%            | −20,000        |
| 10         | 50        | −34,592          | −0.0020%            | −20,000        |
| 10         | 10        | −34,592          | −0.00058%           | −20,000        |
| 10         | 1         | −34,592          | −0.000064%          | −20,000        |
| 100        | 100       | −34,592          | −0.00065%           | −20,000        |
| 100        | 50        | −34,592          | −0.00035%           | −20,000        |
| 100        | 10        | −34,592          | −0.000074%          | −20,000        |
| 100        | 1         | −34,592          | −0.0000075%         | −20,000        |
| 1,000      | 100       | −34,592          | −0.000075%          | −20,000        |
| 1,000      | 50        | −34,592          | −0.000038%          | −20,000        |
| 1,000      | 10        | −34,592          | −0.0000076%         | −20,000        |
| 1,000      | 1         | −34,592          | −0.00000076%        | −20,000        |
| 10,000     | 100       | −34,592          | −0.0000076%         | −20,000        |
| 10,000     | 50        | −34,592          | −0.0000038%         | −20,000        |
| 10,000     | 10        | −34,592          | −0.00000076%        | −20,000        |
| 10,000     | 1         | *(both failed)*   | —                   | —              |

- **Comm time** is identical for SYNC and ASYNC at every (state_mult, bandwidth).
- Async is consistently **34,592 cycles** faster in wall time and **20,000 cycles** lower in GPU time; the relative gain shrinks as checkpoint size or comm grows.

---

## 5. Summary

| Comparison | Main result |
|------------|-------------|
| **BASE vs checkpoint** | Adding checkpoint (SYNC or ASYNC) increases wall time by **+60% to +309,224%** vs BASE, depending on state_mult and bandwidth. |
| **REMOTE_SYNC vs REMOTE_ASYNC** | Wall time and comm time are effectively the same; async is **34,592 cycles** (≈0.003% or less) faster. |
| **Bandwidth** | Lower bandwidth (1 vs 100 GB/s) multiplies wall time for both BASE and checkpoint runs. |
| **state_multiplier** | Larger checkpoint size (higher state_mult) multiplies wall time; at 10,000 × 1 GB/s the simulator fails (unreleased nodes). |

**Takeaway:** Checkpoint overhead is dominated by communication. REMOTE_ASYNC does not materially reduce wall time vs REMOTE_SYNC in this regime; overlap is small relative to total comm.

---

## 6. Deep investigation: why is Δ Wall exactly 34,592 cycles?

**Observed:** For every (state_mult, bandwidth) where both REMOTE_SYNC and REMOTE_ASYNC complete, **Wall_sync − Wall_async = 34,592 cycles**. That number does not depend on checkpoint size or network speed.

### How AstraSim defines wall time

AstraSim reports (and we parse) **Wall**, **GPU**, **Comm**, and **Total compute–communication overlap**. The relationship is:

- **Wall = GPU + Comm − Overlap**

So the **reported Wall is already the effective (real) elapsed time**: overlap is already subtracted. When overlap is 0 (BASE, REMOTE_SYNC), Wall = GPU + Comm; when overlap > 0 (REMOTE_ASYNC), Wall = GPU + Comm − Overlap. You do **not** need to compute “real time” as Wall − Overlap; that would double-count. Wall *is* real time.

### Fixed numbers from the traces

From `checkpoint_sweep.json` (same for every completed (state_mult, bandwidth)):

| Quantity | REMOTE_SYNC | REMOTE_ASYNC |
|----------|-------------|--------------|
| GPU (cycles) | 2,035,360 | 2,015,360 |
| Overlap (cycles) | 0 | 2,014,592 |
| Comm (cycles) | *C* (varies by config) | *C* + 2,000,000 |

So:

- **Δ GPU = GPU_sync − GPU_async = 20,000** (sync has 20k more GPU cycles).
- **Comm_async = Comm_sync + 2,000,000** in every config (simulator reports 2M more “Comm” for async).
- **Overlap** is 2,014,592 for async and 0 for sync.

### Derivation of 34,592

Using Wall = GPU + Comm − Overlap:

- Wall_sync = 2,035,360 + *C*
- Wall_async = 2,015,360 + (*C* + 2,000,000) − 2,014,592 = *C* + 768

So:

- **Wall_sync − Wall_async = (2,035,360 + *C*) − (*C* + 768) = 2,034,592**

That would be the difference if Comm were the same for both. But the simulator reports Comm_async = *C* + 2,000,000, so when we substitute the *reported* Comm values we get:

- Wall_sync − Wall_async = 2,035,360 + *C* − (2,015,360 + (*C* + 2,000,000) − 2,014,592)  
  = 2,035,360 − 2,015,360 − 2,000,000 + 2,014,592  
  = **20,000 + 2,014,592 − 2,000,000 = 34,592**

So:

- **34,592 = (GPU_sync − GPU_async) + Overlap − (Comm_async − Comm_sync)**  
- **34,592 = 20,000 + 14,592**

The **20,000** is the extra GPU cycles in sync. The **14,592** is the part of Overlap that is *not* offset by the extra 2,000,000 cycles that the simulator adds to Comm for async (2,014,592 − 2,000,000 = 14,592).

### Where 20,000 and 2,014,592 come from in the trace

- **BASE** GPU time is **15,360** cycles (training only, no checkpoint).
- **REMOTE_ASYNC** adds 20 iterations of a **kickoff** node: `duration_micros = 100` (from `kickoff_cost_micros` in the wrapper). At 1 GHz, 100 µs = 100,000 cycles per iteration ⇒ 20 × 100,000 = **2,000,000** cycles. So GPU_async = 15,360 + 2,000,000 = **2,015,360**.
- **REMOTE_SYNC** has the same kickoff plus a **sync_join** node per iteration: `duration_micros = 1` (flops=1, tensor_size=1). At 1 GHz, 1 µs = 1,000 cycles per iteration ⇒ 20 × 1,000 = **20,000** cycles. So GPU_sync = 2,015,360 + 20,000 = **2,035,360**.

So the **20,000** is exactly the cost of 20 × sync_join (1 µs each) in the sync trace.

- In async, almost all of that compute overlaps with the upload: the simulator reports **Overlap = 2,014,592**. That is 2,000,000 (kickoff) plus 14,592. The base training compute is 15,360; 15,360 − 768 = **14,592**, and the “exposed” compute in async is 768 (so Wall_async = *C* + 768). So 2,014,592 = 2,000,000 (kickoff) + 14,592 (part of base that overlaps).

### Why the reported Comm is 2,000,000 higher for async

The simulator reports **Comm_async = Comm_sync + 2,000,000** in every config. So the same 2,000,000 cycles (the kickoff compute) appear in the “Comm” bucket for async—e.g. because when compute and comm overlap, AstraSim may count the overlapped compute as part of “Comm” or the timeline aggregation assigns that duration to comm. So in the formula Wall = GPU + Comm − Overlap, the 2M in Comm_async and the 2M inside Overlap largely cancel; what remains is the extra 14,592 (Overlap − 2M) plus the 20,000 (extra GPU in sync) ⇒ **34,592**.

### Why it is constant

- **GPU_sync**, **GPU_async**, and **Overlap** are fixed by the *trace structure*: same number of iterations (20), same nodes (kickoff, sync_join vs kickoff only), same durations (100 µs kickoff, 1 µs sync_join). So they do not depend on state_mult or bandwidth.
- **Comm_async − Comm_sync = 2,000,000** in every config. So the way the simulator attributes the overlapped 2M to “Comm” for async is also fixed.
- Therefore **Wall_sync − Wall_async = 34,592** for every (state_mult, bandwidth) where both runs complete.

**Summary:** The constant 34,592 is **20,000** (extra GPU in sync from 20 × 1 µs sync_join) **+ 14,592** (Overlap − 2,000,000). It is constant because the DAG and node durations are fixed and the simulator’s reporting of Comm for async (Comm_sync + 2M) is fixed across all sweep points.

---

## Raw data

- **JSON:** [checkpoint_sweep.json](checkpoint_sweep.json)  
- **CSV:** [checkpoint_sweep.csv](checkpoint_sweep.csv)  
- **Flat table:** [checkpoint_sweep.md](checkpoint_sweep.md)
