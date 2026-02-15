# Results

Times in cycles. B = billion (10⁹).

| Trace | Iters | Wall (B) | Comm (B) | GPU |
|-------|-------|----------|----------|-----|
| BASE | 1 | 10.81 | 10.81 | 384 |
| SYNC | 1 | 11.81 | 10.81 | 1.00B |
| ASYNC | 3 | 35.42 | 34.42 | 3.00B |
| REMOTE_SYNC | 3 | 42.64 | 42.64 | 4.2K |
| REMOTE_ASYNC | 3 | 42.64 | 42.64 | 301K |
