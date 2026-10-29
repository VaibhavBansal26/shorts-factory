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
from .ff import FFMPEG

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
        memes = [m for m in r.json()["data"]["memes"] if m.get("box_count") == 2]
        f.write_text(json.dumps(memes))
    except Exception:
        memes = json.loads(f.read_text()) if f.exists() else []
    return local_memes() + memes


def local_memes() -> list[dict]:
    """Your own meme pack: drop images into assets/memes/ (e.g. an Indian-film reaction still you have the rights to).
    The file name is the template name Claude sees, e.g. 'confused-uncle.jpg' -> 'confused uncle'."""
    d = ROOT / "assets" / "memes"
    if not d.exists():
        return []
    return [{"id": "local-" + p.stem, "name": p.stem.replace("-", " ").replace("_", " "), "url": str(p), "path": str(p),
             "box_count": 2} for p in sorted(d.iterdir()) if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]


def _match_meme(name: str) -> dict | None:
    memes = meme_templates()
    names = {m["name"].lower(): m for m in memes}
    hit = get_close_matches(name.lower(), names, n=1, cutoff=0.55)
    return names[hit[0]] if hit else None


def meme_base(m: dict) -> Path:
    return Path(m["path"]) if m.get("path") else _download(m["url"], CACHE / "memes" / f"{m['id']}{Path(m['url']).suffix}")


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


# ---------------- public-domain archive footage (Internet Archive) ----------------
# Only curated collections count. User-asserted licence tags on archive.org are NOT trusted (people upload
# copyrighted material and tag it CC0), so a plain "publicdomain" licenceurl is never enough on its own.
TRUSTED_COLLECTIONS = ("prelinger", "nasa")


def _is_public_domain(meta: dict) -> bool:
    colls = meta.get("metadata", {}).get("collection", [])
    colls = [colls] if isinstance(colls, str) else colls
    return any(c in TRUSTED_COLLECTIONS for c in colls)


def archive_video(query: str, dur: float):
    """Find a public-domain film on archive.org. Returns dict(url, start, title, id) or None. Never downloads the
    whole file: ffmpeg seeks into the URL for just the seconds we need."""
    import random
    q = f'({query}) AND mediatype:movies AND (collection:prelinger OR collection:nasa)'
    try:
        r = requests.get("https://archive.org/advancedsearch.php", timeout=25, params={
            "q": q, "fl[]": ["identifier", "title"], "rows": 12, "output": "json"})
        docs = r.json()["response"]["docs"]
        top = docs[:4]
        random.shuffle(top)
        docs = top + docs[4:]  # relevance first, a little variety among the best
        for doc in docs:
            meta = requests.get(f"https://archive.org/metadata/{doc['identifier']}", timeout=25).json()
            if not _is_public_domain(meta):
                continue
            mp4 = [f for f in meta.get("files", []) if f["name"].lower().endswith(".mp4")
                   and 0 < int(f.get("size", 0) or 0) < 250_000_000]
            if not mp4:
                continue
            f = min(mp4, key=lambda x: int(x["size"]))
            length = float(f.get("length") or 0)
            if length < dur + 12:
                continue
            start = random.uniform(5, length - dur - 5)
            return {"url": f"https://archive.org/download/{doc['identifier']}/{requests.utils.quote(f['name'])}",
                    "start": round(start, 1), "title": doc["title"], "id": doc["identifier"]}
    except Exception as e:
        print(f"  ! archive search failed: {e}")
    return None


# ---------------- prompt menu + resolution ----------------------
def menu() -> str:
    lines = []
    lib = load_library()
    if lib:
        lines.append("LIBRARY (use library_id; the user's own clips/images):")
        for i in lib:
            lines.append(f"- {i['id']} [{i.get('kind', 'clip')}] {('from ' + i['series'] + ': ') if i.get('series') else ''}{i.get('description', '')} "
                         f"(tags: {', '.join(i.get('tags', []))})")
    memes = meme_templates()
    if memes:
        lines.append("MEME TEMPLATES (photo style: meme_template with top_text/bottom_text): "
                     + "; ".join(m["name"] for m in memes[:70]))
    from . import memes as _m
    lines.append(_m.HELP)
    lines.append("PUBLIC-DOMAIN ARCHIVE FOOTAGE (vintage films, always available): use type 'archive' with a short "
                 "archive_query like 'vintage computer', '1950s office', 'factory assembly line', 'retro science'. Great "
                 "as ironic b-roll for tech jokes; consider 1-2 scenes (about 15 seconds total).")
    if stock_available():
        lines.append("STOCK VIDEO available: give a short visual stock_query (e.g. 'server room', 'typing code').")
    return "\n".join(lines)


def _extract_frames(src: Path, start: float, dur: float, fps: int, out_dir: Path,
                    w: int = BOX_W, h: int = BOX_H) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    vf = (f"fps={fps},scale={w}:{h}:force_original_aspect_ratio=increase,"
          f"crop={w}:{h}")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-ss", str(start), "-t", f"{dur:.2f}", "-i", str(src),
                    "-an", "-vf", vf, "-q:v", "4", str(out_dir / "%04d.jpg")], check=True)
    return sorted(out_dir.glob("*.jpg"))


