"""Short-form formats. Each one tells the script writer the structure to follow."""
import random

FORMATS = {
    "concept_explainer": {
        "moods": ["calm", "any"],
        "label": "CONCEPT",
        "accent": (56, 189, 248),
        "words": (70, 100),
        "guide": (
            "Explain ONE concept from the source in plain language. Structure: "
            "1) a hook that names the pain or surprise, 2) what it is in one sentence, "
            "3) how it works in 2-3 steps (use a bullets scene), 4) why it matters to an engineer, "
            "5) a one-line takeaway."
        ),
    },
    "ask_question": {
        "moods": ["chill", "any"],
        "label": "QUESTION",
        "accent": (250, 204, 21),
        "words": (45, 75),
        "guide": (
            "Pose a sharp, debatable question inspired by the source, give 2 short sides/options "
            "(bullets scene), then end by asking the viewer to answer in the comments. "
            "Do NOT reveal a 'correct' answer. The last scene uses the 'question' layout."
        ),
    },
    "research_opinion": {
        "moods": ["calm", "any"],
        "label": "RESEARCH TAKE",
        "accent": (192, 132, 252),
        "words": (75, 105),
        "guide": (
            "Summarise what the paper/article found in 2 sentences (no invented numbers), then give a "
            "clearly-labelled opinion ('My take:') with one reason and one caveat, and END with a "
            "genuine open question to the audience. The last scene uses the 'question' layout."
        ),
    },
    "myth_vs_fact": {
        "moods": ["upbeat", "any"],
        "label": "MYTH vs FACT",
        "accent": (244, 114, 182),
        "words": (60, 90),
        "guide": (
            "State a common misconception related to the source topic, flip it with the fact as supported "
            "by the source, explain why people get it wrong, and give a practical rule of thumb."
        ),
    },
    "analogy": {
        "moods": ["chill", "any"],
        "label": "EXPLAINED SIMPLY",
        "accent": (52, 211, 153),
        "words": (65, 95),
        "guide": (
            "Explain the core idea using one everyday analogy (kitchen, traffic, post office...). "
            "Map 2-3 parts of the analogy to the real technical parts (bullets scene). End with where "
            "the analogy breaks down, in one line."
        ),
    },
    "interview_question": {
        "moods": ["tense", "any"],
        "label": "INTERVIEW Q",
        "accent": (251, 146, 60),
        "words": (65, 100),
        "guide": (
            "Frame the source topic as a realistic engineering interview question. Scene 1 asks it, "
            "scene 2 says 'pause and think' with a beat, then give a strong 3-point answer (bullets "
            "scene), and finish with the common mistake candidates make."
        ),
    },
    "hot_take": {
        "moods": ["upbeat", "any"],
        "label": "HOT TAKE",
        "accent": (248, 113, 113),
        "words": (50, 80),
        "guide": (
            "One spicy-but-defensible opinion triggered by the source. Hook with the claim, give the "
            "evidence from the source, concede one counterpoint, and ask if the viewer agrees. "
            "Clearly an opinion, never stated as fact. The last scene uses the 'question' layout."
        ),
    },
    "quick_news": {
        "moods": ["upbeat", "any"],
        "label": "TECH NEWS",
        "accent": (96, 165, 250),
        "words": (60, 90),
        "guide": (
            "What happened (who + what), why it matters to engineers, and what to watch next. "
            "Include one stat scene ONLY if the source gives a concrete number."
        ),
    },
    "this_vs_that": {
        "moods": ["upbeat", "any"],
        "label": "VERSUS",
        "accent": (45, 212, 191),
        "words": (65, 95),
        "guide": (
            "Compare two approaches/tools from the source in a 'when to use which' bullets scene, "
            "with a clear decision rule, and end with a one-line verdict."
        ),
    },
    "meme_explainer": {
        "label": "MEME",
        "moods": ["funny", "upbeat", "any"],
        "accent": (250, 170, 60),
        "words": (55, 85),
        "guide": (
            "A funny-but-useful short. Open with a relatable engineering pain as a meme scene "
            "(visual.type='meme', pick the template whose joke actually fits, keep top/bottom text under 8 words each), "
            "then explain the real concept or fix from the source in 2-3 plain sentences, and close with a second "
            "meme or a one-line takeaway. Humour must land on the technical idea, never on a person or company."
        ),
    },
    "series_moment": {
        "label": "SERIES x TECH",
        "moods": ["funny", "upbeat", "any"],
        "accent": (236, 72, 153),
        "words": (55, 85),
        "guide": (
            "Use ONE clip from the LIBRARY (a moment from a show/film) as the hook: say what happens in the "
            "moment ('Remember when...'), connect it to a concept from the source, add one funny line and one real "
            "takeaway. Use visual.type='library' with a listed library_id only; if no library item fits, use a meme "
            "instead. Never describe the clip inaccurately; stay with its library description. Keep commentary the star: "
            "the clip is a short illustration, not the content."
        ),
    },
}


def pick_format(cfg: dict, name: str | None = None) -> str:
    if name:
        if name not in FORMATS:
            raise SystemExit(f"Unknown format '{name}'. Options: {', '.join(FORMATS)}")
        return name
    weights = {k: v for k, v in cfg["formats"].items() if k in FORMATS}
    return random.choices(list(weights), weights=list(weights.values()))[0]
