"""Background-music library: assets/music/<mood>/*.mp3 (flat files count as mood 'any')."""
import random
import shutil
from pathlib import Path

from .config import resolve
from .formats import FORMATS

EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}


def _root(cfg) -> Path:
    return resolve(cfg, cfg["video"]["music_dir"])


def tracks(cfg) -> list[tuple[str, Path]]:
    root = _root(cfg)
    out = []
    if root.exists():
        for p in sorted(root.rglob("*")):
            if p.suffix.lower() in EXTS:
                mood = p.parent.name if p.parent != root else "any"
                out.append((mood, p))
    return out


def add(cfg, src: str, mood: str) -> Path:
    src_p = Path(src).expanduser()
    if src_p.suffix.lower() not in EXTS:
        raise SystemExit(f"Unsupported audio type: {src_p.suffix}")
    dest = _root(cfg) / mood
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_p, dest / src_p.name)
    return dest / src_p.name


def pick(cfg, fmt: str, choice: str | None = None) -> Path | None:
    """fixed track > track in one of the format's moods > any track. 'off' disables music."""
    m = cfg["video"].get("music", {})
    if m.get("mode") == "off" or choice == "none":
        return None
    if choice and choice != "auto":  # a specific track picked in the UI/CLI, matched by file name
        hit = [p for _, p in tracks(cfg) if p.name == choice]
        if hit:
            return hit[0]
    if m.get("fixed"):
        p = resolve(cfg, m["fixed"])
        if p.exists():
            return p
    wanted = set(FORMATS[fmt].get("moods", []))
    lib = tracks(cfg)
    if "sigma" in wanted and not any(mood == "sigma" for mood, _ in lib):
        from . import sigma_bgm
        sigma_bgm.ensure(cfg)  # original synthesized tracks, generated once
        lib = tracks(cfg)
    if not lib:
        return None
    matches = [p for mood, p in lib if mood in wanted] or [p for mood, p in lib if mood == "any"] \
        or [p for _, p in lib]
    return random.choice(matches)