def make_meme(v: dict, out: Path, photo_font, cfg: dict) -> Path | None:
    """A meme visual -> PNG: a hand-drawn style (boy/girl, chat, ...) or a photo template with our own text."""
    from . import memes
    ui_font = next((p for p in cfg["video"]["fonts"] if Path(p).exists()), None)
    p = memes.render(v, out, photo_font, ui_font)
    if p:
        return p
    m = _match_meme(v.get("meme_template", ""))
    if not m:
        return None
    return draw_meme(meme_base(m), v.get("top_text", ""), v.get("bottom_text", ""), out, photo_font)


def prepare(cfg: dict, script: dict, timeline: dict, workdir: Path) -> dict[int, dict]:
    """Resolve each scene's `visual` into frames/an image. Returns {scene_index: media}. Never raises."""
    fps = cfg["video"]["fps"]
    first = [] if script.get("language") == "hi" else ["/System/Library/Fonts/Supplemental/Impact.ttf"]
    font = next((p for p in [*first, *cfg["video"]["fonts"]] if Path(p).exists()), None)
    lib = {i["id"]: i for i in load_library()}
    out = {}
    # footage guardrail: third-party clips stay a small, interspersed part of every video
    vcfg = cfg["video"]
    budget = min(vcfg.get("footage_cap_seconds", 12), vcfg.get("footage_cap_ratio", 0.35) * timeline["total"])
    used = 0.0
    pd_left = float(vcfg.get("archive_cap_seconds", 15))
    for idx, sc in enumerate(script["scenes"]):
        v = sc.get("visual") or {}
        kind = v.get("type", "none")
        if kind == "none":
            continue
        span = timeline["scenes"][idx]
        dur = min(MAX_CLIP_SECONDS, span["end"] - span["start"] + 0.5)
        try:
            if kind == "meme":
                p = make_meme(v, workdir / f"meme{idx}.png", font, cfg)
                if not p:
                    continue
                out[idx] = {"kind": "image", "path": p}
            elif kind == "library":
                e = lib.get(v.get("library_id"))
                if not e:
                    continue
                f = resolve(cfg, e["file"])
                if e.get("kind", "clip") == "clip":
                    d = min(dur, e.get("duration", MAX_CLIP_SECONDS), budget - used)
                    if d < 1.5:
                        print(f"  footage budget ({budget:.0f}s) used up; scene {idx} shown without the clip")
                        continue
                    used += d
                    full = sc.get("layout") == "clip_dub" or bool(v.get("fullscreen"))
                    size = (cfg["video"]["width"], cfg["video"]["height"]) if full else (BOX_W, BOX_H)
                    out[idx] = {"kind": "video", "full": full, "credit": e.get("credit"),
                                "frames": _extract_frames(f, e.get("start", 0), d, fps, workdir / f"clip{idx}", *size)}
                else:
                    out[idx] = {"kind": "image", "path": f, "credit": e.get("credit")}
            elif kind == "upload":  # the owner's own uploaded clip (Remix); no footage cap applies
                f = Path(v["file"])
                full = sc.get("layout") == "clip_dub" or bool(v.get("fullscreen"))
                size = (cfg["video"]["width"], cfg["video"]["height"]) if full else (BOX_W, BOX_H)
                d = min(float(v.get("duration", dur)), 12.0)
                out[idx] = {"kind": "video", "full": full, "frames": _extract_frames(
                    f, float(v.get("start", 0)), d, fps, workdir / f"clip{idx}", *size)}
            elif kind == "archive":
                d = min(dur, pd_left, MAX_CLIP_SECONDS)
                if d < 1.5:
                    continue
                hit = archive_video(v.get("archive_query", ""), d)
                if not hit:
                    print(f"  no public-domain match for '{v.get('archive_query')}'")
                    continue
                full = sc.get("layout") == "clip_dub" or bool(v.get("fullscreen"))
                size = (cfg["video"]["width"], cfg["video"]["height"]) if full else (BOX_W, BOX_H)
                pd_left -= d
                print(f"  archive: {hit['title'][:50]} ({hit['id']}) {d:.0f}s")
                out[idx] = {"kind": "video", "full": full, "frames": _extract_frames(
                    hit["url"], hit["start"], d, fps, workdir / f"clip{idx}", *size),
                    "credit": f"{hit['title'][:60]} (Prelinger/NASA via Internet Archive, public domain) archive.org/details/{hit['id']}"}
            elif kind == "stock":
                f = stock_video(v.get("stock_query", ""))
                if f:
                    out[idx] = {"kind": "video", "frames": _extract_frames(f, 0, dur, fps, workdir / f"clip{idx}")}
        except Exception as e:
            print(f"  ! visual for scene {idx} skipped: {e}")
    return out


def credits(media: dict[int, dict]) -> list[str]:
    return sorted({m["credit"] for m in media.values() if m.get("credit")})
