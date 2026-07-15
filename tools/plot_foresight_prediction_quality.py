#!/usr/bin/env python3
"""Plot Figure 4: foresight prediction quality across horizons."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


DEFAULT_EXAMPLES = Path(
    "/home/chenshuai/Project/output/foresight_ckpt/"
    "latent_foresight_board_260609_260610_multistep16_boardvae_marker_only_e100_bs16_preload/"
    "figures/val_prediction_examples.npz"
)


def _mean_sem(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = values.mean(axis=0)
    if values.shape[0] <= 1:
        return mean, np.zeros_like(mean)
    sem = values.std(axis=0, ddof=1) / np.sqrt(values.shape[0])
    return mean, sem


def compute_metrics(examples_path: Path, horizons: list[int]) -> dict:
    data = np.load(examples_path)
    pred_latent = data["pred_latent"].astype(np.float64)
    gt_latent = data["gt_latent"].astype(np.float64)
    pred_marker = data["pred_marker_raw"].astype(np.float64)
    gt_marker = data["gt_marker_raw"].astype(np.float64)

    indices = np.asarray([h - 1 for h in horizons], dtype=int)
    if indices.min() < 0 or indices.max() >= pred_latent.shape[1]:
        raise ValueError(f"horizons {horizons} exceed cached horizon {pred_latent.shape[1]}")

    latent_abs = np.abs(pred_latent - gt_latent).mean(axis=2)
    pred_flat = pred_latent.reshape(pred_latent.shape[0], pred_latent.shape[1], -1)
    gt_flat = gt_latent.reshape(gt_latent.shape[0], gt_latent.shape[1], -1)
    latent_dot = (pred_flat * gt_flat).sum(axis=2)
    latent_norm = np.linalg.norm(pred_flat, axis=2) * np.linalg.norm(gt_flat, axis=2)
    latent_cos = latent_dot / np.maximum(latent_norm, 1e-8)

    marker_vec_l2 = np.linalg.norm(pred_marker - gt_marker, axis=-1).mean(axis=(2, 3))

    latent_mae_mean, latent_mae_sem = _mean_sem(latent_abs[:, indices])
    latent_cos_mean, latent_cos_sem = _mean_sem(latent_cos[:, indices])
    marker_l2_mean, marker_l2_sem = _mean_sem(marker_vec_l2[:, indices])

    return {
        "source": str(examples_path),
        "num_windows": int(pred_latent.shape[0]),
        "cached_horizon": int(pred_latent.shape[1]),
        "horizons": horizons,
        "latent_mae": latent_mae_mean.tolist(),
        "latent_mae_sem": latent_mae_sem.tolist(),
        "latent_cosine": latent_cos_mean.tolist(),
        "latent_cosine_sem": latent_cos_sem.tolist(),
        "marker_reconstruction_error_px": marker_l2_mean.tolist(),
        "marker_reconstruction_error_px_sem": marker_l2_sem.tolist(),
    }


def plot(metrics: dict, out_path: Path) -> None:
    horizons = np.asarray(metrics["horizons"], dtype=float)
    panels = [
        (
            "A",
            "Latent MAE ↓",
            np.asarray(metrics["latent_mae"]),
            np.asarray(metrics["latent_mae_sem"]),
            "#2f6f9f",
            "MAE",
        ),
        (
            "B",
            "Latent Cosine Similarity ↑",
            np.asarray(metrics["latent_cosine"]),
            np.asarray(metrics["latent_cosine_sem"]),
            "#2d8a66",
            "cosine",
        ),
        (
            "C",
            "Marker Reconstruction Error (px) ↓",
            np.asarray(metrics["marker_reconstruction_error_px"]),
            np.asarray(metrics["marker_reconstruction_error_px_sem"]),
            "#b05238",
            "px",
        ),
    ]

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.titlesize": 12,
            "axes.labelsize": 10.5,
            "xtick.labelsize": 9.5,
            "ytick.labelsize": 9.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )

    fig, axes = plt.subplots(1, 3, figsize=(12.6, 3.15), dpi=240)
    fig.patch.set_facecolor("#ffffff")

    for ax, (_letter, title, mean, sem, color, ylabel) in zip(axes, panels):
        ax.set_facecolor("#fbfbf8")
        ax.plot(
            horizons,
            mean,
            marker="o",
            markersize=5.2,
            linewidth=2.4,
            color=color,
            markerfacecolor="#ffffff",
            markeredgewidth=1.8,
            zorder=3,
        )
        ax.fill_between(horizons, mean - sem, mean + sem, color=color, alpha=0.10, linewidth=0)
        ax.grid(True, axis="y", color="#d9d6cc", alpha=0.65, linewidth=0.8)
        ax.grid(True, axis="x", color="#ebe7dd", alpha=0.45, linewidth=0.6)
        ax.set_xticks(horizons)
        ax.set_xlabel("Prediction horizon H (steps)")
        ax.set_ylabel(ylabel)
        ax.set_title(title, pad=8, fontweight="semibold")

        ax.text(
            0.965,
            0.075,
            "mean ± SEM",
            transform=ax.transAxes,
            fontsize=8.4,
            color="#6f6a62",
            ha="right",
            va="bottom",
            zorder=8,
            bbox={
                "boxstyle": "round,pad=0.16",
                "facecolor": "#fbfbf8",
                "edgecolor": "none",
                "alpha": 0.96,
            },
        )

    axes[1].set_ylim(
        max(0.99, min(metrics["latent_cosine"]) - 0.0025),
        min(1.0, max(metrics["latent_cosine"]) + 0.0008),
    )

    fig.text(
        0.012,
        1.015,
        f"Foresight prediction quality over {metrics['num_windows']} validation windows",
        fontsize=12.5,
        fontweight="bold",
        color="#1f1f1f",
        ha="left",
        va="bottom",
    )
    fig.tight_layout(pad=1.1, w_pad=1.6)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--examples", type=Path, default=DEFAULT_EXAMPLES)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("tmp_vtm_ProjectPage/static/images/foresight_prediction_quality_horizons.png"),
    )
    parser.add_argument(
        "--metrics-out",
        type=Path,
        default=Path(
            "tmp_vtm_ProjectPage/static/images/foresight_prediction_quality_horizons_metrics.json"
        ),
    )
    parser.add_argument("--horizons", type=int, nargs="+", default=[1, 4, 8, 12, 16])
    args = parser.parse_args()

    metrics = compute_metrics(args.examples, args.horizons)
    plot(metrics, args.out)
    args.metrics_out.parent.mkdir(parents=True, exist_ok=True)
    args.metrics_out.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(json.dumps(metrics, indent=2))
    print(f"saved figure: {args.out}")
    print(f"saved metrics: {args.metrics_out}")


if __name__ == "__main__":
    main()
