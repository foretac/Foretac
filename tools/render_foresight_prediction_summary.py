#!/usr/bin/env python3
"""Render a quiver-style GT-vs-pred foresight marker summary."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NPZ = (
    ROOT
    / "outputs/foresight_retrain_20260708/trial_marker_videos_tplus16/"
    / "caheiban_260609/20260708_180826_port8781_episode_6/marker_prediction_tplus16.npz"
)
DEFAULT_OUT = ROOT / "tmp_vtm_ProjectPage/static/images/foresight_prediction_board_episode6_tplus16_summary.png"


def marker_mag(marker: np.ndarray) -> np.ndarray:
    return np.linalg.norm(marker.astype(np.float32), axis=-1)


def rolling_mean(values: np.ndarray, window: int = 15) -> np.ndarray:
    if window <= 1:
        return values.astype(np.float32, copy=True)
    pad = window // 2
    padded = np.pad(values.astype(np.float32), (pad, pad), mode="edge")
    kernel = np.ones(window, dtype=np.float32) / float(window)
    return np.convolve(padded, kernel, mode="valid")


def quiver_scale(mag: np.ndarray, *, error: bool = False) -> float:
    vmax = float(np.nanmax(mag)) if mag.size else 1.0
    if error:
        return max(vmax * 2.8, 3.0)
    return max(vmax * 1.9, 11.5)


def plot_marker_panel(
    ax: plt.Axes,
    marker: np.ndarray,
    title: str,
    cmap: str,
    *,
    error: bool = False,
) -> tuple[object, np.ndarray]:
    rows, cols = marker.shape[:2]
    x, y = np.meshgrid(np.arange(cols), np.arange(rows))
    u = marker[..., 0]
    v = marker[..., 1]
    mag = marker_mag(marker)

    q = ax.quiver(
        x,
        y,
        u,
        v,
        mag,
        cmap=cmap,
        angles="xy",
        scale_units="xy",
        scale=quiver_scale(mag, error=error),
        width=0.0062,
        headwidth=4.5,
        headlength=6.0,
        headaxislength=5.0,
        minlength=0.05,
        pivot="tail",
    )
    ax.set_title(
        f"{title}\nmax={float(mag.max()):.1f}, mean={float(mag.mean()):.1f}",
        fontsize=16,
        pad=8,
    )
    ax.set_xlim(-0.5, cols - 0.5)
    ax.set_ylim(-0.5, rows - 0.5)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks(np.arange(cols))
    ax.set_yticks(np.arange(rows))
    ax.tick_params(labelsize=10, length=3, color="#334155")
    ax.grid(True, color="#e5e7eb", linewidth=0.8)
    for spine in ax.spines.values():
        spine.set_linewidth(1.0)
        spine.set_color("#111827")
    return q, mag


def render_summary(npz_path: Path, out_path: Path, sample_step: int) -> None:
    data = np.load(npz_path)
    gt = data["gt"].astype(np.float32)
    pred = data["pred"].astype(np.float32)
    err_l2 = data["err_l2"].astype(np.float32)
    base_ts = data["base_ts"].astype(np.int64)
    target_ts = data["target_ts"].astype(np.int64)

    idx = int(np.argmin(np.abs(base_ts - int(sample_step))))
    gt_i = gt[idx]
    pred_i = pred[idx]
    diff_i = pred_i - gt_i

    fig = plt.figure(figsize=(16, 8.4), dpi=150, facecolor="white")
    gs = GridSpec(
        2,
        6,
        figure=fig,
        height_ratios=[5.4, 1.45],
        width_ratios=[1.0, 0.048, 1.0, 0.048, 1.0, 0.048],
        hspace=0.48,
        wspace=0.34,
    )

    ax_gt = fig.add_subplot(gs[0, 0])
    cax_gt = fig.add_subplot(gs[0, 1])
    ax_pred = fig.add_subplot(gs[0, 2])
    cax_pred = fig.add_subplot(gs[0, 3])
    ax_diff = fig.add_subplot(gs[0, 4])
    cax_diff = fig.add_subplot(gs[0, 5])
    ax_curve = fig.add_subplot(gs[1, :])

    q_gt, _ = plot_marker_panel(ax_gt, gt_i, "GT future", "viridis")
    q_pred, _ = plot_marker_panel(ax_pred, pred_i, "Predicted future", "viridis")
    q_diff, _ = plot_marker_panel(ax_diff, diff_i, "Error (pred - GT)", "Reds", error=True)

    for q, cax in ((q_gt, cax_gt), (q_pred, cax_pred), (q_diff, cax_diff)):
        cb = fig.colorbar(q, cax=cax)
        cb.ax.set_title("px", fontsize=9, pad=5)
        cb.ax.tick_params(labelsize=9)

    horizon = int(target_ts[idx] - base_ts[idx])
    fig.suptitle(
        f"Foresight Prediction Visualization  |  t={int(base_ts[idx])} -> t+H={int(target_ts[idx])}  |  H={horizon}  |  L2={float(err_l2[idx]):.3f}",
        fontsize=19,
        y=0.985,
    )

    smooth = rolling_mean(err_l2, 15)
    ax_curve.plot(base_ts, err_l2, color="#fed7aa", linewidth=1.2, label="raw L2")
    ax_curve.plot(base_ts, smooth, color="#ea580c", linewidth=2.3, label="smoothed L2")
    ax_curve.axvline(base_ts[idx], color="#111827", linewidth=1.4)
    ax_curve.scatter([base_ts[idx]], [smooth[idx]], s=52, color="#ea580c", edgecolor="white", zorder=3)
    ax_curve.set_title("Episode-level marker prediction error", fontsize=13, loc="left", pad=6)
    ax_curve.set_xlabel("base step t", fontsize=11)
    ax_curve.set_ylabel("L2", fontsize=11)
    ax_curve.grid(True, color="#e5e7eb", linewidth=0.8)
    ax_curve.legend(loc="upper right", frameon=False, fontsize=10)
    ax_curve.set_xlim(int(base_ts[0]), int(base_ts[-1]))
    ax_curve.set_ylim(bottom=0.0)
    ax_curve.tick_params(labelsize=10)
    for spine in ax_curve.spines.values():
        spine.set_color("#cbd5e1")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--npz", type=Path, default=DEFAULT_NPZ)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--sample-step",
        type=int,
        default=420,
        help="Base step t to visualize. The nearest available step is used.",
    )
    args = parser.parse_args()
    render_summary(args.npz, args.out, args.sample_step)
    print(args.out)


if __name__ == "__main__":
    main()
