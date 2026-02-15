#!/bin/bash
# Run remote sweep: 20 iter, checkpoint_every_n=5, Part 1 (scale=1) + Part 2 (scale=2).
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT"
python3 experiment/remote_sweep/run_remote_sweep.py
