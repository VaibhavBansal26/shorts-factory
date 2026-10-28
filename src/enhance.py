"""Optional clean-up of a face-cam recording: replace or blur the background and balance the lighting/colour.

Person segmentation runs locally (MediaPipe selfie model, bundled in assets/models), so nothing leaves the machine.
Clothes can't be changed reliably on video, so this does background and lighting only.
"""
import re
import subprocess
from pathlib import Path

import cv2
import numpy as np

from .config import CODE
from .ff import FFMPEG

MODEL = CODE / "assets" / "models" / "selfie_segmenter.tflite"
BACKGROUNDS = ("none", "blur", "studio", "clean")


def _size(src: Path) -> tuple[int, int]:
    err = subprocess.run([FFMPEG, "-hide_banner", "-i", str(src)], capture_output=True, text=True).stderr
    m = re.search(r"Video:.*?, (\d{2,5})x(\d{2,5})", err)
    return int(m.group(1)), int(m.group(2))


def _backdrop(kind: str, w: int, h: int, accent=(96, 165, 250)) -> np.ndarray:
    """Generated backdrops, so there are no image licences to worry about. RGB uint8."""
    y = np.linspace(0, 1, h)[:, None, None]
    x = np.linspace(0, 1, w)[None, :, None]
    if kind == "clean":  # soft light wall
        base = np.array([232, 236, 242]) * (1 - 0.18 * y) + np.array([205, 214, 228]) * 0.18 * y
        base = base * (1 - 0.10 * (x - 0.5) ** 2 * 4)
        return np.clip(np.broadcast_to(base, (h, w, 3)), 0, 255).astype(np.uint8)
    top, bot = np.array([16, 26, 58]), np.array([34, 58, 118])  # studio: navy gradient with bokeh and a rim of light
    img = np.ascontiguousarray(np.broadcast_to(top * (1 - y) + bot * y, (h, w, 3))).astype(np.float32)
    rng = np.random.default_rng(4)
    glow = np.zeros((h, w, 3), np.float32)
    for _ in range(26):
        c = (int(rng.uniform(0, w)), int(rng.uniform(0, h * 0.8)))
        r = int(rng.uniform(0.02, 0.07) * min(w, h))
        col = tuple(float(v) * rng.uniform(0.35, 0.8) for v in accent)
        cv2.circle(glow, c, r, col, -1, cv2.LINE_AA)
    glow = cv2.GaussianBlur(glow, (0, 0), max(6, min(w, h) * 0.012))
    img = img + glow * 0.55
    img *= (1 - 0.35 * ((x - 0.5) ** 2 + (y - 0.5) ** 2) * 2)  # vignette
    return np.clip(img, 0, 255).astype(np.uint8)


def _polish(frame: np.ndarray, mask: np.ndarray | None, state: dict) -> np.ndarray:
    """Even out exposure (aim for a well-lit face), lift contrast and add a little warmth. Uses lookup tables for speed."""
    small = cv2.resize(frame, (160, int(160 * frame.shape[0] / frame.shape[1])), interpolation=cv2.INTER_AREA)
    luma = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    if mask is not None:
        sm = cv2.resize(mask, (luma.shape[1], luma.shape[0]), interpolation=cv2.INTER_AREA)
        region = luma[sm > 0.6] if (sm > 0.6).sum() > 40 else luma.ravel()
    else:
        region = luma.ravel()
    mean = float(np.clip(region.mean(), 0.08, 0.9))
    state["mean"] = mean if "mean" not in state else 0.9 * state["mean"] + 0.1 * mean  # no flicker
    gamma = float(np.clip(np.log(0.46) / np.log(state["mean"]), 0.6, 1.5))
    x = np.arange(256, dtype=np.float32) / 255.0
    curve = np.clip(0.5 + (np.power(x, gamma) - 0.5) * 1.08, 0, 1) * 255  # exposure + contrast
    luts = [np.clip(curve * k, 0, 255).astype(np.uint8) for k in (1.02, 1.0, 0.98)]  # R, G, B: slightly warmer
    out = cv2.merge([cv2.LUT(frame[..., i], luts[i]) for i in range(3)])
    gray = cv2.cvtColor(cv2.cvtColor(out, cv2.COLOR_RGB2GRAY), cv2.COLOR_GRAY2RGB)
    return cv2.addWeighted(out, 1.10, gray, -0.10, 0)  # a touch more colour


def run(src: Path, out: Path, background: str = "studio", polish: bool = True, accent=(96, 165, 250)) -> Path:
    """Write `out`: same video and audio as `src` with the requested clean-up applied."""
    from mediapipe import Image as MpImage, ImageFormat
    from mediapipe.tasks.python import BaseOptions, vision

    w, h = _size(src)
    s = min(1.0, 1920 / max(w, h), 1080 / min(w, h))  # cap the working size for speed
    w, h = int(w * s) // 2 * 2, int(h * s) // 2 * 2
    seg = None
    if background in ("blur", "studio", "clean"):
        seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
            base_options=BaseOptions(model_asset_path=str(MODEL)), running_mode=vision.RunningMode.VIDEO,
            output_confidence_masks=True, output_category_mask=False))
    backdrop = _backdrop(background, w, h, accent) if background in ("studio", "clean") else None
    dec = subprocess.Popen([FFMPEG, "-loglevel", "error", "-i", str(src), "-vf", f"scale={w}:{h}", "-f", "rawvideo",
                            "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen([FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                            "-r", "30", "-i", "-", "-i", str(src), "-map", "0:v", "-map", "1:a", "-c:v", "libx264",
                            "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "copy",
                            str(out)], stdin=subprocess.PIPE)
    prev, state, n = None, {}, 0
    try:
        while True:
            buf = dec.stdout.read(w * h * 3)
            if len(buf) < w * h * 3:
                break
            frame = np.frombuffer(buf, np.uint8).reshape(h, w, 3).copy()
            mask = None
            if seg is not None:
                res = seg.segment_for_video(MpImage(image_format=ImageFormat.SRGB, data=frame), int(n * 1000 / 30))
                m = res.confidence_masks[-1].numpy_view().astype(np.float32).reshape(h, w)
                m = np.clip((m - 0.35) / 0.3, 0, 1)
                m = cv2.GaussianBlur(m, (0, 0), 2.5)
                m = m if prev is None else 0.65 * m + 0.35 * prev  # steady edges between frames
                prev = m
                mask = m
                bg = backdrop if backdrop is not None else cv2.GaussianBlur(frame, (0, 0), max(12, min(w, h) * 0.03))
                frame = cv2.blendLinear(frame, bg, mask, 1.0 - mask)
            if polish:
                frame = _polish(frame, mask, state)
            enc.stdin.write(frame.tobytes())
            n += 1
    finally:
        enc.stdin.close()
        enc.wait()
        dec.kill()
    if enc.returncode:
        raise RuntimeError("could not enhance the recording")
    return out
