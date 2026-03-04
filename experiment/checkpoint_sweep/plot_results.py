#!/usr/bin/env python3
"""
Generate visuals for checkpoint sweep: BASE vs REMOTE_SYNC vs REMOTE_ASYNC.
Reads results/checkpoint_sweep.json, writes figures to results/figures/.

Requires: pip install matplotlib
"""
import json
import sys
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mtick
except ImportError:
    print("matplotlib not found. Install with: pip install matplotlib", file=sys.stderr)
    sys.exit(1)

RESULTS_DIR = Path(__file__).resolve().parent / "results"
FIG_DIR = RESULTS_DIR / "figures"
JSON_PATH = RESULTS_DIR / "checkpoint_sweep.json"

BANDWIDTHS = [100, 50, 10, 1]
STATE_MULTS = [10, 100, 1000, 10000]


def load_and_organize():
    with open(JSON_PATH) as f:
        rows = json.load(f)
    base_by_bw = {}
    sync = {}  # (sm, bw) -> {wall, gpu, comm, overlap}
    async_ = {}
    for r in rows:
        bw = r["bandwidth_gb_s"]
        mode = r["mode"]
        if mode == "BASE":
            base_by_bw[bw] = {
                "wall": r["wall_time_cycles"],
                "gpu": r["gpu_time_cycles"],
                "comm": r["comm_time_cycles"],
            }
        elif mode == "REMOTE_SYNC":
            sm = r["state_multiplier"]
            if sm is not None and r["wall_time_cycles"] is not None:
                sync[(sm, bw)] = {
                    "wall": r["wall_time_cycles"],
                    "gpu": r["gpu_time_cycles"],
                    "comm": r["comm_time_cycles"],
                }
        elif mode == "REMOTE_ASYNC":
            sm = r["state_multiplier"]
            if sm is not None and r["wall_time_cycles"] is not None:
                async_[(sm, bw)] = {
                    "wall": r["wall_time_cycles"],
                    "gpu": r["gpu_time_cycles"],
                    "comm": r["comm_time_cycles"],
                    "overlap": r["overlap_cycles"],
                }
    return base_by_bw, sync, async_


def fig_wall_by_strategy(base_by_bw, sync, async_):
    """Wall time (cycles) by strategy: one subplot per state_mult, x=bandwidth."""
    fig, axes = plt.subplots(2, 2, figsize=(11, 9), sharey=True)
    axes = axes.flatten()
    for idx, sm in enumerate(STATE_MULTS):
        ax = axes[idx]
        bws = []
        base_vals, sync_vals, async_vals = [], [], []
        for bw in BANDWIDTHS:
            bws.append(str(bw))
            base_vals.append(base_by_bw[bw]["wall"] / 1e9)
            sync_vals.append(sync.get((sm, bw), {}).get("wall") or 0)
            async_vals.append(async_.get((sm, bw), {}).get("wall") or 0)
        sync_vals = [v / 1e9 if v else 1e-3 for v in sync_vals]
        async_vals = [v / 1e9 if v else 1e-3 for v in async_vals]
        x = range(len(BANDWIDTHS))
        w = 0.26
        ax.bar([i - w for i in x], base_vals, width=w, label="BASE", color="C0", alpha=0.9)
        ax.bar([i for i in x], sync_vals, width=w, label="REMOTE_SYNC", color="C1", alpha=0.9)
        ax.bar([i + w for i in x], async_vals, width=w, label="REMOTE_ASYNC", color="C2", alpha=0.9)
        ax.set_xticks(x)
        ax.set_xticklabels([f"{b} GB/s" for b in BANDWIDTHS])
        ax.set_ylabel("Wall time (×10⁹ cycles)")
        ax.set_title(f"state_multiplier = {sm}")
        ax.legend(loc="upper right", fontsize=8)
        ax.set_yscale("log")
    fig.suptitle("Wall time by strategy and bandwidth", fontsize=12)
    plt.tight_layout()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / "wall_by_strategy.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved {FIG_DIR / 'wall_by_strategy.png'}")


