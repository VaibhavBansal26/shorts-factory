"""Misc reels: entertainment, cooking, nutrition, general knowledge and other general-interest topics.

Two ways to make one: faceless (Claude writes it, with memes / stock / library visuals) or from a video you drop in
(a clip Claude watches and dubs, reusing the Remix pipeline with this topic area).
"""
import time

import anthropic

from . import db, pipeline, scriptgen, seo
from .sources import Item

CATEGORIES = {
    "entertainment": "Entertainment (movies, TV, music, pop culture, trivia)",
    "cooking": "Cooking and recipes",
    "nutrition": "Nutrition and healthy eating",
    "general_knowledge": "General knowledge and facts",
    "science": "Science and nature",
    "history": "History",
    "travel": "Travel and places",
    "fitness": "Fitness and wellbeing",
    "money": "Money basics and personal finance",
    "motivation": "Motivation and productivity",
}

RULES = {
    "nutrition": "This is general educational information, not medical advice. No cure or weight-loss promises; say to check "
                 "with a doctor or dietitian where relevant. Do not invent figures.",
    "fitness": "General educational information, not medical advice. No guarantees; mention checking with a professional where relevant.",
    "money": "Educational only, not financial advice. No guaranteed returns, no tips on specific stocks or coins.",
    "cooking": "Real, safe techniques (food safety matters). Give quantities and times only when you are confident they are right.",
    "entertainment": "Stick to verifiable facts. No rumours, spoilers without warning, or claims about real people's private lives.",
}


def system_for(category: str) -> str:
    label = CATEGORIES.get(category, category)
    return f"""You write scripts for a faceless YouTube Shorts channel in the niche: {label}. Audience: curious general viewers.

Rules:
- Be accurate. Never invent numbers, quotes, studies or facts; if unsure, stay general or leave it out.
- {RULES.get(category, "Keep claims general and verifiable; frame opinions as opinions.")}
- Spoken style: short sentences, concrete nouns, warm and energetic, no filler, no "in today's video", no emojis, no hashtags.
  Write numbers so a TTS voice reads them right (spell out "percent", "degrees").
- The first sentence is a hook that stops the scroll within 3 seconds.
- Each scene's narration is spoken aloud; `headline` is the short text shown on screen (max 7 words).
- Humour may be Hinglish or relatable, but never targets a real person, religion, caste or community."""


IDEAS_TOOL = {
    "name": "submit_ideas", "description": "Submit short-video topic ideas.",
    "input_schema": {"type": "object", "properties": {"ideas": {"type": "array", "minItems": 4, "maxItems": 8, "items": {
        "type": "object", "properties": {"topic": {"type": "string"}, "hook": {"type": "string", "description": "first spoken line"}},
        "required": ["topic", "hook"]}}}, "required": ["ideas"]},
}


def ideas(cfg: dict, category: str, avoid: str = "") -> list[dict]:
    label = CATEGORIES.get(category, category)
    resp = anthropic.Anthropic().messages.create(
        model=cfg["llm"]["model"], max_tokens=1500, tools=[IDEAS_TOOL], tool_choice={"type": "auto"},
        system="You suggest specific, interesting, accurate topics for 30-second YouTube Shorts.",
        messages=[{"role": "user", "content": f"Give 6 fresh topic ideas for the niche: {label}. Each topic is specific "
                   f"(not a broad subject) with a scroll-stopping hook line.{' Avoid: ' + avoid if avoid else ''}"}])
    block = next((b for b in resp.content if b.type == "tool_use"), None)
    return block.input["ideas"] if block else []


def make_faceless(cfg: dict, category: str, topic: str):
    """Write the script with Claude and render it. Returns (folder, script, video)."""
    label = CATEGORIES.get(category, category)
    item = Item(url=f"misc:{category}:{topic[:80]}:{int(time.time())}", title=topic, summary=topic, source=f"Misc · {label}",
                kind="blog", published=time.time())
    print(f"\n▶ [misc · {category}] {topic}")
    script = scriptgen.generate(cfg, item, "misc", f"Topic: {topic}\nNiche: {label}", system=system_for(category))
    script["source"] = {"name": f"Misc · {label}", "title": topic, "url": ""}
    folder, video = pipeline.produce(cfg, script)
    db.mark_used(db.connect(), item.url, topic, "misc", str(folder))
    return folder, script, video


def make_with_clip(cfg: dict, clip, category: str, topic: str, hint: str = "", voices: str = "two", memes: int = 2,
                   music: str = "auto"):
    from . import remix
    label = CATEGORIES.get(category, category)
    return remix.make(cfg, clip, hint=hint, voices=voices, memes=memes, music=music,
                      topic=topic or f"an interesting fact about {label.lower()}", domain=label)
