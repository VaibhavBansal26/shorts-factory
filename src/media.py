"""Visuals beyond text: memes, stock video, and your own clip/image library.

Three sources a scene can use:
  meme    - an Imgflip template image; we draw the top/bottom text ourselves
  stock   - a Pexels portrait video (free licence; needs PEXELS_API_KEY)
  library - your own clips/images listed in assets/library.yaml (series moments, screen recordings, ...)
"""
import json
import os
import re
import subprocess
import time
from difflib import get_close_matches
from pathlib import Path

import requests
import yaml
from PIL import Image, ImageDraw, ImageFont

from .config import ROOT, resolve

CACHE = ROOT / "assets" / "cache"
LIB = ROOT / "assets" / "library.yaml"
BOX_W, BOX_H = 920, 670
MAX_CLIP_SECONDS = 8


# ---------------- library ----------------
def load_library() -> list[dict]:
    if not LIB.exists():
        return []
    return yaml.safe_load(LIB.read_text()) or []


def add_library(entry: dict):
    items = load_library()
    items = [i for i in items if i["id"] != entry["id"]]
    items.append(entry)
    LIB.parent.mkdir(parents=True, exist_ok=True)
    LIB.write_text(yaml.safe_dump(items, sort_keys=False))


# ---------------- memes ----------------
def meme_templates() -> list[dict]:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / "memes.json"
    if f.exists() and time.time() - f.stat().st_mtime < 86400:
        return json.loads(f.read_text())
    try:
        r = requests.get("https://api.imgflip.com/get_memes", timeout=20)
        memes = [m for m in r.json()["data"]["memes"] if m.get("box_count") == 2][:60]
        f.write_text(json.dumps(memes))
        return memes
    except Exception:
        return json.loads(f.read_text()) if f.exists() else []


def _match_meme(name: str) -> dict | None:
    memes = meme_templates()
    names = {m["name"].lower(): m for m in memes}
    hit = get_close_matches(name.lower(), names, n=1, cutoff=0.55)
    return names[hit[0]] if hit else None


def _download(url: str, dest: Path) -> Path:
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        dest.write_bytes(r.content)
    return dest


def draw_meme(base: Path, top: str, bottom: str, out: Path, font_path: str | None) -> Path:
    img = Image.open(base).convert("RGB")
    w = 900
    img = img.resize((w, int(img.height * w / img.width)))
    d = ImageDraw.Draw(img)

    def block(text, anchor_top):
        text = text.upper().strip()
        if not text:
            return
        size = 78
        while size > 30:
            f = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default(size=size)
            lines, cur = [], ""
            for word in text.split():
                t = f"{cur} {word}".strip()
                if d.textlength(t, font=f) <= w - 40 or not cur:
                    cur = t
                else:
                    lines.append(cur)
                    cur = word
            lines.append(cur)
            if len(lines) <= 2:
                break
            size -= 6
        lh = int(size * 1.1)
        y = 14 if anchor_top else img.height - 14 - lh * len(lines)
        for ln in lines:
            d.text((w / 2, y), ln, font=f, fill="white", anchor="mt", stroke_width=max(3, size // 12),
                   stroke_fill="black")
            y += lh

    block(top, True)
    block(bottom, False)
    img.save(out)
    return out


# ---------------- stock video ----------------
def stock_available() -> bool:
    return bool(os.getenv("PEXELS_API_KEY"))


def stock_video(query: str) -> Path | None:
    key = os.getenv("PEXELS_API_KEY")
    if not key:
        return None
    try:
        r = requests.get("https://api.pexels.com/videos/search", headers={"Authorization": key},
                         params={"query": query, "orientation": "portrait", "per_page": 5}, timeout=20)
        for v in r.json().get("videos", []):
            files = sorted((f for f in v["video_files"] if f.get("file_type") == "video/mp4"),
                           key=lambda f: abs((f.get("width") or 0) - 720))
            if files:
                return _download(files[0]["link"], CACHE / "stock" / f"{v['id']}.mp4")
    except Exception as e:
        print(f"  ! stock video failed: {e}")
    return None


# ---------------- prompt menu + resolution ----------------
def menu() -> str:
    lines = []
    lib = load_library()
    if lib:
        lines.append("LIBRARY (use library_id; the user's own clips/images):")
        for i in lib:
            lines.append(f"- {i['id']} [{i.get('kind', 'clip')}] {i.get('description', '')} "
                         f"(tags: {', '.join(i.get('tags', []))})")
    memes = meme_templates()
    if memes:
        lines.append("MEME TEMPLATES (use meme_template with top_text/bottom_text): "
                     + "; ".join(m["name"] for m in memes[:40]))
    if stock_available():
        lines.append("STOCK VIDEO available: give a short visual stock_query (e.g. 'server room', 'typing code').")
    return "\n".join(lines)


def _extract_frames(src: Path, start: float, dur: float, fps: int, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    vf = (f"fps={fps},scale={BOX_W}:{BOX_H}:force_original_aspect_ratio=increase,"
          f"crop={BOX_W}:{BOX_H}")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(start), "-t", f"{dur:.2f}", "-i", str(src),
                    "-an", "-vf", vf, "-q:v", "4", str(out_dir / "%04d.jpg")], check=True)
    return sorted(out_dir.glob("*.jpg"))


def prepare(cfg: dict, script: dict, timeline: dict, workdir: Path) -> dict[int, dict]:
    """Resolve each scene's `visual` into frames/an image. Returns {scene_index: media}. Never raises."""
    fps = cfg["video"]["fps"]
    font = next((p for p in ["/System/Library/Fonts/Supplemental/Impact.ttf", *cfg["video"]["fonts"]]
                 if Path(p).exists()), None)
    lib = {i["id"]: i for i in load_library()}
    out = {}
    for idx, sc in enumerate(script["scenes"]):
        v = sc.get("visual") or {}
        kind = v.get("type", "none")
        if kind == "none":
            continue
        span = timeline["scenes"][idx]
        dur = min(MAX_CLIP_SECONDS, span["end"] - span["start"] + 0.5)
        try:
            if kind == "meme":
                m = _match_meme(v.get("meme_template", ""))
                if not m:
                    continue
                base = _download(m["url"], CACHE / "memes" / f"{m['id']}{Path(m['url']).suffix}")
                p = draw_meme(base, v.get("top_text", ""), v.get("bottom_text", ""),
                              workdir / f"meme{idx}.png", font)
                out[idx] = {"kind": "image", "path": p}
            elif kind == "library":
                e = lib.get(v.get("library_id"))
                if not e:
                    continue
                f = resolve(cfg, e["file"])
                if e.get("kind", "clip") == "clip":
                    d = min(dur, e.get("duration", MAX_CLIP_SECONDS))
                    out[idx] = {"kind": "video", "frames": _extract_frames(
                        f, e.get("start", 0), d, fps, workdir / f"clip{idx}"), "credit": e.get("credit")}
                else:
                    out[idx] = {"kind": "image", "path": f, "credit": e.get("credit")}
            elif kind == "stock":
                f = stock_video(v.get("stock_query", ""))
                if f:
                    out[idx] = {"kind": "video", "frames": _extract_frames(f, 0, dur, fps, workdir / f"clip{idx}")}
        except Exception as e:
            print(f"  ! visual for scene {idx} skipped: {e}")
    return out


def credits(media: dict[int, dict]) -> list[str]:
    return sorted({m["credit"] for m in media.values() if m.get("credit")})