def fig_pct_delta_from_base(base_by_bw, sync, async_):
    """% delta from BASE (wall time): positive = slower than BASE."""
    fig, ax = plt.subplots(figsize=(12, 6))
    # One group per (sm, bw): SYNC bar and ASYNC bar
    labels = []
    sync_pct = []
    async_pct = []
    for sm in STATE_MULTS:
        for bw in BANDWIDTHS:
            base_wall = base_by_bw[bw]["wall"]
            sw = sync.get((sm, bw), {}).get("wall")
            aw = async_.get((sm, bw), {}).get("wall")
            labels.append(f"sm={sm}\n{bw} GB/s")
            sync_pct.append((sw - base_wall) / base_wall * 100 if sw else float("nan"))
            async_pct.append((aw - base_wall) / base_wall * 100 if aw else float("nan"))
    x = range(len(labels))
    w = 0.35
    ax.bar([i - w / 2 for i in x], sync_pct, width=w, label="REMOTE_SYNC Δ%", color="C1", alpha=0.9)
    ax.bar([i + w / 2 for i in x], async_pct, width=w, label="REMOTE_ASYNC Δ%", color="C2", alpha=0.9)
    ax.axhline(0, color="gray", linestyle="-", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8, rotation=0)
    ax.set_ylabel("% Δ vs BASE (wall time)")
    ax.set_title("Checkpoint overhead: % increase in wall time vs BASE")
    ax.legend()
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    plt.tight_layout()
    fig.savefig(FIG_DIR / "pct_delta_from_base.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved {FIG_DIR / 'pct_delta_from_base.png'}")


def fig_sync_vs_async(sync, async_):
    """Sync vs Async: wall time difference (ASYNC − SYNC) in cycles; negative = async faster."""
    fig, ax = plt.subplots(figsize=(12, 5))
    labels = []
    diffs = []
    for sm in STATE_MULTS:
        for bw in BANDWIDTHS:
            sw = sync.get((sm, bw), {}).get("wall")
            aw = async_.get((sm, bw), {}).get("wall")
            if sw and aw:
                labels.append(f"sm={sm}, {bw} GB/s")
                diffs.append(aw - sw)  # negative ≈ -34592
    x = range(len(labels))
    colors = ["C2" if d < 0 else "C3" for d in diffs]
    ax.bar(x, diffs, color=colors, alpha=0.9)
    ax.axhline(0, color="gray", linestyle="-", linewidth=0.8)
    ax.axhline(-34592, color="black", linestyle="--", linewidth=1, label="≈ −34,592 cycles")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8, rotation=45, ha="right")
    ax.set_ylabel("Wall time difference (cycles)\nASYNC − SYNC")
    ax.set_title("Sync vs Async: small wall-time difference (negative = async faster)")
    ax.legend()
    plt.tight_layout()
    fig.savefig(FIG_DIR / "sync_vs_async.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved {FIG_DIR / 'sync_vs_async.png'}")


