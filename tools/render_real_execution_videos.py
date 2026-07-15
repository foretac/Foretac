#!/usr/bin/env python3
"""Render homepage real-execution videos with the board-demo visual template."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "static/videos"
FFMPEG = Path("/home/chenshuai/.local/lib/python3.13/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2")

W, H = 1280, 720
CENTER_W = 960
CENTER_X = (W - CENTER_W) // 2

TASKS = {
    "board": "Board Wiping",
    "vase": "Vase Wiping",
    "card": "Card Swiping",
    "chip": "Chip Grasping",
}


def put(img, text, xy, scale=0.82, color=(24, 24, 28), thick=2, align="left"):
    size, _ = cv2.getTextSize(str(text), cv2.FONT_HERSHEY_SIMPLEX, scale, thick)
    x, y = xy
    if align == "center":
        x -= size[0] // 2
    elif align == "right":
        x -= size[0]
    cv2.putText(img, str(text), (int(x), int(y)), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)


def filled_rect_alpha(img, box, color, alpha):
    x1, y1, x2, y2 = map(int, box)
    roi = img[y1:y2, x1:x2]
    overlay = np.full_like(roi, color, dtype=np.uint8)
    cv2.addWeighted(overlay, alpha, roi, 1.0 - alpha, 0, dst=roi)


def crop_center_ratio(frame, ratio=4 / 3):
    h, w = frame.shape[:2]
    crop_w = min(w, int(round(h * ratio)))
    crop_h = min(h, int(round(w / ratio)))
    if crop_w <= w and crop_w / h <= ratio + 1e-3:
        x0 = max(0, (w - crop_w) // 2)
        return frame[:, x0 : x0 + crop_w]
    y0 = max(0, (h - crop_h) // 2)
    return frame[y0 : y0 + crop_h, :]


def render_frame(frame, title):
    frame = cv2.resize(frame, (W, H), interpolation=cv2.INTER_AREA)

    bg = cv2.GaussianBlur(frame, (0, 0), 28)
    bg = cv2.addWeighted(bg, 0.78, np.full_like(bg, 236), 0.22, 0)

    center_crop = crop_center_ratio(frame, 4 / 3)
    center = cv2.resize(center_crop, (CENTER_W, H), interpolation=cv2.INTER_AREA)
    bg[:, CENTER_X : CENTER_X + CENTER_W] = center
    cv2.line(bg, (CENTER_X, 0), (CENTER_X, H), (238, 238, 238), 2, cv2.LINE_AA)
    cv2.line(bg, (CENTER_X + CENTER_W, 0), (CENTER_X + CENTER_W, H), (238, 238, 238), 2, cv2.LINE_AA)

    filled_rect_alpha(bg, (28, 24, 336, 69), (255, 255, 255), 0.88)
    put(bg, title, (48, 56), 0.82, (22, 22, 28), 2)

    filled_rect_alpha(bg, (1104, 24, 1252, 66), (219, 164, 25), 0.96)
    put(bg, "4x speed", (1178, 54), 0.78, (255, 255, 255), 2, "center")
    return bg


def encode(raw: Path, out: Path):
    if FFMPEG.exists():
        subprocess.run(
            [
                str(FFMPEG),
                "-y",
                "-i",
                str(raw),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-an",
                str(out),
            ],
            check=True,
        )
        raw.unlink(missing_ok=True)
    else:
        shutil.move(str(raw), str(out))


def render_video(name: str, source: Path):
    title = TASKS[name]
    out = OUT / f"{name}_real.mp4"
    preview = OUT / f"{name}_real_preview.jpg"

    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open {source}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    raw = OUT / f"{name}_real_template_tmp.mp4"
    writer = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    preview_frame = None
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        rendered = render_frame(frame, title)
        writer.write(rendered)
        if frames and i == frames // 2:
            preview_frame = rendered.copy()
        i += 1
    cap.release()
    writer.release()
    if i == 0:
        raw.unlink(missing_ok=True)
        raise RuntimeError(f"no frames read from {source}")
    encode(raw, out)
    if preview_frame is None:
        cap = cv2.VideoCapture(str(out))
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, i // 2))
        ok, preview_frame = cap.read()
        cap.release()
        if not ok:
            preview_frame = np.zeros((H, W, 3), dtype=np.uint8)
    cv2.imwrite(str(preview), preview_frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(f"{name}: {i} frames at {fps:.3f} fps -> {out}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True, help="Directory containing <task>_real.mp4 source videos")
    parser.add_argument("--task", nargs="+", choices=sorted(TASKS), default=["vase", "card", "chip"])
    args = parser.parse_args()

    for name in args.task:
        source = args.source_dir / f"{name}_real.mp4"
        render_video(name, source)


if __name__ == "__main__":
    main()
