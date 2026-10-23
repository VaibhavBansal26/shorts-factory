"""Recurring K-drama parody series: a story bible + episode memory so each episode continues the last."""
import json
from pathlib import Path

from . import db, pipeline, scriptgen, sources
from .config import ROOT

DIR = ROOT / "series"


def path(sid: str) -> Path:
    return DIR / f"{sid}.json"


def load(sid: str) -> dict:
    return json.loads(path(sid).read_text())


def save(bible: dict):
    path(bible["id"]).write_text(json.dumps(bible, indent=2, ensure_ascii=False))


def list_all() -> list[dict]:
    return [load(p.stem) for p in sorted(DIR.glob("*.json"))] if DIR.exists() else []


def context(b: dict, n: int) -> str:
    cast = "\n".join(
        f"- id={c['id']} · {c['name']} ({c['name_ko']}), {c['role']}, {c['gender']}, look={c['look']}. {c['traits']}"
        for c in b["characters"])
    past = "\n".join(f"Episode {e['n']} — {e['title']}: {e['summary']}" for e in b["episodes"]) or "(this is the pilot)"
    beat = b["arc"][n - 1] if n - 1 < len(b.get("arc", [])) else "free choice"
    return (
        f"SERIES: \"{b['title']}\" ({b['title_ko']}). {b['logline']}\nTONE: {b['tone']}\n\nCAST:\n{cast}\n\n"
        f"STORY SO FAR:\n{past}\n\n"
        f"WRITE EPISODE {n}. Suggested beat: {beat}. Rules: continue the story and call back to earlier episodes; "
        f"choose exactly TWO cast members for `characters` and copy their ids exactly; keep each character's voice and quirks; "
        f"the technical idea must come from the SOURCE above; set every dialogue headline to 'Episode {n}: <episode_title>'; "
        f"the final narrator scene gives the real takeaway, asks the viewer a question, and ends with a one-line cliffhanger "
        f"teasing episode {n + 1}; also return `episode_title` (<= 5 words) and `episode_summary` (2 sentences: what happened + cliffhanger)."
    )


def make_episode(cfg: dict, sid: str, item=None, mock: bool = False, source: str | None = None):
    b = load(sid)
    n = len(b["episodes"]) + 1
    if item is None:
        picks = sources.pick(cfg, 1, source)
        if not picks:
            raise RuntimeError("No fresh source item found for this episode")
        item = picks[0]
    print(f"\n▶ {b['title']} · episode {n} · topic: {item.title}")
    if mock:
        raise RuntimeError("Series episodes need ANTHROPIC_API_KEY (story continuity is written by Claude)")
    text = sources.fetch_article_text(item)
    script = scriptgen.generate(cfg, item, "kdrama_parody", text, series_ctx=context(b, n))

    by_id = {c["id"]: c for c in b["characters"]}
    chosen = [by_id[c["id"]] for c in script.get("characters", []) if c.get("id") in by_id][:2]
    if len(chosen) < 2:
        chosen = (chosen + [c for c in b["characters"] if c not in chosen])[:2]
    script["characters"] = chosen
    fallback = b["arc"][n - 1] if n - 1 < len(b["arc"]) else f"Episode {n}"
    ep_title = script.pop("episode_title", None) or fallback
    summary = script.pop("episode_summary", "") or ""
    for sc in script["scenes"]:
        if sc["layout"] == "dialogue":
            sc["headline"] = f"Episode {n}: {ep_title}"
    script["series"] = {"id": b["id"], "title": b["title"], "title_ko": b["title_ko"], "episode": n}
    script["title"] = f"{b['title']} · Ep {n}: {ep_title}"[:90]
    script["description"] = (f"{b['title']} ({b['title_ko']}), episode {n}: {ep_title}. "
                             f"A parody series with original characters. {script.get('description', '')}")[:400]

    folder, video = pipeline.produce(cfg, script)
    db.mark_used(db.connect(), item.url, item.title, "kdrama_parody", str(folder))
    b["episodes"].append({"n": n, "title": ep_title, "summary": summary, "topic": item.title,
                          "folder": folder.name})
    save(b)
    return folder, script, video
