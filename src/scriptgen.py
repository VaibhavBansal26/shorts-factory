"""Turn a source item into a structured short-video script with Claude."""
import re

import anthropic

from . import media
from .formats import FORMATS
from .sources import Item

SYSTEM = """You write scripts for a faceless tech YouTube Shorts channel about AI engineering, \
software engineering and new technology. Audience: working engineers and students.

Rules:
- Ground every factual claim in the SOURCE provided. Never invent numbers, quotes, benchmarks or \
product features. If the source is thin, stay general and say less.
- Credit the source by name once, naturally (e.g. "Netflix's engineering blog says...").
- Opinions must be clearly framed as opinions ("my take", "I think").
- Spoken style: short sentences, concrete nouns, no filler, no "in today's video", no emojis, \
no hashtags in narration. Write numbers and acronyms so a TTS voice reads them right (e.g. "L L M" -> "LLM" is fine, \
but spell out symbols like "percent").
- The first sentence must be a hook that stops the scroll within 3 seconds.
- Optionally tell the viewer the video is a parody/commentary when the format is a parody.
- Each scene's narration is spoken aloud; `headline` is the short text shown on screen (max 7 words).
"""

TOOL = {
    "name": "submit_script",
    "description": "Submit the finished short-video script.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "YouTube title, <= 70 chars, no hashtags"},
            "characters": {
                "type": "array",
                "maxItems": 2,
                "description": "Only for kdrama_parody: the two original fictional characters",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"}, "name": {"type": "string"}, "name_ko": {"type": "string"}, "role": {"type": "string"},
                        "gender": {"type": "string", "enum": ["male", "female"]},
                        "look": {"type": "string", "enum": ["chairman", "intern", "ai", "hero", "rival"]},
                    },
                    "required": ["id", "name", "gender", "look"],
                },
            },
            "scenes": {
                "type": "array",
                "minItems": 4,
                "maxItems": 7,
                "items": {
                    "type": "object",
                    "properties": {
                        "narration": {"type": "string", "description": "Exactly what the voice says"},
                        "layout": {
                            "type": "string",
                            "enum": ["big_text", "bullets", "stat", "question", "quote", "dialogue", "clip_dub"],
                        },
                        "headline": {"type": "string", "description": "On-screen text, <= 7 words"},
                        "voice": {"type": "string", "enum": ["male", "female"],
                                  "description": "clip_dub only: which generic English dub voice speaks the line"},
                        "speaker": {"type": "string", "description": "kdrama only: a character id or 'narrator'"},
                        "bullets": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 3,
                            "description": "Only for layout=bullets; each <= 6 words",
                        },
                        "stat": {"type": "string", "description": "Only for layout=stat, e.g. '10x'"},
                        "visual": {
                            "type": "object",
                            "description": "Optional media shown instead of plain text for this scene. "
                                           "Use on 1-3 scenes at most; only options from the MEDIA MENU.",
                            "properties": {
                                "type": {"type": "string", "enum": ["none", "meme", "library", "stock", "archive"]},
                                "meme_template": {"type": "string"},
                                "top_text": {"type": "string"},
                                "bottom_text": {"type": "string"},
                                "library_id": {"type": "string"},
                                "stock_query": {"type": "string"},
                                "archive_query": {"type": "string"},
                            },
                            "required": ["type"],
                        },
                    },
                    "required": ["narration", "layout", "headline"],
                },
            },
            "episode_title": {"type": "string", "description": "series episodes only"},
            "episode_summary": {"type": "string", "description": "series episodes only: 2 sentences"},
            "description": {"type": "string", "description": "2-3 sentence YouTube description (no URL)"},
            "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
        },
        "required": ["title", "scenes", "description", "tags"],
    },
}


def word_count(script: dict) -> int:
    return sum(len(s["narration"].split()) for s in script["scenes"])


