# CheckpointWrapper

Injects checkpoint save overhead into ET traces at end-of-iteration boundaries.

## Modes

| Mode | Behavior |
|------|----------|
| `sync` | Local disk write (COMP_NODE), stop-the-world |
| `async` | Local background write (KICKOFF + WRITE_BG), optional drain |
| `remote_sync` | KICKOFF (blocking) then ring COMM; boundary = SYNC_JOIN (wait for send+recv). Same kickoff cost as remote_async. |
| `remote_async` | KICKOFF (non-blocking boundary) then COMM in background, shares NIC |

## Config (under `wrapper:`)

| Option | Default | Description |
|--------|---------|-------------|
| `type` | — | Must be `"checkpoint"` |
| `mode` | `sync` | One of: sync, async, remote_sync, remote_async |
| `checkpoint_every_n` | 1 | Checkpoint every N iterations |
| `state_multiplier` | 3.0 | Model (1×) + optimizer (2×) + overhead |
| `overhead_multiplier` | 1.0 | Scales flops/bytes for checkpoint node |
| `kickoff_cost_micros` | 100 | Async kickoff duration |
| `drain_when_backpressure` | false | Block next ckpt until prior write completes |
| `use_storage_sink` | false | remote_async: send to storage endpoint (num_npus) vs ring |

## Example

```yaml
wrapper:
  type: checkpoint
  mode: remote_async
  checkpoint_every_n: 5
  state_multiplier: 0.5
```
