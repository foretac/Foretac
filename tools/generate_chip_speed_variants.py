#!/usr/bin/env python3
"""Create labelled 1X and 4X chip demo video pairs from the current web videos."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import cv2


ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = ROOT / "static/videos"
FFMPEG = "ffmpeg"


def put_centered(img, text: str, center: tuple[int, int], scale: float) -> None:
    size, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)
    x = int(center[0] - size[0] / 2)
    y = int(center[1])
    cv2.putText(
        img,
        text,
        (x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )


def add_badge(frame, kind: str, label: str):
    height, width = frame.shape[:2]
    if kind == "real":
        expected = (1280, 720)
        box = (1104, 24, 1252, 66)
        text_center = (1178, 54)
        scale = 0.78
    elif kind == "viz":
        expected = (1920, 1080)
        box = (1690, 28, 1855, 88)
        text_center = (1772, 68)
        scale = 0.85
    else:
        raise ValueError(f"unknown video kind: {kind}")
    if (width, height) != expected:
        raise RuntimeError(f"{kind} input is {width}x{height}, expected {expected[0]}x{expected[1]}")
    x1, y1, x2, y2 = box
    cv2.rectangle(frame, (x1, y1), (x2, y2), (219, 164, 25), thickness=-1)
    put_centered(frame, label, text_center, scale)
    return frame


def encode_h264(
    source: Path,
    destination: Path,
    *,
    speed: int,
    output_fps: float | None = None,
) -> None:
    vf = f"setpts=PTS/{speed}" if speed != 1 else "null"
    command = [FFMPEG, "-y", "-loglevel", "error", "-i", str(source), "-vf", vf]
    if output_fps is None:
        command += ["-vsync", "0"]
    else:
        command += ["-r", f"{output_fps:.9f}"]
    command += [
        "-an",
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
        str(destination),
    ]
    subprocess.run(command, check=True)


def render_labelled(source: Path, destination: Path, kind: str, label: str, fps: float) -> None:
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open {source}")
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    raw = destination.with_name(destination.stem + "_labelled_raw.mp4")
    writer = cv2.VideoWriter(
        str(raw), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )
    frames = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        writer.write(add_badge(frame, kind, label))
        frames += 1
    capture.release()
    writer.release()
    if frames == 0:
        raw.unlink(missing_ok=True)
        raise RuntimeError(f"no frames read from {source}")
    encode_h264(raw, destination, speed=1)
    raw.unlink(missing_ok=True)
    print(f"{destination.name}: {frames} frames at {fps:.6f} fps")


def make_variant(kind: str, speed: int, source: Path, output: Path, tmpdir: Path) -> None:
    labelled = tmpdir / f"chip_{kind}_1X.mp4"
    capture = cv2.VideoCapture(str(source))
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 24.0)
    capture.release()
    render_labelled(source, labelled, kind, f"{speed}x speed" if speed == 4 else "1x speed", fps)
    if speed == 1:
        labelled.replace(output)
        return
    encode_h264(labelled, output, speed=speed, output_fps=fps * speed)


def relabel_1x_as_4x(kind: str, tmpdir: Path) -> None:
    source = VIDEO_DIR / f"chip_{kind}_1X.mp4"
    output = VIDEO_DIR / f"chip_{kind}_1x4x.mp4"
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate", "-of", "json", str(source),
    ]))
    frame_rate = probe["streams"][0]["r_frame_rate"]
    capture = cv2.VideoCapture(str(source))
    ok, frame = capture.read()
    capture.release()
    if not ok:
        raise RuntimeError(f"cannot read first frame from {source}")

    labelled = add_badge(frame.copy(), kind, "4x speed")
    badge = cv2.cvtColor(labelled, cv2.COLOR_BGR2BGRA)
    badge[:, :, 3] = 0
    box = (1104, 24, 1252, 66) if kind == "real" else (1690, 28, 1855, 88)
    x1, y1, x2, y2 = box
    badge[y1:y2 + 1, x1:x2 + 1, 3] = 255
    badge_path = tmpdir / f"chip_{kind}_badge.png"
    if not cv2.imwrite(str(badge_path), badge):
        raise RuntimeError(f"cannot write {badge_path}")

    # Overlay the badge while retaining the source video's timestamps.
    subprocess.run([
        FFMPEG, "-y", "-loglevel", "error", "-i", str(source),
        "-loop", "1", "-framerate", frame_rate, "-i", str(badge_path),
        "-filter_complex", "[0:v][1:v]overlay=0:0:shortest=1[v]",
        "-map", "[v]", "-vsync", "0", "-enc_time_base", "-1", "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output),
    ], check=True)
    preview = VIDEO_DIR / f"chip_{kind}_1x4x_preview.jpg"
    if not cv2.imwrite(str(preview), labelled, [cv2.IMWRITE_JPEG_QUALITY, 92]):
        raise RuntimeError(f"cannot write {preview}")
    print(f"{output.name}: kept {source.name} timeline, added 4x speed badge")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--relabel-1x-as-4x", action="store_true",
        help="Create _1x4x files from _1X files, changing only the speed badge.",
    )
    args = parser.parse_args()
    sources = {
        "real": VIDEO_DIR / "chip_real.mp4",
        "viz": VIDEO_DIR / "chip_viz.mp4",
    }
    with tempfile.TemporaryDirectory(prefix="foretac_chip_speed_") as tmp:
        tmpdir = Path(tmp)
        if args.relabel_1x_as_4x:
            for kind in sources:
                relabel_1x_as_4x(kind, tmpdir)
            return
        for speed in (1, 4):
            for kind, source in sources.items():
                make_variant(
                    kind,
                    speed,
                    source,
                    VIDEO_DIR / f"chip_{kind}_{speed}X.mp4",
                    tmpdir,
                )


if __name__ == "__main__":
    main()
