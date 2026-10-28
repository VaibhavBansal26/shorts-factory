import json
import random
import re
import time
from datetime import date

from . import db, media, music, scriptgen, seo, sources, tts
from .config import ROOT
from .formats import pick_format
from .render import Renderer

RATES = [None, "+14%", "+22%"]  # progressively faster narration if a script runs long


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40]


def produce(cfg: dict, script: dict):
    """voiceover + visuals + music + render for a finished script dict. Returns (folder, video_path)."""
    lo, hi = cfg["video"]["min_seconds"], cfg["video"]["max_seconds"]
    if script.get("format") == "remix":
        hi = cfg["video"].get("max_seconds_remix", 50)
    script.setdefault("channel_id", cfg["channel"].get("id", "main"))
    folder = ROOT / "output" / f"{date.today()}_{slug(script['title'])}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "script.json").write_text(json.dumps(script, indent=2))
    print(f"  script: {len(script['scenes'])} scenes, {scriptgen.word_count(script)} words")

    timeline = None
    for rate in RATES:
        timeline = tts.synthesize(script, cfg, folder, rate)
        print(f"  voiceover: {timeline['total']:.1f}s" + (f" (rate {rate})" if rate else ""))
        if timeline["total"] <= hi:
            break
    if not lo <= timeline["total"] <= hi:
        raise RuntimeError(f"Duration {timeline['total']:.1f}s outside {lo}-{hi}s; script needs rewriting")

    scene_media = media.prepare(cfg, script, timeline, folder)
    if scene_media:
        print(f"  visuals: {len(scene_media)} scene(s) with media")
        script["media_credits"] = media.credits(scene_media)
        (folder / "script.json").write_text(json.dumps(script, indent=2))
    if seo.ensure(cfg, script):
        print(f"  seo: {script['seo']['title']}")
        (folder / "script.json").write_text(json.dumps(script, indent=2))
    track = music.pick(cfg, script["format"], script.get("music"))
    print(f"  music: {track.name if track else 'none'}")
    out = folder / "video.mp4"
    t0 = time.time()
    Renderer(cfg, script, timeline, scene_media).render(out, timeline["audio"], track)
    print(f"  rendered {out.name} in {time.time() - t0:.0f}s")
    return folder, out


def make_video(cfg: dict, item, fmt: str, mock: bool = False):
    print(f"\n▶ [{fmt}] {item.title}\n  {item.source} · {item.url}")
    if mock:
        script = scriptgen.mock(item, fmt)
    else:
        text = sources.fetch_article_text(item)
        script = scriptgen.generate(cfg, item, fmt, text)
    folder, out = produce(cfg, script)
    return folder, script, out


def make_from_item(cfg: dict, item, fmt: str, mock: bool = False):
    folder, script, video = make_video(cfg, item, fmt, mock)
    db.mark_used(db.connect(), item.url, item.title, fmt, str(folder))
    return folder, script, video


def render_script(cfg: dict, script: dict):
    """Render a hand-written/imported script (see examples/)."""
    script.setdefault("tags", [])
    script.setdefault("description", "")
    print(f"\n▶ [{script['format']}] {script['title']}")
    folder, out = produce(cfg, script)
    con = db.connect()
    db.mark_used(con, script["source"]["url"] or "local:" + script["title"], script["source"]["title"], script["format"], str(folder))
    return folder, script, out


def run(cfg: dict, n: int, fmt: str | None, publish: bool, privacy: str | None,
        mock: bool, source: str | None, formats: list[str] | None = None) -> list[dict]:
    con = db.connect()
    items = sources.pick(cfg, n, source)
    if not items:
        print("No fresh candidates found.")
        return []
    results = []
    for item in items:
        f = pick_format(cfg, fmt) if fmt or not formats else random.choice(formats)
        try:
            folder, script, video = make_video(cfg, item, f, mock)
        except Exception as e:
            print(f"  ✗ skipped ({e})")
            continue
        db.mark_used(con, item.url, item.title, f, str(folder))
        res = {"folder": str(folder), "title": script["title"], "video_id": None}
        if publish:
            from . import youtube  # lazy: only needed when publishing
            try:
                res["video_id"] = youtube.upload(video, script, cfg, privacy)
                db.set_video_id(con, str(folder), res["video_id"])
            except BaseException as e:  # SystemExit when not authorised
                print(f"  ✗ upload failed: {e}")
        results.append(res)
    return results
