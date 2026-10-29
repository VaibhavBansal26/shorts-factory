"""Per-language fonts: Hindi (Devanagari) needs a font that has those glyphs; the default Latin fonts draw boxes."""
from pathlib import Path

from .config import CODE

HINDI = [str(CODE / "assets" / "fonts" / "NotoSansDevanagari-Bold.ttf"),
         "/System/Library/Fonts/Kohinoor.ttc", "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf"]


def hindi_font() -> str | None:
    return next((p for p in HINDI if Path(p).exists()), None)


def for_script(cfg: dict, script: dict) -> dict:
    """cfg with the Hindi font first in the list when the script is spoken in Hindi."""
    if script.get("language") != "hi":
        return cfg
    f = hindi_font()
    if not f:
        return cfg
    return {**cfg, "video": {**cfg["video"], "fonts": [f, *cfg["video"]["fonts"]]}}
