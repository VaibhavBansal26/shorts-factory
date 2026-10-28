"""Several YouTube channels: each has its own name, handle, optional logo and its own Google sign-in (token file).

The first channel ("main") is the one in config.yaml with token.json. Extra channels live in data/channels.json.
The active channel (data/prefs.json) decides the branding on new reels; each reel remembers its channel for posting.
"""
import copy
import json
import re
from pathlib import Path

from . import prefs
from .config import ROOT

FILE = ROOT / "data" / "channels.json"


def _extras() -> list[dict]:
    try:
        return json.loads(FILE.read_text())
    except Exception:
        return []


def _save(items: list[dict]):
    FILE.parent.mkdir(exist_ok=True)
    FILE.write_text(json.dumps(items, indent=2))


def token_path(cid: str) -> Path:
    return ROOT / "token.json" if cid in ("", "main", None) else ROOT / f"token_{cid}.json"


def all_channels(cfg: dict) -> list[dict]:
    main = {"id": "main", "name": cfg["channel"]["name"], "handle": cfg["channel"]["handle"],
            "logo": cfg["channel"].get("logo"), "about": cfg["channel"].get("about", "")}
    out = [main] + _extras()
    for c in out:
        c["connected"] = token_path(c["id"]).exists()
    return out


def get(cfg: dict, cid: str | None) -> dict:
    items = all_channels(cfg)
    return next((c for c in items if c["id"] == cid), items[0])


def apply(cfg: dict, cid: str | None = None) -> dict:
    """A copy of cfg with the channel's branding swapped in (used when making a reel for that channel)."""
    cid = cid or prefs.load().get("channel", "main")
    ch = get(cfg, cid)
    out = copy.deepcopy(cfg)
    out["channel"].update({"name": ch["name"], "handle": ch["handle"], "id": ch["id"]})
    if ch.get("about"):
        out["channel"]["about"] = ch["about"]
    if ch.get("logo"):
        out["channel"]["logo"] = ch["logo"]
    return out


def add(name: str, handle: str, about: str = "") -> dict:
    items = _extras()
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:20] or "channel"
    cid, n = base, 1
    while cid == "main" or any(c["id"] == cid for c in items):
        n += 1
        cid = f"{base}-{n}"
    ch = {"id": cid, "name": name.strip(), "handle": handle.strip(), "logo": None, "about": about.strip()}
    _save(items + [ch])
    return ch


def update(cid: str, **fields):
    items = _extras()
    for c in items:
        if c["id"] == cid:
            c.update({k: v for k, v in fields.items() if v is not None})
    _save(items)


def remove(cid: str):
    _save([c for c in _extras() if c["id"] != cid])
    token_path(cid).unlink(missing_ok=True)