def _prompt(item: Item, fmt: str, article_text: str, feedback: str = "") -> str:
    f = FORMATS[fmt]
    lo, hi = f["words"]
    body = article_text if item.kind == "blog" else f"Abstract: {item.summary}"
    return (
        f"FORMAT: {fmt} — {f['guide']}\n"
        f"TOTAL SPOKEN LENGTH: {lo}-{hi} words across all scenes (this becomes a 15-45 second video).\n\n"
        f"SOURCE ({item.kind}) — {item.source}\nTitle: {item.title}\nURL: {item.url}\n\n"
        f"{body[:5000]}\n\nMEDIA MENU (optional visuals; skip if nothing fits, never invent ids):\n"
        f"{media.menu() or 'none available'}\n\n{feedback}"
    )


def generate(cfg: dict, item: Item, fmt: str, article_text: str, series_ctx: str = "") -> dict:
    client = anthropic.Anthropic()
    feedback, script = "", None
    base = f"\n{series_ctx}\n" if series_ctx else ""
    for attempt in range(3):
        resp = client.messages.create(
            model=cfg["llm"]["model"],
            max_tokens=2500,
            system=SYSTEM,
            tools=[TOOL],
            tool_choice={"type": "auto"},  # newer models reject forced tool choice
            messages=[{"role": "user", "content": _prompt(item, fmt, article_text, base + feedback)}],
        )
        block = next((b for b in resp.content if b.type == "tool_use"), None)
        if block is None:
            feedback = "You must answer by calling the submit_script tool."
            continue
        script = block.input
        n, (lo, hi) = word_count(script), FORMATS[fmt]["words"]
        if lo - 10 <= n <= hi + 10:
            return _finish(script, item, fmt)
        feedback = f"Your last draft had {n} words. Rewrite it with {lo}-{hi} words."
    if script is None:
        raise RuntimeError("Claude did not return a script")
    return _finish(script, item, fmt)


def mock(item: Item, fmt: str) -> dict:
    """Offline stand-in so the render/TTS/upload path can be tested without an API key."""
    import json
    import random

    from .config import ROOT
    pool = [json.loads(p.read_text()) for p in sorted((ROOT / "examples").glob("*.json"))]
    pool = [s for s in pool if s.get("format") == fmt]
    if pool:  # hand-written example of the same format, so the look/voices are right
        return _finish(random.choice(pool), item, fmt, keep_source=True)
    short = item.title[:60]
    scenes = [
        {"narration": f"Here's something engineers keep getting wrong about {short}.",
         "layout": "big_text", "headline": "Engineers keep missing this"},
        {"narration": f"According to {item.source}, the core idea is simpler than it sounds. "
                      "It works in three steps.",
         "layout": "big_text", "headline": "Simpler than it sounds",
         "visual": {"type": "meme", "meme_template": "Drake Hotline Bling",
                    "top_text": "Reading the whole docs", "bottom_text": "Asking the one engineer who knows"}},
        {"narration": "First, you collect the signal. Second, you compress it. Third, you act on it.",
         "layout": "bullets", "headline": "Three steps",
         "bullets": ["Collect the signal", "Compress it", "Act on it"]},
        {"narration": "That matters because it cuts cost without cutting quality.",
         "layout": "stat", "headline": "Lower cost, same quality", "stat": "2x"},
        {"narration": "My take: worth trying on a small service first. Would you use it in production?",
         "layout": "question", "headline": "Would you use it in production?"},
    ]
    return _finish(
        {"title": f"{short}", "scenes": scenes,
         "description": f"A quick breakdown inspired by {item.source}.", "tags": ["ai", "engineering"]},
        item, fmt)


def _finish(script: dict, item: Item, fmt: str, keep_source: bool = False) -> dict:
    script["format"] = fmt
    if not keep_source:
        script["source"] = {"name": item.source, "title": item.title, "url": item.url}
    script["title"] = re.sub(r"\s+", " ", script["title"]).strip()[:90]
    return script
