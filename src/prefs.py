"""Small per-install preferences (data/prefs.json): voice accent, narrator gender, active channel."""
import json

from .config import ROOT

FILE = ROOT / "data" / "prefs.json"
ACCENTS = ("indian", "american", "uk", "korean")
DEFAULTS = {"accent": "indian", "narrator": "male", "channel": "main"}


def load() -> dict:
    try:
        return {**DEFAULTS, **json.loads(FILE.read_text())}
    except Exception:
        return dict(DEFAULTS)


def save(**kw) -> dict:
    cur = load()
    if kw.get("accent") in ACCENTS:
        cur["accent"] = kw["accent"]
    if kw.get("narrator") in ("male", "female"):
        cur["narrator"] = kw["narrator"]
    if kw.get("channel"):
        cur["channel"] = kw["channel"]
    FILE.parent.mkdir(exist_ok=True)
    FILE.write_text(json.dumps(cur))
    return cur
