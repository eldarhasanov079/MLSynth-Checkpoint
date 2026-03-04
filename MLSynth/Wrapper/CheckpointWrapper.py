"""
Checkpointing wrapper with four modes:
  sync:        Local disk write (COMP_NODE), stop-the-world.
  async:       Local background write (KICKOFF + WRITE_BG), optional drain.
  remote_sync: KICKOFF (blocking) then ring COMM; boundary = sync_join (wait for send+recv).
  remote_async: KICKOFF (non-blocking boundary) then COMM in background, shares NIC.
"""

from typing import List, Optional, Tuple
from Wrapper.Wrapper import Wrapper
from utils import compute, send, receive
from chakra.schema.protobuf.et_def_pb2 import Node as ChakraNode


class CheckpointWrapper(Wrapper):
    """
    Wrapper that injects checkpoint save overhead nodes at end-of-iteration boundaries.

    Uses a COMP_NODE to model the synchronous write: tensor_size = bytes written,
    num_ops = 0 (I/O-bound). Simulators interpret this as local storage write latency.
    """

    def __init__(self, model, config: dict):
        self.model = model
        self.num_params = model.num_params
        self.config = config
        wc = config.get("wrapper", {})
        self.checkpoint_every_n = int(wc.get("checkpoint_every_n", 1))
        self.state_multiplier = float(wc.get("state_multiplier", 3.0))
        self.overhead_multiplier = float(wc.get("overhead_multiplier", 1.0))
        self.mode = str(wc.get("mode", "sync")).lower()
        self.kickoff_cost_micros = int(wc.get("kickoff_cost_micros", 100))
        self.drain_when_backpressure = bool(wc.get("drain_when_backpressure", False))
        self.use_storage_sink = bool(wc.get("use_storage_sink", False))
        self.tp_size = config["parallelism"]["tp_size"]
        self.pp_size = config["parallelism"]["pp_size"]
        self.dp_size = config["parallelism"]["dp_size"]
        self.num_npus = self.dp_size * self.pp_size * self.tp_size
        self.scale = float(config["model"].get("scale", 1.0))

    def fwd(self, name: str, npu_id: int, layer: int, num_batches: int, pg_name: Optional[str] = None) -> List[ChakraNode]:
        return self.model.fwd(name, npu_id, layer, num_batches, pg_name)

    def bckwd(self, name: str, npu_id: int, layer: int, num_batches: int, pg_name: Optional[str] = None) -> List[ChakraNode]:
        return self.model.bckwd(name, npu_id, layer, num_batches, pg_name)

    def get_checkpoint_nodes(
        self,
        npu_id: int,
        parents: List[Optional[ChakraNode]],
        iteration: int = 0,
        prev_write_bg: Optional[ChakraNode] = None,
    ) -> Tuple[List[ChakraNode], Optional[ChakraNode]]:
        """
        Return (nodes_to_append, bg_node_or_none).

        CRITICAL for async modes: nodes[0] must be the BOUNDARY (kickoff or drain).
        The orchestrator uses nodes[0] as prev_comp for the next iteration.
        bg_node (write_bg / upload_send) must exist in the trace but must NOT be nodes[0];
        training's next-iter first nodes must not depend on bg_node completion.
        """
        if iteration % self.checkpoint_every_n != 0:
            return [], prev_write_bg

        valid_parents = [p for p in parents if p]
        if not valid_parents:
            return [], prev_write_bg

        num_params = self.model.num_params
        bytes_per_val = self.model.get_bytes_per_val()
        params_per_rank = num_params / (self.tp_size * self.pp_size)
        bytes_to_write = int(params_per_rank * bytes_per_val * self.state_multiplier * self.scale)
        bytes_to_write = max(bytes_to_write, 1)
        cost = int(bytes_to_write * self.overhead_multiplier)
        duration_micros = int(100 * self.overhead_multiplier)

        if self.mode == "sync":
            node = compute(
                flops=cost,
                tensor_size=cost,
                parents=valid_parents,
                name=f"COMP_NODE_CHECKPOINT_SAVE_iter{iteration}_npu{npu_id}",
                duration_micros=duration_micros,
            )
            return [node], None

        if self.mode == "remote_sync":
            # Blocking kickoff (same cost model as remote_async, slightly smaller cap), then ring COMM.
            # Boundary = sync_join so next iteration waits for full upload (no finalize node).
            kickoff_cap = min(cost, int(5e5))  # Slightly smaller than async 1e6
            kickoff = compute(
                flops=kickoff_cap,
                tensor_size=kickoff_cap,
                parents=valid_parents,
                name=f"COMP_NODE_CHECKPOINT_REMOTE_KICKOFF_iter{iteration}_npu{npu_id}",
                duration_micros=self.kickoff_cost_micros,
            )
            next_npu = (npu_id + 1) % self.num_npus
            prev_npu = (npu_id - 1 + self.num_npus) % self.num_npus
            tag = 8000 + iteration  # Distinct from training comm tags
            snd = send(
                npu_id,
                next_npu,
                bytes_to_write,
                name=f"COMM_SEND_NODE_CHECKPOINT_REMOTE_iter{iteration}_npu{npu_id}",
                parents=[kickoff],
                comm_tag=tag,
            )
            rcv = receive(
                prev_npu,
                npu_id,
                bytes_to_write,
                name=f"COMM_RECV_NODE_CHECKPOINT_REMOTE_iter{iteration}_npu{npu_id}",
                parents=[kickoff],
                comm_tag=tag,
            )
            # Minimal join so orchestrator's prev_comp waits for both send and recv (blocking).
            sync_join = compute(
                flops=1,
                tensor_size=1,
                parents=[snd, rcv],
                name=f"COMP_NODE_CHECKPOINT_REMOTE_SYNC_JOIN_iter{iteration}_npu{npu_id}",
                duration_micros=1,
            )
            # Return [sync_join, kickoff, snd, rcv] so prev_comp=sync_join; all nodes appended
            return [sync_join, kickoff, snd, rcv], None

        if self.mode == "remote_async":
            # Boundary: kickoff|drain. Spawn: COMM upload (background, shares NIC).
            # Throttle: drain only when behind. Training next-iter does NOT depend on upload.
            # Ring (default): GPU-to-GPU proxy for interference. use_storage_sink=True would
            # send to a storage endpoint (requires orchestrator to generate sink trace).
            tag = 8000 + iteration
            nodes_ra: List[ChakraNode] = []
            boundary_parents_ra: List[ChakraNode] = []

            if self.drain_when_backpressure and prev_write_bg is not None and iteration > 0:
                drain = compute(
                    flops=1,
                    tensor_size=1,
                    parents=valid_parents + [prev_write_bg],
                    name=f"COMP_NODE_CHECKPOINT_REMOTE_DRAIN_iter{iteration}_npu{npu_id}",
                    duration_micros=1,
                )
                nodes_ra.append(drain)
                boundary_parents_ra = [drain]
            else:
                boundary_parents_ra = valid_parents

            kickoff_cap = min(cost, int(5e5))  # Same as remote_sync, slightly smaller than before
            kickoff = compute(
                flops=kickoff_cap,
                tensor_size=kickoff_cap,
                parents=boundary_parents_ra,
                name=f"COMP_NODE_CHECKPOINT_REMOTE_KICKOFF_iter{iteration}_npu{npu_id}",
                duration_micros=self.kickoff_cost_micros,
            )
            nodes_ra.append(kickoff)
            # boundary_node = kickoff (or drain); nodes[0] for orchestrator

            upload_send_parents: List[ChakraNode] = [kickoff]
            if prev_write_bg is not None:
                upload_send_parents.append(prev_write_bg)

            if self.use_storage_sink:
                dst_npu = self.num_npus
                upload_send = send(
                    npu_id,
                    dst_npu,
                    bytes_to_write,
                    name=f"COMM_SEND_NODE_CHECKPOINT_REMOTE_ASYNC_iter{iteration}_npu{npu_id}",
                    parents=upload_send_parents,
                    comm_tag=tag,
                )
                nodes_ra.append(upload_send)
                return nodes_ra, upload_send
            else:
                next_npu = (npu_id + 1) % self.num_npus
                prev_npu = (npu_id - 1 + self.num_npus) % self.num_npus
                upload_send = send(
                    npu_id,
                    next_npu,
                    bytes_to_write,
                    name=f"COMM_SEND_NODE_CHECKPOINT_REMOTE_ASYNC_iter{iteration}_npu{npu_id}",
                    parents=upload_send_parents,
                    comm_tag=tag,
                )
                upload_recv = receive(
                    prev_npu,
                    npu_id,
                    bytes_to_write,
                    name=f"COMM_RECV_NODE_CHECKPOINT_REMOTE_ASYNC_iter{iteration}_npu{npu_id}",
                    parents=valid_parents,
                    comm_tag=tag,
                )
                nodes_ra.append(upload_send)
                nodes_ra.append(upload_recv)
                return nodes_ra, upload_send

        # Async (local): boundary=kickoff|drain, bg=write_bg. Next iter depends on boundary only.
        nodes: List[ChakraNode] = []
        boundary_parents: List[ChakraNode] = []

        if self.drain_when_backpressure and prev_write_bg is not None and iteration > 0:
            # Throttle: block only when behind (prior write still in flight)
            drain = compute(
                flops=1,
                tensor_size=1,
                parents=valid_parents + [prev_write_bg],
                name=f"COMP_NODE_CHECKPOINT_DRAIN_iter{iteration}_npu{npu_id}",
                duration_micros=1,
            )
            nodes.append(drain)
            boundary_parents = [drain]
        else:
            boundary_parents = valid_parents

        kickoff = compute(
            flops=min(cost, int(1e6)),
            tensor_size=min(cost, int(1e6)),
            parents=boundary_parents,
            name=f"COMP_NODE_CHECKPOINT_KICKOFF_iter{iteration}_npu{npu_id}",
            duration_micros=self.kickoff_cost_micros,
        )
        nodes.append(kickoff)
        # boundary_node = kickoff (or drain if above); nodes[0] is boundary for orchestrator

        write_bg_parents: List[ChakraNode] = [kickoff]
        if prev_write_bg is not None:
            write_bg_parents.append(prev_write_bg)  # max_inflight=1: chain writes

        write_bg = compute(
            flops=cost,
            tensor_size=cost,
            parents=write_bg_parents,
            name=f"COMP_NODE_CHECKPOINT_WRITE_BG_iter{iteration}_npu{npu_id}",
            duration_micros=duration_micros,
        )
        nodes.append(write_bg)
        return nodes, write_bg

    def get_name(self) -> str:
        return self.model.get_name()

    def get_num_params(self) -> int:
        return self.model.get_num_params()

    def get_num_layers(self) -> int:
        return self.model.get_num_layers()

    def get_hidden_size(self) -> int:
        return self.model.get_hidden_size()

    def get_sequence_len(self) -> int:
        return self.model.get_sequence_len()

    def get_batch_size(self) -> int:
        return self.model.get_batch_size()

    def get_bytes_per_val(self) -> int:
        return self.model.get_bytes_per_val()
