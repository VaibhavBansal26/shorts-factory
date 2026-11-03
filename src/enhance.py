"""Optional clean-up of a face-cam recording: replace or blur the background and balance the lighting/colour.

Person segmentation runs locally (MediaPipe selfie model, bundled in assets/models), so nothing leaves the machine.
Clothes can't be changed reliably on video, so this does background and lighting only.
"""
import math
import re
import subprocess
from pathlib import Path

import cv2
import numpy as np

from .config import CODE
from .ff import FFMPEG

MODEL = CODE / "assets" / "models" / "selfie_segmenter.tflite"
BACKGROUNDS = ("none", "blur", "studio", "clean", "office", "cafe", "conference")


def _size(src: Path) -> tuple[int, int]:
    err = subprocess.run([FFMPEG, "-hide_banner", "-i", str(src)], capture_output=True, text=True).stderr
    m = re.search(r"Video:.*?, (\d{2,5})x(\d{2,5})", err)
    return int(m.group(1)), int(m.group(2))


def _backdrop(kind: str, w: int, h: int, accent=(96, 165, 250)) -> np.ndarray:
    """Generated backdrops, so there are no image licences to worry about. RGB uint8."""
    y = np.linspace(0, 1, h)[:, None, None]
    x = np.linspace(0, 1, w)[None, :, None]
    if kind in ("office", "cafe", "conference"):
        return _scene(kind, w, h, accent)
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


