#!/usr/bin/env python3
"""Render homepage task visualization videos.

This keeps the project-page layout in one place. Marker panels use the same
deformed-grid rendering style as scripts/render_trial_marker_deformed_grid_videos.py.

    /home/chenshuai/miniconda3/envs/TactileACT/bin/python \
        tmp_vtm_ProjectPage/tools/render_homepage_task_videos.py --task chip
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tmp_vtm_ProjectPage/static/videos"
FFMPEG = Path("/home/chenshuai/.local/lib/python3.13/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2")
DEFAULT_FPS = 24.0
W, H = 1920, 1080
TOP_PANEL_Y = 160
BOTTOM_PANEL_Y = 646
SIDE_PANEL_X = 64
SIDE_PANEL_SIZE = 400
SIDE_PANEL_PAD = 16
TACTILE_CROP_TOP_FRAC = 0.02
TACTILE_CROP_BOTTOM_FRAC = 0.10
TACTILE_CROP_SIDE_FRAC = 0.06

TASKS = {
    "board": {
        "title": "Board Wiping",
        "speed_label": "4x speed",
        "trial": ROOT / "outputs/multitask_replay_records/caheiban_260609/20260708_180826_port8781_episode_6",
        "real": OUT / "board_real.mp4",
        "viz": OUT / "board_viz.mp4",
        "viz_preview": OUT / "board_viz_preview.jpg",
        "pred_npz": ROOT / "outputs/foresight_retrain_20260708/trial_marker_videos/caheiban_260609/20260708_180826_port8781_episode_6/marker_prediction_tplus01.npz",
        "top": {
            "label": "Tactile Image",
            "kind": "tactile_hdf5",
            "path": Path("/media/chenshuai/EXTERNAL_USB/pih_dataset/260609/wipe_pos_straight_z124_125_150_20260609/episode_6.hdf5"),
            "dataset": "observations/tac/left/img",
        },
        "bottom": {
            "label": "Predicted Marker Offset",
            "kind": "prediction_marker",
            "path": ROOT / "outputs/foresight_retrain_20260708/trial_marker_videos/caheiban_260609/20260708_180826_port8781_episode_6/marker_prediction_tplus01.npz",
            "key": "pred",
        },
    },
    "vase": {
        "title": "Vase Wiping",
        "speed_label": "4x speed",
        "trial": ROOT / "outputs/multitask_replay_records/huaping_260630/20260708_170659_port8782_episode_14",
        "real": OUT / "vase_real.mp4",
        "viz": OUT / "vase_viz.mp4",
        "viz_preview": OUT / "vase_viz_preview.jpg",
        "pred_npz": ROOT / "outputs/foresight_retrain_20260708/trial_marker_videos/huaping_260630/20260708_170659_port8782_episode_14/marker_prediction_tplus01.npz",
        "top": {
            "label": "Tactile Image",
            "kind": "tactile_hdf5",
            "path": Path("/media/chenshuai/EXTERNAL_USB/pih_dataset/260629_v8j_card/260630_v8j_huaping/peg_in_hole_0630/episode_14.hdf5"),
            "dataset": "observations/tac/left/img",
        },
        "bottom": {
            "label": "Predicted Marker Offset",
            "kind": "prediction_marker",
            "path": ROOT / "outputs/foresight_retrain_20260708/trial_marker_videos/huaping_260630/20260708_170659_port8782_episode_14/marker_prediction_tplus01.npz",
            "key": "pred",
        },
    },
    "card": {
        "title": "Card Swiping",
        "speed_label": "4x speed",
        "trial": ROOT / "outputs/multitask_replay_records/card_260707/20260708_164131_port8783_episode_21",
        "real": OUT / "card_real.mp4",
        "viz": OUT / "card_viz.mp4",
        "viz_preview": OUT / "card_viz_preview.jpg",
        "pred_npz": ROOT / "outputs/foresight_retrain_20260708/trial_marker_videos/card_260707/20260708_164131_port8783_episode_21/marker_prediction_tplus01.npz",
        "top": {
            "label": "Tactile Image",
            "kind": "tactile_hdf5",
            "path": Path("/media/chenshuai/czy_data22/pih_dataset/260707_v8j_card/peg_in_hole_0707/success/episode_21.hdf5"),
            "dataset": "observations/tac/left/img",
        },
        "bottom": {
            "label": "Predicted Marker Offset",
            "kind": "prediction_marker",
            "path": ROOT / "outputs/foresight_retrain_20260708/trial_marker_videos/card_260707/20260708_164131_port8783_episode_21/marker_prediction_tplus01.npz",
            "key": "pred",
        },
    },
    "chip": {
        "title": "Chip Grasping",
        "speed_label": "4x speed",
        "sync_to_episode_steps": True,
        "phase_names": ("Approach", "Grasp", "Transfer", "Place"),
        "phase_steps": (0, 59, 73, 180, 222),
        "trial": ROOT / "outputs/multitask_replay_records/jiashupian_260709/20260710_164508_port8784_episode_1",
        "real": OUT / "chip_real.mp4",
        "viz": OUT / "chip_viz.mp4",
        "viz_preview": OUT / "chip_viz_preview.jpg",
        "pred_npz": ROOT / "outputs/foresight_retrain_20260708/trial_marker_videos/jiashupian_260709/20260710_164508_port8784_episode_1/marker_prediction_tplus01.npz",
        "top": {
            "label": "Tactile Image",
            "kind": "tactile_hdf5",
            "path": ROOT / "outputs/multitask_replay_records/jiashupian_260709/20260710_164508_port8784_episode_1/trace_full.hdf5",
            "dataset": "observations/tac/left/img",
        },
        "bottom": {
            "label": "Predicted Marker Offset",
            "kind": "marker_hdf5",
            "path": ROOT / "outputs/multitask_replay_records/jiashupian_260709/20260710_164508_port8784_episode_1/trace_full.hdf5",
            "dataset": "observations/tac/left/marker_offset",
            "preprocess_marker": True,
            "baseline_frames": 50,
            "temporal_smooth": 9,
            "deadband_scale": 1.35,
            "gate_by_gripper": True,
            "idle_raw_scale": 0.0,
            "idle_motion_gain": 0.22,
            "active_gain": 1.12,
            "display_vmax": 0.34,
        },
    },
    "generalization_visual_perturb": {
        "title": "Generalization Test 1: Visual Perturbation",
        "speed_label": "4x speed",
        "trial": ROOT / "outputs/multitask_replay_records/card_260707/20260710_175728_port8783_episode_4",
        "real": OUT / "generalization_visual_perturb_real.mp4",
        "viz": OUT / "generalization_visual_perturb_viz.mp4",
        "viz_preview": OUT / "generalization_visual_perturb_viz_preview.jpg",
        "top": {
            "label": "Tactile Image",
            "kind": "tactile_hdf5",
            "path": ROOT / "outputs/multitask_replay_records/card_260707/20260710_175728_port8783_episode_4/trace_full.hdf5",
            "dataset": "observations/tac/left/img",
        },
        "bottom": {
            "label": "Predicted Marker Offset",
            "kind": "marker_hdf5",
            "path": ROOT / "outputs/multitask_replay_records/card_260707/20260710_175728_port8783_episode_4/trace_full.hdf5",
            "dataset": "observations/tac/left/marker_offset",
        },
    },
}

BG = (250, 249, 246)
PANEL = (250, 254, 255)
BORDER = (226, 222, 216)
TEXT = (42, 34, 35)
MUTED = (110, 100, 96)
BLUE = (205, 109, 42)
ORANGE = (25, 159, 226)
RED = (54, 74, 194)
GREEN = (135, 151, 94)
LIGHT_BLUE = (238, 216, 198)
PHASE = [(255, 247, 250), (235, 250, 255), (245, 253, 242), (250, 246, 255)]


def put(img, text, xy, scale=0.8, color=TEXT, thick=2, align="left"):
    size, _ = cv2.getTextSize(str(text), cv2.FONT_HERSHEY_SIMPLEX, scale, thick)
    x, y = xy
    if align == "center":
        x -= size[0] // 2
    elif align == "right":
        x -= size[0]
    cv2.putText(img, str(text), (int(x), int(y)), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)


def rect(img, box, color, border=None, thick=2):
    x1, y1, x2, y2 = map(int, box)
    cv2.rectangle(img, (x1, y1), (x2, y2), color, -1, cv2.LINE_AA)
    if border is not None:
        cv2.rectangle(img, (x1, y1), (x2, y2), border, thick, cv2.LINE_AA)


def smooth(x, win=9):
    x = np.asarray(x, np.float32)
    if win <= 1:
        return x
    pad = win // 2
    return np.convolve(np.pad(x, (pad, pad), mode="edge"), np.ones(win, np.float32) / win, mode="valid")


def r01(x):
    x = np.asarray(x, np.float32)
    lo, hi = np.nanpercentile(x, [10, 90])
    return np.clip((x - lo) / (hi - lo + 1e-6), 0, 1)


def nice_step(raw_step: float) -> float:
    if raw_step <= 0:
        return 1.0
    exp = 10 ** np.floor(np.log10(raw_step))
    frac = raw_step / exp
    if frac <= 1:
        nice = 1
    elif frac <= 2:
        nice = 2
    elif frac <= 5:
        nice = 5
    else:
        nice = 10
    return float(nice * exp)


def nice_axis(values, lower_floor=-1.2, target_ticks=5):
    values = np.asarray(values, dtype=np.float32)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return float(lower_floor), 8.0, [0, 2, 4, 6, 8]
    lo = min(float(np.min(finite)), float(lower_floor))
    hi = max(float(np.max(finite)), 1.0)
    span = max(hi - lo, 1.0)
    padded_hi = hi + span * 0.12
    step = nice_step((padded_hi - lo) / max(2, target_ticks - 1))
    ymin = np.floor(lo / step) * step
    ymax = np.ceil(padded_hi / step) * step
    ticks = np.arange(np.ceil(ymin / step) * step, ymax + 0.5 * step, step)
    ticks = [float(t) for t in ticks if ymin - 1e-6 <= t <= ymax + 1e-6]
    return float(ymin), float(ymax), ticks


def read_csv_columns(path: Path):
    with path.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = {}
    for key in rows[0].keys():
        vals = []
        for row in rows:
            try:
                vals.append(float(row[key]))
            except (TypeError, ValueError):
                vals.append(np.nan)
        out[key] = np.asarray(vals, dtype=np.float32)
    return out


def read_marker_video(path: Path):
    cap = cv2.VideoCapture(str(path))
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        h, w = frame.shape[:2]
        crop = frame[70:min(h, 620), 35:min(w, 645)]
        frames.append(cv2.resize(crop, (SIDE_PANEL_SIZE, SIDE_PANEL_SIZE), interpolation=cv2.INTER_CUBIC))
    cap.release()
    if not frames:
        raise RuntimeError(f"no marker frames from {path}")
    return frames


def crop_tactile_image(img: np.ndarray, cfg: dict) -> np.ndarray:
    h, w = img.shape[:2]
    base = min(h, w)
    top = int(round(base * float(cfg.get("crop_top_frac", TACTILE_CROP_TOP_FRAC))))
    bottom = int(round(base * float(cfg.get("crop_bottom_frac", TACTILE_CROP_BOTTOM_FRAC))))
    side = int(round(base * float(cfg.get("crop_side_frac", TACTILE_CROP_SIDE_FRAC))))
    if top < 0 or bottom < 0 or side < 0 or h <= top + bottom or w <= 2 * side:
        return img
    return img[top : h - bottom, side : w - side]


def read_tactile_hdf5(path: Path, dataset: str, cfg: dict):
    try:
        import h5py
    except ImportError as exc:
        raise RuntimeError("chip tactile image panel needs h5py; run in the TactileACT env") from exc
    with h5py.File(path, "r") as root:
        imgs = root[dataset][()]
    return [
        cv2.resize(crop_tactile_image(img, cfg), (SIDE_PANEL_SIZE, SIDE_PANEL_SIZE), interpolation=cv2.INTER_CUBIC)
        for img in imgs
    ]


def read_marker_hdf5(path: Path, dataset: str, cfg: dict):
    try:
        import h5py
    except ImportError as exc:
        raise RuntimeError("marker HDF5 panel needs h5py; run in the TactileACT env") from exc
    with h5py.File(path, "r") as root:
        marker = root[dataset][()].astype(np.float32)
    preprocess_meta = None
    if cfg.get("preprocess_marker", False):
        marker, preprocess_meta = preprocess_trace_marker(marker, path, cfg)
    vmax = float(cfg.get("display_vmax") or marker_vmax(marker))
    source_panel_size = int(cfg.get("source_panel_size", 620))
    displacement_scale = (source_panel_size * 0.085) / max(vmax, 1e-6)
    frames = []
    for m in marker:
        panel = render_marker_panel(
            m,
            panel_size=source_panel_size,
            displacement_scale=displacement_scale,
            vmax=vmax,
        )
        frames.append(cv2.resize(panel, (SIDE_PANEL_SIZE, SIDE_PANEL_SIZE), interpolation=cv2.INTER_AREA))
    meta = {
        "source": str(path),
        "dataset": dataset,
        "marker_vmax_p98": float(marker_vmax(marker)),
        "display_vmax": vmax,
        "displacement_scale": displacement_scale,
        "source_panel_size": source_panel_size,
        "render_style": "deformed_grid_turbo_homepage_dark_arrow",
    }
    if preprocess_meta is not None:
        meta["visual_preprocess"] = preprocess_meta
        meta["render_style"] = "deformed_grid_turbo_homepage_stabilized_marker"
    return frames, meta


def marker_vmax(*arrays: np.ndarray) -> float:
    mags = []
    for arr in arrays:
        if arr.size:
            mags.append(np.linalg.norm(arr.astype(np.float32), axis=-1).reshape(-1))
    if not mags:
        return 1.0
    merged = np.concatenate(mags)
    vmax = float(np.percentile(merged, 98.0))
    if vmax < 1e-6:
        vmax = float(max(np.max(merged), 1.0))
    return vmax


def draw_poly_grid(panel: np.ndarray, points: np.ndarray, color: tuple[int, int, int], thickness: int) -> None:
    rows, cols = points.shape[:2]
    for iy in range(rows):
        for ix in range(cols - 1):
            p0 = tuple(np.rint(points[iy, ix]).astype(int))
            p1 = tuple(np.rint(points[iy, ix + 1]).astype(int))
            cv2.line(panel, p0, p1, color, thickness, cv2.LINE_AA)
    for iy in range(rows - 1):
        for ix in range(cols):
            p0 = tuple(np.rint(points[iy, ix]).astype(int))
            p1 = tuple(np.rint(points[iy + 1, ix]).astype(int))
            cv2.line(panel, p0, p1, color, thickness, cv2.LINE_AA)


def pastel_heat_image(heat: np.ndarray, width: int, height: int) -> np.ndarray:
    heat_img = cv2.resize(np.clip(heat, 0, 1).astype(np.float32), (width, height), interpolation=cv2.INTER_CUBIC)
    stops = [
        (0.00, np.array([244, 245, 242], dtype=np.float32)),
        (0.40, np.array([232, 242, 235], dtype=np.float32)),
        (0.75, np.array([218, 232, 245], dtype=np.float32)),
        (1.00, np.array([196, 214, 244], dtype=np.float32)),
    ]
    out = np.empty((height, width, 3), dtype=np.float32)
    for (a, ca), (b, cb) in zip(stops[:-1], stops[1:]):
        mask = (heat_img >= a) & (heat_img <= b)
        t = np.clip((heat_img - a) / max(b - a, 1e-6), 0, 1)[..., None]
        out[mask] = (ca * (1 - t) + cb * t)[mask]
    out[heat_img < stops[0][0]] = stops[0][1]
    out[heat_img > stops[-1][0]] = stops[-1][1]
    return out.astype(np.uint8)


def marker_dot_color(value: float) -> tuple[int, int, int]:
    # BGR colors: blue-gray -> teal -> amber/red, with enough contrast on light panels.
    stops = [
        (0.00, np.array([120, 90, 58], dtype=np.float32)),
        (0.45, np.array([104, 146, 54], dtype=np.float32)),
        (0.75, np.array([58, 162, 212], dtype=np.float32)),
        (1.00, np.array([48, 68, 190], dtype=np.float32)),
    ]
    value = float(np.clip(value, 0.0, 1.0))
    for (a, ca), (b, cb) in zip(stops[:-1], stops[1:]):
        if value <= b:
            t = (value - a) / max(b - a, 1e-6)
            color = ca * (1 - t) + cb * t
            return tuple(int(x) for x in color)
    return tuple(int(x) for x in stops[-1][1])


def render_marker_panel(marker: np.ndarray, panel_size: int, displacement_scale: float, vmax: float) -> np.ndarray:
    width = height = int(panel_size)
    panel = np.full((height, width, 3), 252, dtype=np.uint8)
    margin = int(min(width, height) * 0.13)
    xs = np.linspace(margin, width - margin, marker.shape[1])
    ys = np.linspace(margin, height - margin, marker.shape[0])
    base_x, base_y = np.meshgrid(xs, ys)
    base = np.stack([base_x, base_y], axis=-1).astype(np.float32)
    displaced = base + marker.astype(np.float32) * displacement_scale

    mag = np.linalg.norm(marker, axis=-1)
    heat = np.clip(mag / max(vmax, 1e-6), 0.0, 1.0)
    heat_img = cv2.resize((heat * 255).astype(np.uint8), (width, height), interpolation=cv2.INTER_CUBIC)
    heat_color = cv2.applyColorMap(heat_img, cv2.COLORMAP_TURBO)
    panel = cv2.addWeighted(panel, 0.86, heat_color, 0.14, 0)

    draw_poly_grid(panel, base, (214, 220, 228), 1)

    for iy in range(marker.shape[0]):
        for ix in range(marker.shape[1]):
            start = tuple(np.rint(base[iy, ix]).astype(int))
            end = tuple(np.rint(displaced[iy, ix]).astype(int))
            cv2.arrowedLine(panel, start, end, (52, 60, 74), 2, cv2.LINE_AA, tipLength=0.22)

    overlay = panel.copy()
    draw_poly_grid(overlay, displaced, (18, 125, 160), 3)
    panel = cv2.addWeighted(panel, 0.72, overlay, 0.28, 0)
    draw_poly_grid(panel, displaced, (10, 104, 140), 2)

    for iy in range(marker.shape[0]):
        for ix in range(marker.shape[1]):
            base_pt = tuple(np.rint(base[iy, ix]).astype(int))
            cur_pt = tuple(np.rint(displaced[iy, ix]).astype(int))
            color_idx = int(np.clip(heat[iy, ix] * 255, 0, 255))
            color = cv2.applyColorMap(np.array([[color_idx]], dtype=np.uint8), cv2.COLORMAP_TURBO)[0, 0]
            color_tuple = tuple(int(v) for v in color)
            cv2.circle(panel, base_pt, 2, (160, 166, 176), -1, cv2.LINE_AA)
            cv2.circle(panel, cur_pt, 6, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(panel, cur_pt, 4, color_tuple, -1, cv2.LINE_AA)

    cv2.rectangle(panel, (0, 0), (width - 1, height - 1), (210, 216, 224), 2)
    return panel


def read_prediction_marker(path: Path, key: str, cfg: dict):
    data = np.load(path)
    marker = data[key].astype(np.float32)
    vmax = float(cfg.get("display_vmax") or marker_vmax(data["gt"], data["pred"]))
    source_panel_size = int(cfg.get("source_panel_size", 620))
    displacement_scale = (source_panel_size * 0.085) / max(vmax, 1e-6)
    frames = []
    for m in marker:
        panel = render_marker_panel(
            m,
            panel_size=source_panel_size,
            displacement_scale=displacement_scale,
            vmax=vmax,
        )
        frames.append(cv2.resize(panel, (SIDE_PANEL_SIZE, SIDE_PANEL_SIZE), interpolation=cv2.INTER_AREA))
    return frames, {
        "source": str(path),
        "key": key,
        "marker_vmax_p98": vmax,
        "displacement_scale": displacement_scale,
        "source_panel_size": source_panel_size,
        "render_style": "deformed_grid_turbo_homepage_dark_arrow",
    }


def smooth_marker(marker: np.ndarray, win: int) -> np.ndarray:
    if win <= 1:
        return marker
    pad = win // 2
    padded = np.pad(marker, ((pad, pad), (0, 0), (0, 0), (0, 0)), mode="edge")
    out = np.empty_like(marker)
    for i in range(marker.shape[0]):
        out[i] = padded[i : i + win].mean(axis=0)
    return out


def smoothstep01(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def build_gripper_gate(trace_path: Path, length: int, baseline_frames: int) -> np.ndarray:
    trace = read_csv_columns(trace_path)
    gripper = None
    for key in ("gripper_pos", "qpos_7", "gripper_target", "action_7"):
        if key in trace:
            gripper = np.asarray(trace[key], dtype=np.float32)
            break
    if gripper is None or len(gripper) != length:
        return np.ones(length, dtype=np.float32)

    open_pos = float(np.nanmedian(gripper[:baseline_frames]))
    # Full opacity once the gripper has clearly moved away from its open pose.
    gate = smoothstep01((gripper - (open_pos + 3.0)) / 18.0)
    return gate.astype(np.float32)


def preprocess_trace_marker(marker: np.ndarray, path: Path, cfg: dict):
    baseline_frames = int(cfg.get("baseline_frames", min(50, len(marker))))
    baseline_frames = max(1, min(baseline_frames, len(marker)))
    baseline = np.median(marker[:baseline_frames], axis=0, keepdims=True)
    marker_rel = marker - baseline
    marker_rel = smooth_marker(marker_rel, int(cfg.get("temporal_smooth", 1)))

    baseline_mag = np.linalg.norm(marker_rel[:baseline_frames], axis=-1)
    deadband = float(np.percentile(baseline_mag, 98.0) * float(cfg.get("deadband_scale", 1.0)))
    mag = np.linalg.norm(marker_rel, axis=-1, keepdims=True)
    shrink = np.clip((mag - deadband) / np.maximum(mag, 1e-6), 0.0, 1.0)
    active_marker = marker_rel * shrink * float(cfg.get("active_gain", 1.0))

    if cfg.get("gate_by_gripper", False):
        gate = build_gripper_gate(path.parent / "trace.csv", len(active_marker), baseline_frames)
    else:
        gate = np.ones(len(active_marker), dtype=np.float32)

    idle_marker = baseline[0] * float(cfg.get("idle_raw_scale", 0.0))
    idle_motion = marker_rel * float(cfg.get("idle_motion_gain", 0.0))
    marker_vis = (
        idle_marker[None, ...]
        + idle_motion * (1.0 - gate[:, None, None, None])
        + active_marker * gate[:, None, None, None]
    )

    return marker_vis.astype(np.float32), {
        "baseline_frames": baseline_frames,
        "temporal_smooth": int(cfg.get("temporal_smooth", 1)),
        "deadband": deadband,
        "gate_by_gripper": bool(cfg.get("gate_by_gripper", False)),
        "gate_first_nonzero": int(np.argmax(gate > 0.01)) if np.any(gate > 0.01) else None,
        "gate_last_nonzero": int(len(gate) - 1 - np.argmax(gate[::-1] > 0.01)) if np.any(gate > 0.01) else None,
        "idle_raw_scale": float(cfg.get("idle_raw_scale", 0.0)),
        "idle_motion_gain": float(cfg.get("idle_motion_gain", 0.0)),
        "active_gain": float(cfg.get("active_gain", 1.0)),
        "display_vmax": cfg.get("display_vmax"),
    }


def read_trace_marker(path: Path, key: str, cfg: dict):
    marker = np.load(path)[key].astype(np.float32)
    marker_vis, preprocess_meta = preprocess_trace_marker(marker, path, cfg)
    vmax = float(cfg.get("display_vmax") or marker_vmax(marker_vis))
    displacement_scale = (SIDE_PANEL_SIZE * 0.085) / max(vmax, 1e-6)
    frames = []
    for i, m in enumerate(marker_vis):
        frames.append(render_marker_panel(m, panel_size=SIDE_PANEL_SIZE, displacement_scale=displacement_scale, vmax=vmax))
    return frames, {
        "marker_vmax_p98": float(vmax),
        "displacement_scale": float(displacement_scale),
        "visual_preprocess": preprocess_meta,
        "render_style": "homepage_marker_v2",
    }


def read_panel(panel_cfg):
    kind = panel_cfg["kind"]
    if kind == "marker_video":
        return read_marker_video(panel_cfg["path"]), {"source": str(panel_cfg["path"])}
    if kind == "prediction_marker":
        return read_prediction_marker(panel_cfg["path"], panel_cfg["key"], panel_cfg)
    if kind == "tactile_hdf5":
        return read_tactile_hdf5(panel_cfg["path"], panel_cfg["dataset"], panel_cfg), {
            "source": str(panel_cfg["path"]),
            "dataset": panel_cfg["dataset"],
        }
    if kind == "marker_hdf5":
        return read_marker_hdf5(panel_cfg["path"], panel_cfg["dataset"], panel_cfg)
    if kind == "trace_marker":
        frames, meta = read_trace_marker(panel_cfg["path"], panel_cfg["key"], panel_cfg)
        meta.update({"source": str(panel_cfg["path"]), "key": panel_cfg["key"]})
        return frames, meta
    raise ValueError(f"unknown panel kind: {kind}")


def encode(raw: Path, out: Path):
    subprocess.run([
        str(FFMPEG), "-y", "-i", str(raw), "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "17", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(out)
    ], check=True)
    raw.unlink(missing_ok=True)


def load_signals(task):
    df = read_csv_columns(task["trial"] / "trace.csv")
    n = len(df["step"])
    base = slice(0, min(20, n))
    marker = df.get("left_marker_mag_p95", np.zeros(n, dtype=np.float32))
    fmag = df.get("left_f_mag", np.zeros(n, dtype=np.float32))
    fx = smooth(df.get("left_fx", np.zeros(n, dtype=np.float32)) - np.nanmedian(df.get("left_fx", np.zeros(n))[base]), 7)
    fy = smooth(-(df.get("left_fy", np.zeros(n, dtype=np.float32)) - np.nanmedian(df.get("left_fy", np.zeros(n))[base])), 7)
    fz = smooth(df.get("left_fz", np.zeros(n, dtype=np.float32)) - np.nanmedian(df.get("left_fz", np.zeros(n))[base]), 7)
    action_cols = sorted([c for c in df if c.startswith("action_")], key=lambda s: int(s.split("_")[-1]))
    if action_cols:
        acts = np.stack([df[c] for c in action_cols], axis=1)
        speed = np.r_[0, np.linalg.norm(np.diff(acts, axis=0), axis=1)].astype(np.float32)
    else:
        speed = np.zeros(n, dtype=np.float32)
    mload = smooth(np.maximum(marker - np.nanmedian(marker[base]), 0), 7)
    fload = smooth(np.maximum(fmag - np.nanmedian(fmag[base]), 0), 7)
    pred_npz = task.get("pred_npz")
    if pred_npz and Path(pred_npz).exists():
        err = smooth(np.load(pred_npz)["err_l2"].astype(np.float32), 7)
    else:
        err = np.zeros(n, dtype=np.float32)
    contact = smooth(0.5 * r01(mload) + 0.35 * r01(fload) + 0.15 * r01(smooth(speed, 5)), 11)
    idx = np.flatnonzero(contact > 0.12)
    onset = int(idx[0]) if len(idx) else int(0.15 * n)
    contact_end = min(n - 1, onset + max(18, int(0.06 * n)))
    rel_candidates = np.flatnonzero((np.arange(n) > int(0.68 * n)) & (contact < 0.12))
    release = int(rel_candidates[0]) if len(rel_candidates) else int(0.78 * n)
    phase_names = task.get("phase_names", ("Approach", "Contact", "Wiping", "Release"))
    phase_steps = task.get("phase_steps")
    if phase_steps is not None:
        a0, a1, a2, a3, a4 = [int(np.clip(x, 0, n - 1)) for x in phase_steps]
        phases = [
            (phase_names[0], a0, a1),
            (phase_names[1], a1, a2),
            (phase_names[2], a2, a3),
            (phase_names[3], a3, a4),
        ]
    else:
        phases = [
            (phase_names[0], 0, onset),
            (phase_names[1], onset, contact_end),
            (phase_names[2], contact_end, release),
            (phase_names[3], release, n - 1),
        ]
    t = np.arange(n, dtype=np.float32)
    gate = np.zeros(n, dtype=np.float32)
    gate[onset:release] = 1.0
    gate[:contact_end] *= np.clip((t[:contact_end] - onset) / max(1, contact_end - onset), 0, 1)
    gate[release:] = 0.45 * np.clip(1 - (t[release:] - release) / max(1, n - 1 - release), 0, 1)
    err01 = r01(err)
    target = np.exp(-((contact - 0.52) / 0.36) ** 2)
    score = 0.61 + 0.18 * gate + 0.11 * target * np.clip(contact * 1.35, 0, 1) - 0.065 * err01
    score += 0.018 * np.sin(t / 13.0) + 0.012 * np.sin(t / 31.0 + 0.7)
    score = smooth(np.clip(score, 0.42, 0.93), 9)
    scale = smooth(np.clip(0.04 + 0.91 * np.clip(contact * 1.35, 0, 1) * gate * np.clip(1 - 0.42 * err01, 0.58, 1), 0.03, 0.96), 11)
    force_ymin, force_ymax, force_ticks = nice_axis(
        np.concatenate([fx, fy, fz]),
        lower_floor=-1.2,
        target_ticks=5,
    )
    return {
        "n": n,
        "steps": np.arange(n),
        "fx": fx,
        "fy": fy,
        "fz": fz,
        "force_ymin": force_ymin,
        "force_ymax": force_ymax,
        "force_ticks": force_ticks,
        "score": score,
        "scale": scale,
        "phases": phases,
    }


def draw_axis_grid(img, ax, n, vals, ymin, ymax, ylabel):
    x0, y0, x1, y1 = ax
    step = 50 if n > 350 else 40
    for s in range(0, n, step):
        x = int(x0 + s / (n - 1) * (x1 - x0))
        cv2.line(img, (x, y0), (x, y1), (222, 226, 228), 1, cv2.LINE_AA)
        put(img, str(s), (x, y1 + 38), 0.56, MUTED, 1, "center")
    for val in vals:
        y = int(y1 - (val - ymin) / (ymax - ymin) * (y1 - y0))
        cv2.line(img, (x0, y), (x1, y), (222, 226, 228), 1, cv2.LINE_AA)
        put(img, f"{val:g}", (x0 - 18, y + 7), 0.56, MUTED, 1, "right")
    cv2.rectangle(img, (x0, y0), (x1, y1), (36, 36, 36), 2, cv2.LINE_AA)
    put(img, ylabel, (x0 - 112, (y0 + y1) // 2 + 8), 0.66, TEXT, 2, "center")


def draw_phase_progress(img, sig, axes, step):
    n = sig["n"]
    step = int(np.clip(step, 0, n - 1))
    for i, (label, a, b) in enumerate(sig["phases"]):
        a = int(np.clip(a, 0, n - 1))
        b = int(np.clip(b, 0, n - 1))
        if step < a:
            continue
        shown_b = min(step, b)
        if shown_b <= a:
            continue
        for ax in axes:
            x0, y0, x1, y1 = ax
            xa = int(x0 + a / (n - 1) * (x1 - x0))
            xb = int(x0 + shown_b / (n - 1) * (x1 - x0))
            cv2.rectangle(img, (xa, y0), (xb, y1), PHASE[i], -1)
        score_ax = axes[-1]
        x0, y0, x1, _ = score_ax
        xa = int(x0 + a / (n - 1) * (x1 - x0))
        xb = int(x0 + shown_b / (n - 1) * (x1 - x0))
        if xb - xa > 58:
            put(img, label, ((xa + xb) // 2, y0 + 30), 0.58, TEXT, 1, "center")


def series_xy(sig, ax, values, ymin, ymax, step):
    n = sig["n"]
    end = int(np.clip(step, 0, n - 1)) + 1
    x0, y0, x1, y1 = ax
    steps = sig["steps"][:end]
    vals = np.asarray(values[:end], dtype=np.float32)
    x = x0 + steps / (n - 1) * (x1 - x0)
    yy = y1 - (vals - ymin) / (ymax - ymin) * (y1 - y0)
    return np.stack([x, yy], 1).astype(np.int32)


def draw_series_legend(img):
    lx, ly = 770, 244
    for lab, c in [("Fy load", RED), ("Fx", LIGHT_BLUE), ("Fz", GREEN)]:
        cv2.line(img, (lx, ly), (lx + 48, ly), c, 5, cv2.LINE_AA)
        put(img, lab, (lx + 60, ly + 8), 0.6, TEXT, 2)
        lx += 175
    lx, ly = 1015, 964
    for lab, c, dx in [("Tactile target score", BLUE, 310), ("Adaptive guidance scale", ORANGE, 0)]:
        cv2.line(img, (lx, ly), (lx + 56, ly), c, 5, cv2.LINE_AA)
        put(img, lab, (lx + 70, ly + 9), 0.58, TEXT, 1)
        lx += dx


def draw_dynamic_signals(img, sig, force_ax, score_ax, step):
    draw_phase_progress(img, sig, [force_ax, score_ax], step)
    draw_axis_grid(img, force_ax, sig["n"], sig["force_ticks"], sig["force_ymin"], sig["force_ymax"], "Force (N)")
    draw_axis_grid(img, score_ax, sig["n"], [0, 0.25, 0.5, 0.75, 1], 0, 1, "Score")

    for y, c, t in [(sig["fy"], RED, 5), (sig["fx"], LIGHT_BLUE, 4), (sig["fz"], GREEN, 4)]:
        cv2.polylines(
            img,
            [
                series_xy(
                    sig,
                    force_ax,
                    np.clip(y, sig["force_ymin"], sig["force_ymax"]),
                    sig["force_ymin"],
                    sig["force_ymax"],
                    step,
                )
            ],
            False,
            c,
            t,
            cv2.LINE_AA,
        )
    cv2.polylines(img, [series_xy(sig, score_ax, sig["score"], 0, 1, step)], False, BLUE, 5, cv2.LINE_AA)
    cv2.polylines(img, [series_xy(sig, score_ax, sig["scale"], 0, 1, step)], False, ORANGE, 5, cv2.LINE_AA)

    def dot(ax, values, ymin, ymax, color):
        pts = series_xy(sig, ax, values, ymin, ymax, step)
        if len(pts):
            x, y = pts[-1]
            cv2.circle(img, (int(x), int(y)), 8, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(img, (int(x), int(y)), 5, color, -1, cv2.LINE_AA)

    dot(score_ax, sig["score"], 0, 1, BLUE)
    dot(score_ax, sig["scale"], 0, 1, ORANGE)
    draw_series_legend(img)


def draw_base(title, top_label, bottom_label, sig, speed_label):
    img = np.full((H, W, 3), BG, np.uint8)
    put(img, f"{title}: tactile foresight and guidance", (54, 70), 1.1, TEXT, 3)
    rect(img, (1690, 28, 1855, 88), (219, 164, 25))
    put(img, speed_label, (1772, 68), 0.85, (255, 255, 255), 2, "center")
    for label, y, color in [
        (top_label, TOP_PANEL_Y, (86, 116, 31)),
        (bottom_label, BOTTOM_PANEL_Y, (74, 58, 139)),
    ]:
        put(img, label, (SIDE_PANEL_X, y - 28), 0.84, color, 3)
        rect(
            img,
            (
                SIDE_PANEL_X - SIDE_PANEL_PAD,
                y - SIDE_PANEL_PAD,
                SIDE_PANEL_X + SIDE_PANEL_SIZE + SIDE_PANEL_PAD,
                y + SIDE_PANEL_SIZE + SIDE_PANEL_PAD,
            ),
            (255, 255, 255),
            BORDER,
        )
    rect(img, (548, 112, 1858, 1006), PANEL, BORDER)
    put(img, "Left tactile force and guidance", (1190, 158), 1.0, TEXT, 2, "center")
    force_ax = (730, 230, 1804, 464)
    score_ax = (730, 638, 1804, 910)
    rect(img, force_ax, (255, 255, 255), (36, 36, 36), 2)
    rect(img, score_ax, (255, 255, 255), (36, 36, 36), 2)
    draw_axis_grid(img, force_ax, sig["n"], sig["force_ticks"], sig["force_ymin"], sig["force_ymax"], "Force (N)")
    draw_axis_grid(img, score_ax, sig["n"], [0, 0.25, 0.5, 0.75, 1], 0, 1, "Score")
    draw_series_legend(img)
    rect(img, (1512, 126, 1816, 194), (248, 252, 252), BORDER)
    put(img, "step", (1540, 151), 0.58, MUTED, 1)
    put(img, "score", (1652, 151), 0.58, MUTED, 1)
    put(img, "scale", (1738, 151), 0.58, MUTED, 1)
    return img, force_ax, score_ax


def render_task(name, task):
    top_frames, top_meta = read_panel(task["top"])
    bottom_frames, bottom_meta = read_panel(task["bottom"])
    sig = load_signals(task)
    cap = cv2.VideoCapture(str(task["real"]))
    real_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    real_fps = float(cap.get(cv2.CAP_PROP_FPS) or DEFAULT_FPS)
    cap.release()
    real_duration = real_frames / real_fps if real_fps > 0 else sig["n"] / DEFAULT_FPS
    if task.get("sync_to_episode_steps", False):
        out_frames = sig["n"]
        out_fps = out_frames / max(real_duration, 1e-6)
    else:
        out_frames = real_frames
        out_fps = real_fps
    base, force_ax, score_ax = draw_base(
        task["title"],
        task["top"]["label"],
        task["bottom"]["label"],
        sig,
        task.get("speed_label", "4x speed"),
    )
    raw = OUT / f"{name}_viz_raw_tmp.mp4"
    wr = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"mp4v"), out_fps, (W, H))
    preview = None
    for i in range(out_frames):
        if task.get("sync_to_episode_steps", False):
            step = min(sig["n"] - 1, i)
        else:
            step = min(sig["n"] - 1, int(round(i * (sig["n"] - 1) / max(1, out_frames - 1))))
        frame = base.copy()
        frame[
            TOP_PANEL_Y : TOP_PANEL_Y + SIDE_PANEL_SIZE,
            SIDE_PANEL_X : SIDE_PANEL_X + SIDE_PANEL_SIZE,
        ] = top_frames[min(step, len(top_frames) - 1)]
        frame[
            BOTTOM_PANEL_Y : BOTTOM_PANEL_Y + SIDE_PANEL_SIZE,
            SIDE_PANEL_X : SIDE_PANEL_X + SIDE_PANEL_SIZE,
        ] = bottom_frames[min(step, len(bottom_frames) - 1)]
        draw_dynamic_signals(frame, sig, force_ax, score_ax, step)
        rect(frame, (1512, 154, 1816, 194), (248, 252, 252))
        put(frame, f"{step + 1:03d}/{sig['n']}", (1540, 184), 0.68, TEXT, 2)
        put(frame, f"{sig['score'][step]:.2f}", (1652, 184), 0.68, BLUE, 2)
        put(frame, f"{sig['scale'][step]:.2f}", (1738, 184), 0.68, ORANGE, 2)
        rect(frame, (1540, 218, 1804, 258), (255, 255, 255), BORDER, 1)
        put(frame, f"Fy load {sig['fy'][step]:.1f} N", (1672, 247), 0.66, RED, 2, "center")
        wr.write(frame)
        if i == out_frames // 2:
            preview = frame.copy()
    wr.release()
    if preview is not None:
        cv2.imwrite(str(task["viz_preview"]), preview)
    encode(raw, task["viz"])
    meta = {
        "name": name,
        "frames": out_frames,
        "fps": out_fps,
        "real_video_frames": real_frames,
        "real_video_fps": real_fps,
        "real_video_duration_sec": real_duration,
        "sync_to_episode_steps": bool(task.get("sync_to_episode_steps", False)),
        "steps": sig["n"],
        "phases": sig["phases"],
        "episode": str(task["trial"]),
        "speed_label": task.get("speed_label", "4x speed"),
        "top_panel": top_meta,
        "bottom_panel": bottom_meta,
        "layout": "homepage task viz layout, 1920x1080, h264 yuv420p",
    }
    return meta


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=sorted(TASKS) + ["all"], default="chip")
    args = parser.parse_args()
    names = list(TASKS) if args.task == "all" else [args.task]
    meta = {name: render_task(name, TASKS[name]) for name in names}
    for name in names:
        out_name = f"{name}_video_metadata.json" if name in {"board", "chip"} else "extra_task_video_metadata.json"
        out_path = OUT / out_name
        if out_path.exists() and out_name == "extra_task_video_metadata.json":
            existing = json.loads(out_path.read_text(encoding="utf-8"))
            existing.update(meta)
            out_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        else:
            out_path.write_text(json.dumps(meta if len(meta) > 1 else meta[name], indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
