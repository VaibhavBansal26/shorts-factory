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


LANGUAGES = {"en": "English", "hi": "Hindi (हिन्दी)", "hinglish": "Hinglish (Hindi in English letters)"}

AUDIENCES = {"global": "Global (everyone)", "india": "India (made for Indian viewers)"}

LANG_RULES = {
    "en": "",
    "hi": "- LANGUAGE: write every `narration` and `headline` in natural spoken Hindi in Devanagari script, the way people talk "
          "(simple everyday words, common English words like phone, app or doctor are fine written in Devanagari). Write numbers as "
          "Hindi words or digits a Hindi voice reads correctly. No transliteration in Roman letters.\n"
          "- Keep `title`, `description` and `tags` in Hindi too, and put English or Hindi hashtags in tags.",
    "hinglish": "- LANGUAGE: write `narration` and `headline` in Hinglish: Hindi in English (Roman) letters, mixed with common English "
                "words, exactly how Indian creators speak (e.g. \"Yeh trick sabko pata honi chahiye\"). Keep spelling simple and consistent.",
}

INDIA_RULES = ("- AUDIENCE: viewers in India. Use Indian context: rupees (₹), lakh/crore, Indian examples, brands, foods, festivals, "
               "cities, exams, cricket and Bollywood references where they fit, and Indian conditions (climate, prices, regulations). "
               "Do not invent statistics; if a figure is not well known, stay general. No politics, religion or caste angles.")


def system_for(category: str, language: str = "en", audience: str = "global") -> str:
    label = CATEGORIES.get(category, category)
    extra = "\n".join(x for x in (LANG_RULES.get(language, ""), INDIA_RULES if audience == "india" else "") if x)
    return f"""You write scripts for a faceless YouTube Shorts channel in the niche: {label}. Audience: curious general viewers.
{extra}

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


def ideas(cfg: dict, category: str, avoid: str = "", language: str = "en", audience: str = "global") -> list[dict]:
    label = CATEGORIES.get(category, category)
    where = " for viewers in India (Indian context, examples and foods/places/brands)" if audience == "india" else ""
    lang = {"hi": " Write each topic and hook in Hindi (Devanagari).",
            "hinglish": " Write each topic and hook in Hinglish (Hindi in Roman letters)."}.get(language, "")
    resp = anthropic.Anthropic().messages.create(
        model=cfg["llm"]["model"], max_tokens=1500, tools=[IDEAS_TOOL], tool_choice={"type": "auto"},
        system="You suggest specific, interesting, accurate topics for 30-second YouTube Shorts.",
        messages=[{"role": "user", "content": f"Give 6 fresh topic ideas for the niche: {label}{where}. Each topic is specific "
                   f"(not a broad subject) with a scroll-stopping hook line.{lang}{' Avoid: ' + avoid if avoid else ''}"}])
    block = next((b for b in resp.content if b.type == "tool_use"), None)
    return block.input["ideas"] if block else []


def make_faceless(cfg: dict, category: str, topic: str, language: str = "en", audience: str = "global"):
    """Write the script with Claude and render it. Returns (folder, script, video)."""
    label = CATEGORIES.get(category, category)
    item = Item(url=f"misc:{category}:{topic[:80]}:{int(time.time())}", title=topic, summary=topic, source=f"Misc · {label}",
                kind="blog", published=time.time())
    print(f"\n▶ [misc · {category}] {topic}")
    script = scriptgen.generate(cfg, item, "misc", f"Topic: {topic}\nNiche: {label}",
                               system=system_for(category, language, audience))
    script["language"] = language if language in ("hi", "hinglish") else "en"
    script["source"] = {"name": f"Misc · {label}", "title": topic, "url": ""}
    folder, video = pipeline.produce(cfg, script)
    db.mark_used(db.connect(), item.url, topic, "misc", str(folder))
    return folder, script, video


def make_with_clip(cfg: dict, clip, category: str, topic: str, hint: str = "", voices: str = "two", memes: int = 2,
                   music: str = "auto", language: str = "en", audience: str = "global"):
    from . import remix
    label = CATEGORIES.get(category, category)
    extra = "\n".join(x for x in (LANG_RULES.get(language, ""), INDIA_RULES if audience == "india" else "") if x)
    return remix.make(cfg, clip, hint=hint, voices=voices, memes=memes, music=music,
                      topic=topic or f"an interesting fact about {label.lower()}", domain=label, extra=extra,
                      language=language if language in ("hi", "hinglish") else "en")
