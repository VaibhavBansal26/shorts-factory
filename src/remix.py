"""Remix: take a clip you upload (~30s), have Claude look at it and write a new English dub (two people discussing AI),
insert memes between segments, add music from the library, and render a Short.

The original audio is replaced by the dub. Only upload clips you own or have the rights to use.
"""
import base64
import json
import subprocess
from pathlib import Path

import anthropic

from . import media, pipeline
from .ff import FFMPEG, duration
from .config import ROOT

MAX_CLIP = 40.0  # seconds of the upload we will use; keeps the final video under ~50s

SYSTEM = """You write the new English dub for a short vertical video built from a clip the channel owner uploaded.
You are shown frames sampled from the clip with their timestamps. The dub turns it into a funny, useful conversation about
AI and software engineering (topic given by the user) between two voices (male/female), or one narrator.

Rules:
- Describe and react to what is VISIBLE (actions, setting, mood). Never identify real people from their faces, never guess
  names or the source show or film.
- Break the clip into 3-6 consecutive segments (2-8 seconds each, increasing, non-overlapping, inside the clip length). The
  line for a segment must be speakable in that time: at most 2.3 words per second of segment.
- Insert 1-3 meme beats between segments (not first, not last). Each is 2.5-4 seconds: a meme template from the list, short
  top/bottom text (max 8 words each, funny and tied to the AI point just made), and a quip (max 8 words) spoken by narrator.
- End with one outro beat: narrator, a real takeaway plus a question for viewers (max 18 words).
- Total final video must stay under 48 seconds. Teach one true idea about AI/engineering; humour never targets real people.
- Spoken style: short sentences, no emojis, no hashtags."""

TOOL = {
    "name": "submit_remix",
    "description": "Submit the remix plan.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "YouTube title <= 70 chars"},
            "description": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
            "beats": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": ["clip", "meme", "outro"]},
                        "clip_start": {"type": "number"}, "clip_end": {"type": "number"},
                        "voice": {"type": "string", "enum": ["male", "female", "narrator"]},
                        "line": {"type": "string", "description": "exactly what is spoken"},
                        "headline": {"type": "string", "description": "short on-screen label, <= 6 words"},
                        "meme_template": {"type": "string"},
                        "top_text": {"type": "string"}, "bottom_text": {"type": "string"},
                    },
                    "required": ["kind", "voice", "line"],
                },
            },
        },
        "required": ["title", "description", "beats"],
    },
}


def probe(path: Path) -> float:
    return duration(path)


def sample_frames(path: Path, dur: float, workdir: Path, n: int = 6) -> list[tuple[float, bytes]]:
    frames = []
    for i in range(n):
        t = dur * (i + 0.5) / n
        out = workdir / f"probe{i}.jpg"
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1",
                        "-vf", "scale=512:-2", "-q:v", "5", str(out)], check=True)
        frames.append((t, out.read_bytes()))
        out.unlink()
    return frames


def plan(cfg: dict, clip: Path, dur: float, hint: str, voices: str, memes: int, topic: str, workdir: Path) -> dict:
    content = []
    for t, jpg in sample_frames(clip, dur, workdir):
        content.append({"type": "text", "text": f"Frame at {t:.1f}s:"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                    "data": base64.b64encode(jpg).decode()}})
    names = "; ".join(m["name"] for m in media.meme_templates()[:40])
    voice_rule = ("Use TWO voices alternating (male, female) for clip beats." if voices == "two"
                  else "Use ONE voice: set voice 'narrator' on every beat.")
    content.append({"type": "text", "text": (
        f"Clip length: {dur:.1f}s. Topic of the conversation: {topic}.\n"
        f"What the owner says the clip is: {hint or '(no hint, infer from frames)'}\n"
        f"{voice_rule} Number of meme beats: {memes}.\nMEME TEMPLATES: {names}")})
    client = anthropic.Anthropic()
    feedback = ""
    for _ in range(3):
        resp = client.messages.create(
            model=cfg["llm"]["model"], max_tokens=2500, system=SYSTEM, tools=[TOOL],
            tool_choice={"type": "auto"},
            messages=[{"role": "user", "content": content + ([{"type": "text", "text": feedback}] if feedback else [])}])
        block = next((b for b in resp.content if b.type == "tool_use"), None)
        if block is None:
            feedback = "Answer by calling submit_remix."
            continue
        beats = block.input["beats"]
        clips = [b for b in beats if b["kind"] == "clip"]
        bad = [b for b in clips if not (0 <= b.get("clip_start", -1) < b.get("clip_end", -1) <= dur + 0.3)]
        if clips and not bad:
            return block.input
        feedback = f"Fix: clip beats need valid clip_start < clip_end within 0-{dur:.1f}s."
    raise RuntimeError("Claude did not return a usable remix plan")


def build_script(cfg: dict, plan_: dict, clip: Path, dur: float, voices: str, music: str, name: str) -> dict:
    scenes = []
    last_end = 0.0
    for b in plan_["beats"]:
        voice = b["voice"] if (voices == "two" and b["voice"] in ("male", "female")) else None
        if b["kind"] == "clip":
            start = max(last_end, float(b["clip_start"]))
            end = min(dur, max(start + 1.5, float(b["clip_end"])))
            last_end = end
            scenes.append({"narration": b["line"], "layout": "clip_dub", "headline": b.get("headline", ""),
                           **({"voice": voice} if voice else {}), "min_duration": round(end - start, 2),
                           "visual": {"type": "upload", "file": str(clip), "start": round(start, 2),
                                      "duration": round(end - start, 2), "fullscreen": True}})
        elif b["kind"] == "meme":
            scenes.append({"narration": b["line"], "layout": "big_text", "headline": b.get("headline") or "Meanwhile…",
                           "visual": {"type": "meme", "meme_template": b.get("meme_template", ""),
                                      "top_text": b.get("top_text", ""), "bottom_text": b.get("bottom_text", "")}})
        else:
            scenes.append({"narration": b["line"], "layout": "question",
                           "headline": (b.get("headline") or "What do you think?")})
    return {"format": "remix", "title": plan_["title"][:90], "description": plan_.get("description", ""),
            "tags": plan_.get("tags", []), "music": music,
            "source": {"name": "Original clip", "title": name, "url": ""}, "scenes": scenes}


def make(cfg: dict, clip: Path, hint: str = "", voices: str = "two", memes: int = 2, music: str = "auto",
         topic: str = "AI agents, hallucinations and prompting, explained like a friendly argument"):
    clip = Path(clip).resolve()
    dur = min(probe(clip), MAX_CLIP)
    work = ROOT / "data" / "remix_tmp"
    work.mkdir(parents=True, exist_ok=True)
    print(f"\n▶ Remix of {clip.name} ({dur:.0f}s used)")
    p = plan(cfg, clip, dur, hint, voices, memes, topic, work)
    script = build_script(cfg, p, clip, dur, voices, music, clip.name)
    folder, video = pipeline.produce(cfg, script)
    return folder, script, video
