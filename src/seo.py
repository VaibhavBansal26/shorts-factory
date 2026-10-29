"""YouTube title / description / hashtags / tags, written in the channel owner's voice and tuned for search and the algorithm."""
import os
import re

import anthropic

SYSTEM = """You write YouTube Shorts metadata on behalf of the channel owner, in their first-person voice ("I", "my"):
a practical AI / software engineer who explains things fast and honestly.

Honesty rule: first person is for opinions and teaching ("I think", "here's how I'd explain it"). NEVER claim the owner personally
built, ran, tested or measured anything unless the script says so. Attribute findings to the source ("AWS found", "a new paper
shows"), and say so when a video is a parody.

Goals: be found in YouTube search and suggested feeds, and earn clicks and watch-time WITHOUT misleading anyone.

TITLE (max 70 characters):
- Put the main search keyword near the front (what a viewer would type: "LLM hallucinations", "RAG vs fine-tuning").
- Add a curiosity gap or concrete benefit. Specific beats vague. Numbers help if they are real (from the script).
- No ALL CAPS shouting, no emojis spam (one is fine), no clickbait the video does not pay off, no hashtags in the title.

DESCRIPTION (aim for 450-800 characters):
- The first 2 lines show before "more": restate the hook and include the main keywords naturally.
- Then 2-3 sentences of real value (what the viewer learns), in my voice, using related search phrases naturally.
- One short call to action: a specific question to answer in the comments, plus an invitation to follow for more.
- Do not invent facts, stats or claims that are not in the script. Do not promise things the video does not show.
- No "sub4sub", no "like if", no keyword stuffing, no links except none (the app adds the source link).

HASHTAGS: 3-5, most relevant first (YouTube shows the first three above the title). Specific and searchable
(#AIEngineering #LLM #RAG), not generic spam. Do not include #Shorts (it is added automatically).

TAGS: 8-14 search keyword phrases (2-4 words each), mixing broad and specific.

Match the video's tone (sigma reels can be deadpan; K-drama parodies playful) but keep the metadata clear and searchable."""

TOOL = {
    "name": "submit_metadata",
    "description": "Submit the YouTube metadata.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "hashtags": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 5},
            "tags": {"type": "array", "items": {"type": "string"}, "minItems": 6, "maxItems": 14},
        },
        "required": ["title", "description", "hashtags", "tags"],
    },
}


def have_key() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def clean_hashtags(tags: list[str]) -> list[str]:
    out = []
    for t in tags:
        t = "#" + re.sub(r"[^A-Za-z0-9_]", "", t.lstrip("#"))
        if len(t) > 1 and t.lower() not in (x.lower() for x in out) and t.lower() != "#shorts":
            out.append(t)
    return out[:5]


def generate(cfg: dict, script: dict) -> dict:
    ch = cfg["channel"]
    story = "\n".join(f"- {s['narration']}" for s in script["scenes"])
    src = script.get("source", {})
    prompt = (
        f"Channel: {ch['name']} ({ch['handle']}). About: {ch.get('about', 'AI and software engineering explained in under 45 seconds')}\n"
        f"Video format: {script['format']}. Working title: {script['title']}\n"
        f"Source it was inspired by: {src.get('title', '')} ({src.get('name', '')})\n"
        f"What the video says (script):\n{story}\n\n"
        + {"hi": "Write the title and description in Hindi (Devanagari); keep hashtags short and searchable (English or Hindi).\n",
           "hinglish": "Write the title and description in Hinglish (Hindi in Roman letters), the way Indian viewers type.\n"
           }.get(script.get("language"), "") + "Call submit_metadata.")
    client = anthropic.Anthropic()
    resp = client.messages.create(model=cfg["llm"]["model"], max_tokens=1500, system=SYSTEM, tools=[TOOL],
                                  tool_choice={"type": "auto"}, messages=[{"role": "user", "content": prompt}])
    block = next((b for b in resp.content if b.type == "tool_use"), None)
    if block is None:
        raise RuntimeError("Claude did not return metadata")
    m = block.input
    return {"title": re.sub(r"\s+", " ", m["title"]).strip()[:90], "description": m["description"].strip(),
            "hashtags": clean_hashtags(m["hashtags"]), "tags": [t.strip() for t in m["tags"] if t.strip()][:14]}


def ensure(cfg: dict, script: dict, force: bool = False) -> dict:
    """Attach script['seo'] (generate if missing). Falls back silently when there is no key or the call fails."""
    if script.get("seo") and not force:
        return script["seo"]
    if not have_key():
        return {}
    try:
        script["seo"] = generate(cfg, script)
    except Exception as e:
        print(f"  ! SEO metadata skipped: {e}")
        return {}
    return script["seo"]
