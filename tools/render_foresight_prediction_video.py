#!/usr/bin/env python3
"""Render full-episode foresight marker prediction in the static-figure style."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import cv2
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.gridspec import GridSpec


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NPZ = (
    ROOT
    / "outputs/foresight_retrain_20260708/trial_marker_videos_tplus16/"
    / "caheiban_260609/20260708_180826_port8781_episode_6/marker_prediction_tplus16.npz"
)
DEFAULT_OUT = ROOT / "tmp_vtm_ProjectPage/static/videos/foresight_prediction_board_episode6_tplus16.webm"
DEFAULT_POSTER = ROOT / "tmp_vtm_ProjectPage/static/videos/foresight_prediction_board_episode6_tplus16_preview.jpg"

PHASES = (
    ("Approach", 0, 135, "#fff7ed"),
    ("Contact", 135, 186, "#fef3c7"),
    ("Wiping", 186, 753, "#ecfdf5"),
    ("Release", 753, 864, "#fdf2f8"),
)

MARKER_CMAP = LinearSegmentedColormap.from_list(
    "marker_white_yellow_blue",
    ["#ffffff", "#fff7cc", "#fde68a", "#60a5fa", "#1e3a8a"],
)
ERROR_CMAP = LinearSegmentedColormap.from_list(
    "error_white_to_dark_red",
    ["#fffafa", "#fee2e2", "#fca5a5", "#dc2626", "#7f1d1d"],
)


def marker_mag(marker: np.ndarray) -> np.ndarray:
    return np.linalg.norm(marker.astype(np.float32), axis=-1)


def rolling_mean(values: np.ndarray, window: int = 15) -> np.ndarray:
    if window <= 1:
        return values.astype(np.float32, copy=True)
    pad = window // 2
    padded = np.pad(values.astype(np.float32), (pad, pad), mode="edge")
    kernel = np.ones(window, dtype=np.float32) / float(window)
    return np.convolve(padded, kernel, mode="valid")


def quiver_scale(marker: np.ndarray, *, error: bool = False, reference_vmax: float | None = None) -> float:
    vmax = float(np.nanmax(marker_mag(marker))) if marker.size else 1.0
    if error:
        return max(vmax * 2.8, 3.0)
    vmax = float(reference_vmax) if reference_vmax is not None else vmax
    return max(vmax * 1.08, 7.5)


def plot_marker_panel(
    ax: plt.Axes,
    marker: np.ndarray,
    title: str,
    cmap: str,
    *,
    vmax: float,
    error: bool = False,
    scale_reference: float | None = None,
) -> object:
    rows, cols = marker.shape[:2]
    x, y = np.meshgrid(np.arange(cols), np.arange(rows))
    mag = marker_mag(marker)
    q = ax.quiver(
        x,
        y,
        marker[..., 0],
        marker[..., 1],
        mag,
        cmap=cmap,
        angles="xy",
        scale_units="xy",
        scale=quiver_scale(marker, error=error, reference_vmax=scale_reference),
        width=0.0058 if error else 0.0070,
        headwidth=4.4 if error else 5.0,
        headlength=5.8 if error else 6.7,
        headaxislength=4.8 if error else 5.8,
        minlength=0.05,
        pivot="tail",
        alpha=0.96,
    )
    q.set_clim(0.0, vmax)
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
    return q


def draw_dynamic_curve(
    ax: plt.Axes,
    base_ts: np.ndarray,
    err_l2: np.ndarray,
    smooth_l2: np.ndarray,
    idx: int,
    *,
    y_max: float,
) -> None:
    current_t = int(base_ts[idx])
    x_start = int(base_ts[0])
    x_end = int(base_ts[-1])

    for name, start, end, color in PHASES:
        clipped_start = max(start, x_start)
        clipped_end = min(end, current_t, x_end)
        if clipped_end <= clipped_start:
            continue
        ax.axvspan(clipped_start, clipped_end, color=color, alpha=0.72, linewidth=0)
        visible_w = clipped_end - clipped_start
        if visible_w >= 26:
            ax.text(
                clipped_start + visible_w / 2,
                y_max * 0.90,
                name,
                ha="center",
                va="center",
                fontsize=10,
                color="#334155",
            )

    xs = base_ts[: idx + 1]
    ax.plot(xs, err_l2[: idx + 1], color="#fed7aa", linewidth=1.2, label="raw L2")
    ax.plot(xs, smooth_l2[: idx + 1], color="#ea580c", linewidth=2.3, label="smoothed L2")
    ax.scatter([base_ts[idx]], [smooth_l2[idx]], s=52, color="#ea580c", edgecolor="white", zorder=3)

    ax.set_title("Episode-level marker prediction error", fontsize=13, loc="left", pad=6)
    ax.set_xlabel("base step t", fontsize=11)
    ax.set_ylabel("L2", fontsize=11)
    ax.grid(True, color="#e5e7eb", linewidth=0.8)
    ax.legend(loc="upper right", frameon=False, fontsize=10)
    ax.set_xlim(x_start, x_end)
    ax.set_ylim(0.0, y_max)
    ax.tick_params(labelsize=10)
    for spine in ax.spines.values():
        spine.set_color("#cbd5e1")


def render_frame(
    gt: np.ndarray,
    pred: np.ndarray,
    err_l2: np.ndarray,
    smooth_l2: np.ndarray,
    base_ts: np.ndarray,
    target_ts: np.ndarray,
    idx: int,
    *,
    marker_vmax: float,
    diff_vmax: float,
    y_max: float,
    dpi: int,
) -> np.ndarray:
    gt_i = gt[idx]
    pred_i = pred[idx]
    diff_i = pred_i - gt_i

    fig = plt.figure(figsize=(16, 8.4), dpi=dpi, facecolor="white")
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

    q_gt = plot_marker_panel(
        ax_gt,
        gt_i,
        "GT future",
        MARKER_CMAP,
        vmax=marker_vmax,
        scale_reference=marker_vmax,
    )
    q_pred = plot_marker_panel(
        ax_pred,
        pred_i,
        "Predicted future",
        MARKER_CMAP,
        vmax=marker_vmax,
        scale_reference=marker_vmax,
    )
    q_diff = plot_marker_panel(
        ax_diff,
        diff_i,
        "Error (pred - GT)",
        ERROR_CMAP,
        vmax=diff_vmax,
        error=True,
    )

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
    draw_dynamic_curve(ax_curve, base_ts, err_l2, smooth_l2, idx, y_max=y_max)

    fig.canvas.draw()
    rgba = np.asarray(fig.canvas.buffer_rgba())
    frame = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)
    plt.close(fig)
    return frame


def render_video(
    npz_path: Path,
    out_path: Path,
    poster_path: Path,
    *,
    fps: float,
    stride: int,
    dpi: int,
    poster_step: int,
    target_frames: int | None = None,
) -> None:
    data = np.load(npz_path)
    gt = data["gt"].astype(np.float32)
    pred = data["pred"].astype(np.float32)
    err_l2 = data["err_l2"].astype(np.float32)
    base_ts = data["base_ts"].astype(np.int64)
    target_ts = data["target_ts"].astype(np.int64)
    smooth_l2 = rolling_mean(err_l2, 15)

    marker_vmax = float(np.percentile(marker_mag(np.concatenate([gt, pred], axis=0)), 98.5))
    diff_vmax = 3.0
    y_max = float(np.percentile(err_l2, 99.0) * 1.08)
    marker_vmax = max(marker_vmax, 1e-6)
    diff_vmax = max(diff_vmax, 1e-6)
    y_max = max(y_max, 1e-6)

    if target_frames is not None and int(target_frames) > 1:
        frame_indices = np.rint(
            np.linspace(0, len(gt) - 1, int(target_frames))
        ).astype(int).tolist()
    else:
        frame_indices = list(range(0, len(gt), max(1, int(stride))))
        if frame_indices[-1] != len(gt) - 1:
            frame_indices.append(len(gt) - 1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    poster_path.parent.mkdir(parents=True, exist_ok=True)

    first = render_frame(
        gt,
        pred,
        err_l2,
        smooth_l2,
        base_ts,
        target_ts,
        frame_indices[0],
        marker_vmax=marker_vmax,
        diff_vmax=diff_vmax,
        y_max=y_max,
        dpi=dpi,
    )
    h, w = first.shape[:2]
    suffix = out_path.suffix.lower()
    fourcc = "VP80" if suffix == ".webm" else "mp4v"
    writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*fourcc), float(fps), (w, h))
    if not writer.isOpened():
        raise RuntimeError(f"Could not open video writer: {out_path}")
    writer.write(first)

    poster_idx = int(np.argmin(np.abs(base_ts - int(poster_step))))
    poster_frame = None
    if frame_indices[0] == poster_idx:
        poster_frame = first.copy()

    for n, idx in enumerate(frame_indices[1:], start=2):
        frame = render_frame(
            gt,
            pred,
            err_l2,
            smooth_l2,
            base_ts,
            target_ts,
            idx,
            marker_vmax=marker_vmax,
            diff_vmax=diff_vmax,
            y_max=y_max,
            dpi=dpi,
        )
        if poster_frame is None and idx >= poster_idx:
            poster_frame = frame.copy()
        writer.write(frame)
        if n % 50 == 0 or n == len(frame_indices):
            print(f"rendered {n}/{len(frame_indices)} frames")

    writer.release()
    if poster_frame is None:
        poster_frame = render_frame(
            gt,
            pred,
            err_l2,
            smooth_l2,
            base_ts,
            target_ts,
            poster_idx,
            marker_vmax=marker_vmax,
            diff_vmax=diff_vmax,
            y_max=y_max,
            dpi=dpi,
        )
    cv2.imwrite(str(poster_path), poster_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    print(out_path)
    print(poster_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--npz", type=Path, default=DEFAULT_NPZ)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--poster", type=Path, default=DEFAULT_POSTER)
    parser.add_argument("--fps", type=float, default=20.0)
    parser.add_argument("--stride", type=int, default=1)
    parser.add_argument("--dpi", type=int, default=100)
    parser.add_argument("--poster-step", type=int, default=420)
    parser.add_argument("--target-frames", type=int, default=None)
    args = parser.parse_args()
    render_video(
        args.npz,
        args.out,
        args.poster,
        fps=args.fps,
        stride=args.stride,
        dpi=args.dpi,
        poster_step=args.poster_step,
        target_frames=args.target_frames,
    )


if __name__ == "__main__":
    main()