def _scene(kind: str, w: int, h: int, accent=(96, 165, 250)) -> np.ndarray:
    """Out-of-focus rooms drawn from shapes (no photos, so no licences): office, cafe, conference. RGB uint8."""
    rng = np.random.default_rng({"office": 11, "cafe": 21, "conference": 31}[kind])
    img = np.zeros((h, w, 3), np.float32)
    glow = np.zeros((h, w, 3), np.float32)
    yy = np.linspace(0, 1, h)[:, None, None]
    if kind == "office":
        img[:] = np.array([206, 204, 198]) * (1 - 0.25 * yy) + np.array([150, 150, 150]) * 0.25 * yy       # warm grey wall
        x0, x1 = int(w * 0.04), int(w * 0.58)                                                         # big window
        sky = np.array([170, 205, 238]) * (1 - np.linspace(0, 1, int(h * 0.62))[:, None, None]) + np.array([225, 236, 246]) * np.linspace(0, 1, int(h * 0.62))[:, None, None]
        img[int(h * 0.06):int(h * 0.06) + sky.shape[0], x0:x1] = sky
        base = int(h * 0.06) + sky.shape[0]
        for i in range(14):                                                                            # skyline
            bw = int(rng.uniform(0.04, 0.09) * w)
            bx = int(x0 + rng.uniform(0, 1) * (x1 - x0 - bw))
            bh = int(rng.uniform(0.12, 0.42) * h)
            img[max(0, base - bh):base, bx:bx + bw] = np.array([120, 140, 168]) * rng.uniform(0.75, 1.1)
            for wy in range(base - bh + 14, base - 8, 26):
                for wx in range(bx + 8, bx + bw - 8, 20):
                    if rng.random() < 0.3:
                        glow[wy:wy + 8, wx:wx + 8] += np.array([255, 235, 170]) * 0.8
        for fx in (x0, (x0 + x1) // 2, x1 - 6):                                                       # window frame
            img[int(h * 0.05):base + 8, fx:fx + 6] = (70, 70, 74)
        img[int(h * 0.05):int(h * 0.05) + 6, x0:x1] = (70, 70, 74)
        img[base:base + 8, x0:x1] = (70, 70, 74)
        sx = int(w * 0.66)                                                                             # bookshelf
        img[int(h * 0.12):int(h * 0.62), sx:int(w * 0.97)] = (92, 70, 52)
        for r in range(4):
            y = int(h * 0.14) + r * int(h * 0.115)
            x = sx + 10
            while x < w * 0.95:
                bw = int(rng.uniform(0.012, 0.03) * w)
                col = np.array(rng.choice([(180, 70, 60), (60, 100, 160), (220, 200, 120), (80, 130, 90), (235, 235, 230)]), np.float32)
                img[y:y + int(h * 0.09), x:x + bw] = col * rng.uniform(0.7, 1.0)
                x += bw + 3
        px, py = int(w * 0.62), int(h * 0.66)                                                          # plant
        for k in range(26):
            cx, cy, r = px + rng.normal(0, w * 0.04), py - abs(rng.normal(0, h * 0.06)), rng.uniform(0.02, 0.05) * w
            yy_, xx_ = np.ogrid[:h, :w]
            m = ((yy_ - cy) ** 2 + (xx_ - cx) ** 2) < r * r
            img[m] = np.array([50, 110, 62]) * rng.uniform(0.7, 1.2)
        img[int(h * 0.78):] = np.array([112, 86, 62]) * (1 - 0.3 * yy[int(h * 0.78):])               # desk
        glow[int(h * 0.7):int(h * 0.78), int(w * 0.1):int(w * 0.5)] += np.array([120, 170, 230]) * 0.6  # monitor glow
    elif kind == "cafe":
        img[:] = np.array([118, 78, 52]) * (1 - 0.35 * yy) + np.array([60, 38, 28]) * 0.35 * yy        # warm brown wall
        img[:int(h * 0.55), :int(w * 0.34)] = np.array([226, 214, 190])                                # daylight window
        img[:int(h * 0.55), int(w * 0.34):int(w * 0.35)] = (50, 34, 26)
        for r in range(3):                                                                             # shelves with cups and jars
            y = int(h * (0.18 + r * 0.15))
            img[y + int(h * 0.075):y + int(h * 0.085), int(w * 0.46):int(w * 0.98)] = (160, 118, 78)
            x = int(w * 0.48)
            while x < w * 0.94:
                bw, bh = int(rng.uniform(0.025, 0.06) * w), int(rng.uniform(0.03, 0.074) * h)
                img[y + int(h * 0.075) - bh:y + int(h * 0.075), x:x + bw] = np.array(rng.choice([(235, 225, 205), (70, 110, 90), (190, 80, 60), (240, 190, 90)]), np.float32)
                x += bw + int(rng.uniform(4, 24))
        for k in range(46):                                                                            # string lights: warm bokeh
            cx, cy = rng.uniform(0, w), h * (0.06 + 0.07 * math.sin(k * 0.7) + rng.uniform(0, 0.05))
            r = rng.uniform(0.012, 0.03) * w
            yy_, xx_ = np.ogrid[:h, :w]
            m = ((yy_ - cy) ** 2 + (xx_ - cx) ** 2) < r * r
            glow[m] += np.array([255, 196, 110]) * rng.uniform(0.7, 1.2)
        img[int(h * 0.8):] = np.array([86, 56, 38]) * (1 - 0.25 * yy[int(h * 0.8):])                  # table
    else:  # conference: dark hall, big LED screen, stage lights, rows of chairs
        img[:] = np.array([12, 16, 36]) * (1 - yy) + np.array([22, 30, 66]) * yy
        sx0, sx1, sy0, sy1 = int(w * 0.12), int(w * 0.88), int(h * 0.08), int(h * 0.36)
        for i in range(sx1 - sx0):
            t = i / (sx1 - sx0)
            img[sy0:sy1, sx0 + i] = np.array(accent) * (0.45 + 0.5 * t) * 0.9 + np.array([30, 20, 80]) * (1 - t)
        glow[sy0 - 30:sy1 + 30, sx0 - 30:sx1 + 30] += np.array(accent) * 0.25
        for k in range(10):                                                                            # stage lights and beams
            cx = (k + 0.5) / 10 * w
            yy_, xx_ = np.ogrid[:h, :w]
            beam = np.clip(1 - np.abs(xx_ - (cx + (yy_ - 0) * 0.12 * (k - 4.5) / 4.5)) / (30 + yy_ * 0.12), 0, 1) * np.clip(1 - yy_ / (h * 0.7), 0, 1)
            glow += (beam[..., None] * np.array([90, 120, 255]) * 0.10)
            glow[int(h * 0.02):int(h * 0.05), int(cx) - 12:int(cx) + 12] += (255, 255, 255)
        for r in range(5):                                                                             # chair rows (silhouettes)
            y = int(h * (0.58 + r * 0.075))
            for x in range(-10, w, int(w * 0.11) + r * 6):
                img[y:y + int(h * 0.07), x:x + int(w * 0.085)] = np.array([8, 10, 26]) * (1 + r * 0.12)
    img = img + glow
    blurred = cv2.GaussianBlur(np.clip(img, 0, 255), (0, 0), max(10, min(w, h) * 0.018))                # shallow depth of field
    blurred += rng.normal(0, 1.4, blurred.shape)                                                       # a little grain so it matches camera noise
    vig = 1 - 0.28 * (((np.linspace(0, 1, w)[None, :] - 0.5) ** 2 + (np.linspace(0, 1, h)[:, None] - 0.5) ** 2) * 2)[..., None]
    return np.clip(blurred * vig, 0, 255).astype(np.uint8)


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


def _guided(guide: np.ndarray, p: np.ndarray, r: int, eps: float) -> np.ndarray:
    """Edge-aware smoothing of `p` that follows the edges of `guide` (guided filter): pulls the coarse person mask onto the
    real outline of hair and shoulders."""
    box = lambda x: cv2.boxFilter(x, -1, (2 * r + 1, 2 * r + 1))  # noqa: E731
    mi, mp = box(guide), box(p)
    cov = box(guide * p) - mi * mp
    var = box(guide * guide) - mi * mi
    a = cov / (var + eps)
    b = mp - a * mi
    return box(a) * guide + box(b)


def refine_matte(frame: np.ndarray, m: np.ndarray, bg: np.ndarray, prev: np.ndarray | None):
    """Turn the segmenter's soft mask into a clean alpha and a cleaned foreground: tight edge that follows hair, no halo of the
    old background, and a touch of the new background's light on the outline. Returns (alpha, foreground, state)."""
    h, w = m.shape
    guide = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    r = max(5, int(min(h, w) * 0.010))
    a = np.clip(_guided(guide, np.clip((m - 0.2) / 0.6, 0, 1), r, 2e-3), 0, 1)
    a = np.clip((a - 0.30) / 0.45, 0, 1)
    a = a * a * (3 - 2 * a)                                                  # firm edge, still soft enough for hair
    a = cv2.erode(a, np.ones((3, 3), np.uint8))                              # trim the one-pixel fringe
    a = cv2.GaussianBlur(a, (0, 0), 0.8)
    if prev is not None:
        still = 1.0 - min(1.0, float(np.abs(a - prev).mean()) * 40)          # steady edges when you are still, no lag when you move
        a = a * (1 - 0.3 * still) + prev * (0.3 * still)
    core = cv2.erode((a > 0.97).astype(np.float32), np.ones((5, 5), np.uint8))
    sig = max(4, min(h, w) * 0.008)
    inner = cv2.GaussianBlur(frame.astype(np.float32) * core[..., None], (0, 0), sig)
    wgt = cv2.GaussianBlur(core, (0, 0), sig)[..., None]
    inner = inner / np.maximum(wgt, 1e-3)
    edge = (4 * a * (1 - a))[..., None]                                       # 1 on the outline, 0 inside and outside
    use = np.clip(edge * 2.4, 0, 1) * (wgt > 0.05)
    fg = frame.astype(np.float32) * (1 - use) + inner * use                   # replace edge pixels' old-room colour with inside colour
    wrap = cv2.GaussianBlur(bg.astype(np.float32), (0, 0), 25)
    fg = fg * (1 - 0.22 * edge) + wrap * (0.22 * edge)                        # light wrap: the new room's light on the outline
    return a, fg, a


def run(src: Path, out: Path, background: str = "studio", polish: bool = True, accent=(96, 165, 250), refine: bool = True) -> Path:
    """Write `out`: same video and audio as `src` with the requested clean-up applied."""
    from mediapipe import Image as MpImage, ImageFormat
    from mediapipe.tasks.python import BaseOptions, vision

    w, h = _size(src)
    s = min(1.0, 1920 / max(w, h), 1080 / min(w, h))  # cap the working size for speed
    w, h = int(w * s) // 2 * 2, int(h * s) // 2 * 2
    seg = None
    if background in BACKGROUNDS and background != "none":
        seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
            base_options=BaseOptions(model_asset_path=str(MODEL)), running_mode=vision.RunningMode.VIDEO,
            output_confidence_masks=True, output_category_mask=False))
    backdrop = _backdrop(background, w, h, accent) if background not in ("none", "blur") else None
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
                bg = backdrop if backdrop is not None else cv2.GaussianBlur(frame, (0, 0), max(12, min(w, h) * 0.03))
                if refine:  # tight edge that follows hair, no old-room halo
                    mask, fg, prev = refine_matte(frame, m, bg, prev)
                    frame = np.clip(fg * mask[..., None] + bg.astype(np.float32) * (1 - mask[..., None]), 0, 255).astype(np.uint8)
                else:
                    m = np.clip((m - 0.35) / 0.3, 0, 1)
                    m = cv2.GaussianBlur(m, (0, 0), 2.5)
                    m = m if prev is None else 0.65 * m + 0.35 * prev  # steady edges between frames
                    prev = mask = m
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
