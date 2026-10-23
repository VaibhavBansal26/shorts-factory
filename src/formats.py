"""Short-form formats. Each one tells the script writer the structure to follow."""
import random

FORMATS = {
    "concept_explainer": {
        "blurb": 'One idea, three steps, one takeaway.',
        "theme": "default",
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
        "blurb": 'A debatable question that farms comments.',
        "theme": "default",
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
        "blurb": 'What a paper found, your take, then a question.',
        "theme": "default",
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
        "blurb": 'Flip a common misconception.',
        "theme": "default",
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
        "blurb": 'Explain it with an everyday analogy.',
        "theme": "default",
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
        "blurb": 'Pose an interview question, then answer it.',
        "theme": "default",
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
        "blurb": 'One spicy but defensible opinion.',
        "theme": "default",
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
        "blurb": 'What happened and why engineers care.',
        "theme": "default",
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
        "blurb": 'When to use which.',
        "theme": "default",
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
        "blurb": 'Funny meme scenes that still teach the idea.',
        "theme": "default",
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
        "blurb": 'A clip from your library as the hook.',
        "theme": "default",
        "label": "SERIES x TECH",
        "moods": ["funny", "upbeat", "any"],
        "accent": (236, 72, 153),
        "words": (55, 85),
        "guide": (
            "A fan-dub parody of a Korean-drama (or any series) moment the user has put in the LIBRARY. Use only listed "
            "library ids; if none fits, switch to memes. Make 3-5 `clip_dub` scenes, each with visual {type:'library', "
            "library_id} (clips are shown muted, max ~8s each), a `voice` (male|female) and ONE short English line "
            "(max 14 words) dubbed over it, in a dramatic tone, joking about an AI/tech idea from the source (hallucination, "
            "prompting, tech debt...). Stay consistent with the library description of what the clip shows; never invent "
            "plot, never imitate or name actors. Final scene: layout 'question', speaker narrator, one real takeaway plus a "
            "question. The clip is the illustration; the commentary is the content."
        ),
    },
    "sigma_reel": {
        "blurb": "Deep voice, gold text, phonk bass. Rules of the sigma engineer.",
        "theme": "sigma",
        "label": "SIGMA",
        "moods": ["sigma"],
        "accent": (234, 179, 8),
        "words": (45, 80),
        "guide": (
            "A 'sigma' motivational-edit parody for engineers: calm, absurdly serious, deep-voice energy. "
            "Structure: a one-line hook ('Rule 1 of the sigma engineer'), 3-4 numbered rules, each one a real, "
            "correct technical principle from the source (short, punchy, under 14 words), then a final line that "
            "asks the viewer which rule they break most. The humour is the over-serious tone; the content must stay "
            "accurate and useful. Headlines are ALL the rule in 3-6 words. No insults, no real people."
        ),
    },
    "kdrama_parody": {
        "blurb": "Two Korean-drama characters argue about AI, English-dubbed.",
        "theme": "drama",
        "label": "K-DRAMA x AI",
        "moods": ["sigma", "tense"],
        "accent": (244, 114, 182),
        "words": (18, 60),
        "guide": (
            "A parody scene in the style of a melodramatic Korean TV series, about an AI/tech concept from the source "
            "(hallucination, prompting, RAG, tech debt, evals...). Invent TWO original fictional characters in "
            "`characters` (each: id, name, role, gender male|female, look one of chairman|intern|ai|hero|rival). "
            "Never use real actors, real show titles or copy real dialogue; parody the TROPES only (cold chairman, "
            "tearful intern, slap, rain scene, amnesia, love triangle, 'it's not what it looks like'). "
            "4-5 dialogue scenes (layout 'dialogue'), speakers alternating. The characters are Korean (give them Korean "
            "names plus `name_ko` in Hangul) and the show is ENGLISH-DUBBED: `narration` is the spoken ENGLISH line "
            "(max ~14 words, melodramatic delivery, funny); `headline` is a short tag like 'Episode 7: The Hallucination'. "
            "Do not use `subtitle`. The final scene: speaker 'narrator', layout 'question', English, giving the real "
            "technical takeaway in one sentence plus a question to the viewer."
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