def fig_gpu_comm_breakdown(base_by_bw, sync, async_):
    """Breakdown: Wall = GPU + Comm − Overlap. One panel per mode (sm=10, 100 GB/s)."""
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    sm, bw = 10, 100
    base_wall = base_by_bw[bw]["wall"]
    base_gpu = base_by_bw[bw]["gpu"]
    base_comm = base_by_bw[bw]["comm"]
    sync_w = sync.get((sm, bw), {}).get("wall")
    sync_g = sync.get((sm, bw), {}).get("gpu")
    sync_c = sync.get((sm, bw), {}).get("comm")
    async_w = async_.get((sm, bw), {}).get("wall")
    async_g = async_.get((sm, bw), {}).get("gpu")
    async_c = async_.get((sm, bw), {}).get("comm")
    async_o = async_.get((sm, bw), {}).get("overlap", 0)

    for ax, (label, wall, gpu, comm, overlap) in [
        (axes[0], ("BASE", base_wall, base_gpu, base_comm, 0)),
        (axes[1], ("REMOTE_SYNC", sync_w, sync_g, sync_c, 0)),
        (axes[2], ("REMOTE_ASYNC", async_w, async_g, async_c, async_o)),
    ]:
        if wall is None:
            continue
        # Stack: GPU (tiny), then Comm; for async show Overlap as text
        gpu_n = gpu / 1e9
        comm_n = comm / 1e9
        ax.barh(0, gpu_n, left=0, height=0.4, label="GPU", color="C0", alpha=0.9)
        ax.barh(0, comm_n, left=gpu_n, height=0.4, label="Comm", color="C1", alpha=0.9)
        ax.set_xlabel("Cycles (×10⁹)")
        ax.set_title(f"{label}\nWall = {wall/1e9:,.1f}×10⁹")
        ax.set_yticks([0])
        ax.set_yticklabels([label])
        if overlap > 0:
            ax.text(0.98, 0.5, f"Overlap\n{overlap/1e6:.2f}×10⁶", transform=ax.transAxes, fontsize=8, ha="right", va="center")
        ax.legend(loc="upper right", fontsize=7)
    fig.suptitle("GPU + Comm → Wall (state_mult=10, 100 GB/s); ASYNC has Overlap", fontsize=11)
    plt.tight_layout()
    fig.savefig(FIG_DIR / "gpu_comm_breakdown.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved {FIG_DIR / 'gpu_comm_breakdown.png'}")


def fig_heatmap_overhead(base_by_bw, sync, async_, mode="REMOTE_SYNC"):
    """Heatmap: rows = state_mult, cols = bandwidth, cell = % delta from BASE."""
    fig, ax = plt.subplots(figsize=(6, 4))
    data = []
    for sm in STATE_MULTS:
        row = []
        for bw in BANDWIDTHS:
            base_wall = base_by_bw[bw]["wall"]
            if mode == "REMOTE_SYNC":
                val = sync.get((sm, bw), {}).get("wall")
            else:
                val = async_.get((sm, bw), {}).get("wall")
            if val:
                row.append((val - base_wall) / base_wall * 100)
            else:
                row.append(float("nan"))
        data.append(row)
    im = ax.imshow(data, aspect="auto", cmap="YlOrRd")
    ax.set_xticks(range(len(BANDWIDTHS)))
    ax.set_xticklabels([f"{b} GB/s" for b in BANDWIDTHS])
    ax.set_yticks(range(len(STATE_MULTS)))
    ax.set_yticklabels([str(s) for s in STATE_MULTS])
    ax.set_xlabel("Bandwidth")
    ax.set_ylabel("state_multiplier")
    ax.set_title(f"% wall time increase vs BASE — {mode}")
    plt.colorbar(im, ax=ax, label="% Δ vs BASE")
    for i in range(len(STATE_MULTS)):
        for j in range(len(BANDWIDTHS)):
            v = data[i][j]
            if not (v != v):  # not nan
                ax.text(j, i, f"{v:.0f}%", ha="center", va="center", fontsize=8)
    plt.tight_layout()
    fig.savefig(FIG_DIR / f"heatmap_overhead_{mode.lower()}.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved {FIG_DIR / f'heatmap_overhead_{mode.lower()}.png'}")


def main():
    print("Loading", JSON_PATH)
    base_by_bw, sync, async_ = load_and_organize()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    print("Generating figures...")
    fig_wall_by_strategy(base_by_bw, sync, async_)
    fig_pct_delta_from_base(base_by_bw, sync, async_)
    fig_sync_vs_async(sync, async_)
    fig_gpu_comm_breakdown(base_by_bw, sync, async_)
    fig_heatmap_overhead(base_by_bw, sync, async_, "REMOTE_SYNC")
    fig_heatmap_overhead(base_by_bw, sync, async_, "REMOTE_ASYNC")
    print("Done.")


if __name__ == "__main__":
    main()
