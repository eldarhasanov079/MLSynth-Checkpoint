#!/usr/bin/env bash

# Simple wrapper to run the ASTRA-sim ns-3 backend with the example configuration
# from the official documentation. This is meant as a sanity check that your
# ns-3 build works; we will hook this folder into checkpoint_sweep traces later.

set -euo pipefail

if [[ -z "${ASTRA_SIM_DIR:-}" ]]; then
  echo "ERROR: Please set ASTRA_SIM_DIR to your ASTRA-sim clone."
  echo "Example: export ASTRA_SIM_DIR=\$HOME/src/astra-sim"
  exit 1
fi

NS3_DIR="${ASTRA_SIM_DIR}/extern/network_backend/ns-3"
SCRIPT_DIR="${ASTRA_SIM_DIR}"

if [[ ! -d "${NS3_DIR}" ]]; then
  echo "ERROR: ns-3 backend directory not found at:"
  echo "  ${NS3_DIR}"
  echo "Make sure you have the ns-3 backend checked out inside ASTRA-sim."
  exit 1
fi

if [[ ! -x "${NS3_DIR}/build/scratch/ns3.42-AstraSimNetwork-default" ]]; then
  echo "ERROR: ns3.42-AstraSimNetwork-default binary not found or not executable at:"
  echo "  ${NS3_DIR}/build/scratch/ns3.42-AstraSimNetwork-default"
  echo "You likely still need to build the ns-3 backend, e.g.:"
  echo "  cd \"${ASTRA_SIM_DIR}\""
  echo "  bash build/astra_ns3/build.sh"
  exit 1
fi

cd "${NS3_DIR}/build/scratch"

./ns3.42-AstraSimNetwork-default \
  --workload-configuration="${SCRIPT_DIR}/extern/graph_frontend/chakra/one_comm_coll_node_allgather" \
  --system-configuration="${SCRIPT_DIR}/inputs/system/Switch.json" \
  --network-configuration="../../../ns-3/scratch/config/config.txt" \
  --remote-memory-configuration="${SCRIPT_DIR}/inputs/remote_memory/analytical/no_memory_expansion.json" \
  --logical-topology-configuration="${SCRIPT_DIR}/inputs/network/ns3/sample_8nodes_1D.json" \
  --comm-group-configuration="empty"

