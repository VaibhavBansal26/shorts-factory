"""Fresh content suggestions: Claude reads the latest articles/papers and proposes today's (or this week's) best shorts."""
import json
import os
import subprocess
import sys
import threading
import time

import anthropic

from . import sources
from .config import ROOT
from .formats import FORMATS

FILE = ROOT / "data" / "suggestions.json"
PREFS = ROOT / "data" / "prefs.json"
RUNNING = threading.Event()

TOOL = {
    "name": "submit_ideas",
    "description": "Submit the ranked short-video ideas.",
    "input_schema": {
        "type": "object",
        "properties": {"ideas": {"type": "array", "minItems": 3, "maxItems": 6, "items": {
            "type": "object",
            "properties": {
                "idx": {"type": "integer", "description": "the [number] of the source item"},
                "format": {"type": "string", "enum": [k for k, v in FORMATS.items() if not v.get("needs_upload")]},
                "hook": {"type": "string", "description": "the first spoken line, scroll-stopping, <= 14 words"},
                "angle": {"type": "string", "description": "what this short would say, one sentence"},
                "why_now": {"type": "string", "description": "why it is timely, <= 14 words"},
            },
            "required": ["idx", "format", "hook", "angle", "why_now"]}}},
        "required": ["ideas"],
    },
}


def prefs() -> dict:
    try:
        return {"frequency": "daily", **json.loads(PREFS.read_text())}  # the file also holds voice/channel prefs
    except Exception:
        return {"frequency": "daily"}


def set_frequency(freq: str):
    PREFS.parent.mkdir(exist_ok=True)
    PREFS.write_text(json.dumps({**prefs(), "frequency": "weekly" if freq == "weekly" else "daily"}))


def load() -> dict:
    try:
        return json.loads(FILE.read_text())
    except Exception:
        return {}


def is_stale() -> bool:
    gen = load().get("generated_at", 0)
    limit = 6.5 * 86400 if prefs()["frequency"] == "weekly" else 20 * 3600
    return time.time() - gen > limit


def generate(cfg: dict) -> dict:
    items = sources.ranked(cfg, 25)
    if not items:
        raise RuntimeError("No fresh articles found right now")
    listing = "\n".join(
        f"[{i}] {it.source} · {round((time.time() - it.published) / 86400, 1)}d old · {it.title}\n    {it.summary[:220]}"
        for i, it in enumerate(items))
    period = "week" if prefs()["frequency"] == "weekly" else "day"
    system = (
        "You are the content strategist for a faceless YouTube Shorts channel about AI engineering, software "
        "engineering and new tech (15-45s videos). Pick the best items to turn into shorts this " + period + ". "
        "Prefer concrete, surprising, useful ideas for working engineers. Vary the formats and choose the one that "
        "fits each item: " + "; ".join(f"{k} = {v.get('blurb', '')}" for k, v in FORMATS.items() if not v.get("needs_upload")))
    client = anthropic.Anthropic()
    resp = client.messages.create(model=cfg["llm"]["model"], max_tokens=2000, system=system, tools=[TOOL],
                                  tool_choice={"type": "auto"},
                                  messages=[{"role": "user", "content": f"Source items:\n{listing}\n\nCall submit_ideas."}])
    block = next((b for b in resp.content if b.type == "tool_use"), None)
    if block is None:
        raise RuntimeError("Claude did not return suggestions")
    ideas, seen = [], set()
    for idea in block.input["ideas"]:
        i = idea["idx"]
        if not 0 <= i < len(items) or i in seen:
            continue
        seen.add(i)
        it = items[i]
        ideas.append({**{k: idea[k] for k in ("format", "hook", "angle", "why_now")},
                      "title": it.title, "source": it.source, "url": it.url, "kind": it.kind,
                      "age_days": round((time.time() - it.published) / 86400, 1),
                      "item": {"url": it.url, "title": it.title, "summary": it.summary, "source": it.source,
                               "kind": it.kind, "published": it.published, "weight": it.weight, "text": it.text}})
    out = {"generated_at": time.time(), "frequency": prefs()["frequency"], "ideas": ideas}
    FILE.parent.mkdir(exist_ok=True)
    FILE.write_text(json.dumps(out, indent=2))
    notify(f"{len(ideas)} new content ideas are ready")
    return out


def notify(msg: str):
    if os.getenv("SF_DESKTOP") == "1" and sys.platform == "darwin":
        subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "Shorts Factory"'],
                       capture_output=True)


def refresh_async(cfg: dict):
    if RUNNING.is_set():
        return False

    def run():
        RUNNING.set()
        try:
            generate(cfg)
        except Exception as e:
            print(f"suggestions failed: {e}")
        finally:
            RUNNING.clear()

    threading.Thread(target=run, daemon=True).start()
    return True
