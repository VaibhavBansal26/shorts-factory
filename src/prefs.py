"""Small per-install preferences (data/prefs.json): voice accent, narrator gender, active channel."""
import json

from .config import ROOT

FILE = ROOT / "data" / "prefs.json"
ACCENTS = ("indian", "american", "uk", "korean")
DEFAULTS = {"accent": "indian", "narrator": "male", "channel": "main", "eleven_male": "", "eleven_female": ""}


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
    for k in ("eleven_male", "eleven_female"):  # a chosen ElevenLabs voice id ("" = automatic)
        if k in kw and isinstance(kw[k], str) and len(kw[k]) <= 40 and kw[k].replace("_", "").replace("-", "").isalnum() or kw.get(k) == "":
            cur[k] = kw[k]
    if kw.get("channel"):
        cur["channel"] = kw["channel"]
    FILE.parent.mkdir(exist_ok=True)
    FILE.write_text(json.dumps(cur))
    return cur
