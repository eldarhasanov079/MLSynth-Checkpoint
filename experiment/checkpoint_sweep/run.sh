#!/bin/bash
# Run checkpoint size sweep. Execute from repo root.
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
python3 experiment/checkpoint_sweep/run_sweep.py
