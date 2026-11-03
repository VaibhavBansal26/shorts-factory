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
from . import memes as memes_mod
from .ff import FFMPEG, duration
from .config import ROOT

MAX_CLIP = 40.0  # seconds of the upload we will use; keeps the final video under ~50s

SYSTEM = """You write the new English dub for a short vertical video built from a clip the channel owner uploaded.
You are shown frames sampled from the clip with their timestamps. The dub turns it into a funny, useful conversation about
AI and software engineering (topic given by the user) between two voices (male/female), or one narrator.

Rules:
- Voice casting: FIRST fill "cast" with each distinct on-screen person (what they look like, and whether they appear male
  or female, which is only used to choose a matching dub voice). Then, for every clip beat, set "voice" to the gender of the
  person who is speaking or most prominent in THAT segment, so the dub matches who is on screen. If two people talk to each
  other, alternate between them in line with who is shown. If only one person appears, use that person's voice for every
  clip beat. Meme and outro beats are voiced by the narrator. If the owner's hint says who is who, follow it.
- Describe and react to what is VISIBLE (actions, setting, mood). Never identify real people from their faces, never guess
  names or the source show or film.
- Break the clip into 3-6 consecutive segments (2-8 seconds each, increasing, non-overlapping, inside the clip length). The
  line for a segment must be speakable in that time: at most 2.3 words per second of segment.
- Insert 1-3 meme beats between segments (not first, not last). Each is 2.5-4 seconds: a meme (any style from MEME STYLES; vary them: relationship, boy-girl, chat, expectation vs reality, Indian/Hinglish humour, photo templates), short
  top/bottom text or meme_lines (max 8 words each, funny and tied to the AI point just made), and a quip (max 8 words) spoken by narrator.
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
            "cast": {"type": "array", "items": {"type": "object", "properties": {
                "look": {"type": "string"}, "appears": {"type": "string", "enum": ["male", "female"]}},
                "required": ["look", "appears"]}},
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
                        "meme_style": {"type": "string", "enum": ["template", "boy_girl", "chat", "expectation", "drake", "nobody"]},
                        "meme_lines": {"type": "array", "items": {"type": "string"}},
                        "top_text": {"type": "string"}, "bottom_text": {"type": "string"},
                    },
                    "required": ["kind", "voice", "line"],
                },
            },
        },
        "required": ["title", "description", "cast", "beats"],
    },
}


def _system(domain: str, extra: str = "") -> str:
    if domain == "AI and software engineering" and not extra:
        return SYSTEM
    return (SYSTEM.replace("AI and software engineering", domain).replace("about AI/engineering", f"about {domain}")
            .replace("the AI point just made", "the point just made")
            + f"\n- Topic area is {domain}: keep facts accurate and general, no invented statistics, and for health or "
              "nutrition stay educational (not medical advice)." + (f"\n{extra}" if extra else ""))


def probe(path: Path) -> float:
    return duration(path)


def speech(clip: Path) -> list[tuple[float, float, str]]:
    """What the people in the clip actually say and when: [(start, end, text)], utterances split on pauses.
    Empty when the speech model isn't available or hears nothing."""
    try:
        from . import asr
        if not asr.available():
            return []
        words = asr.transcribe(clip)
    except Exception as e:
        print(f"  original speech not read ({e})")
        return []
    out, cur = [], []
    for w in words:
        if cur and w[1] - cur[-1][2] > 0.45:
            out.append((cur[0][1], cur[-1][2], " ".join(x[0] for x in cur)))
            cur = []
        cur.append(w)
    if cur:
        out.append((cur[0][1], cur[-1][2], " ".join(x[0] for x in cur)))
    return out


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


def plan(cfg: dict, clip: Path, dur: float, hint: str, voices: str, memes: int, topic: str, workdir: Path,
         domain: str = "AI and software engineering", extra: str = "", spoken: list | None = None) -> dict:
    content = []
    for t, jpg in sample_frames(clip, dur, workdir):
        content.append({"type": "text", "text": f"Frame at {t:.1f}s:"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                    "data": base64.b64encode(jpg).decode()}})
    names = "; ".join(m["name"] for m in media.meme_templates()[:70]) + "\n" + memes_mod.HELP
    voice_rule = ("Use TWO voices (male and female), each matched to the person speaking on screen in that segment." if voices == "two"
                  else "Use ONE voice: set voice 'narrator' on every beat.")
    content.append({"type": "text", "text": (
        f"Clip length: {dur:.1f}s. Topic of the conversation: {topic}.\n"
        f"What the owner says the clip is: {hint or '(no hint, infer from frames)'}\n"
        f"{voice_rule} Number of meme beats: {memes}.\nMEME TEMPLATES: {names}")})
    if spoken:
        content.append({"type": "text", "text": (
            "ORIGINAL SPEECH in the clip (start-end seconds, what the on-screen people say). The dub replaces this audio, so it "
            "must be heard exactly while these people are talking. Cut every clip beat on the pauses between utterances "
            "(clip_start just before an utterance begins, clip_end just after it ends), cover each beat with one or two "
            "consecutive utterances, and write the line so it can be spoken within the speech time of those utterances "
            "(at most 2.3 words per second), answering or riffing on what is said there. The clip beats together must total at most "
            "30 seconds (meme and outro beats add about 12 more, and the video must stay under 48s), so use only the best "
            "consecutive utterances and drop the rest:\n"
            + "\n".join(f"[{a:.1f}-{b:.1f}] {t}" for a, b, t in spoken))})
    client = anthropic.Anthropic()
    feedback = ""
    for _ in range(3):
        resp = client.messages.create(
            model=cfg["llm"]["model"], max_tokens=2500, system=_system(domain, extra), tools=[TOOL],
            tool_choice={"type": "auto"},
            messages=[{"role": "user", "content": content + ([{"type": "text", "text": feedback}] if feedback else [])}])
        block = next((b for b in resp.content if b.type == "tool_use"), None)
        if block is None:
            feedback = "Answer by calling submit_remix."
            continue
        beats = block.input.get("beats")
        if isinstance(beats, str):  # the model sometimes sends the list as a JSON string
            try:
                beats = block.input["beats"] = json.loads(beats)
            except Exception:
                beats = None
        if not isinstance(beats, list):
            feedback = "Answer by calling submit_remix with a 'beats' list."
            continue
        clips = [b for b in beats if b["kind"] == "clip"]
        bad = [b for b in clips if not (0 <= b.get("clip_start", -1) < b.get("clip_end", -1) <= dur + 0.3)]
        used = sum(b["clip_end"] - b["clip_start"] for b in clips if b not in bad)
        if clips and not bad and (not spoken or used <= 33):
            return block.input
        feedback = (f"Fix: clip beats need valid clip_start < clip_end within 0-{dur:.1f}s." if bad or not clips else
                    f"Fix: the clip beats total {used:.0f}s; keep them at 30s or less by dropping utterances.")
    raise RuntimeError("Claude did not return a usable remix plan")


def _snap(start: float, end: float, spoken: list, last_end: float, dur: float):
    """Move a segment's edges to the pauses around the speech it contains. Returns (start, end, lead, fit): where the
    first word begins inside the segment and how long the speech lasts, so the dub can be placed on it."""
    inside = [u for u in spoken if start - 0.3 <= (u[0] + u[1]) / 2 <= end + 0.3 and u[0] >= last_end - 0.3]
    if not inside:
        return start, end, 0.0, 0.0
    first, last = inside[0], inside[-1]
    prev_end = max([u[1] for u in spoken if u[1] <= first[0]], default=0.0)
    next_start = min([u[0] for u in spoken if u[0] >= last[1]], default=dur)
    a = max(last_end, (prev_end + first[0]) / 2, first[0] - 0.5)
    b = min(dur, (last[1] + next_start) / 2, last[1] + 0.5)
    return a, max(b, a + 1.5), first[0] - a, last[1] - first[0]


def build_script(cfg: dict, plan_: dict, clip: Path, dur: float, voices: str, music: str, name: str,
                 spoken: list | None = None) -> dict:
    scenes = []
    last_end = 0.0
    for b in plan_["beats"]:
        voice = b["voice"] if (voices == "two" and b["voice"] in ("male", "female")) else None
        if b["kind"] == "clip":
            start = max(last_end, float(b["clip_start"]))
            end = min(dur, max(start + 1.5, float(b["clip_end"])))
            lead = fit = 0.0
            if spoken:
                start, end, lead, fit = _snap(start, end, spoken, last_end, dur)
            last_end = end
            scenes.append({"narration": b["line"], "layout": "clip_dub", "headline": b.get("headline", ""),
                           **({"voice": voice} if voice else {}), "min_duration": round(end - start, 2),
                           **({"speech_lead": round(lead, 2), "speech_len": round(fit, 2)} if fit else {}),
                           "visual": {"type": "upload", "file": str(clip), "start": round(start, 2),
                                      "duration": round(end - start, 2), "fullscreen": True}})
        elif b["kind"] == "meme":
            scenes.append({"narration": b["line"], "layout": "big_text", "headline": b.get("headline") or "Meanwhile…",
                           "visual": {"type": "meme", "meme_template": b.get("meme_template", ""),
                                      "meme_style": b.get("meme_style", "template"), "meme_lines": b.get("meme_lines", []),
                                      "top_text": b.get("top_text", ""), "bottom_text": b.get("bottom_text", "")}})
        else:
            scenes.append({"narration": b["line"], "layout": "question",
                           "headline": (b.get("headline") or "What do you think?")})
    return {"format": "remix", "title": plan_["title"][:90], "description": plan_.get("description", ""),
            "tags": plan_.get("tags", []), "music": music,
            "source": {"name": "Original clip", "title": name, "url": ""}, "scenes": scenes}


def make(cfg: dict, clip: Path, hint: str = "", voices: str = "two", memes: int = 2, music: str = "auto",
         topic: str = "AI agents, hallucinations and prompting, explained like a friendly argument",
         domain: str = "AI and software engineering", extra: str = "", language: str = "en"):
    clip = Path(clip).resolve()
    dur = min(probe(clip), MAX_CLIP)
    work = ROOT / "data" / "remix_tmp"
    work.mkdir(parents=True, exist_ok=True)
    print(f"\n▶ Remix of {clip.name} ({dur:.0f}s used)")
    spoken = [u for u in speech(clip) if u[0] < dur]
    print(f"  original speech: {len(spoken)} utterances" if spoken else "  original speech: not available, timing from frames only")
    p = plan(cfg, clip, dur, hint, voices, memes, topic, work, domain, extra, spoken)
    script = build_script(cfg, p, clip, dur, voices, music, clip.name, spoken)
    script["language"] = language
    folder, video = pipeline.produce(cfg, script)
    return folder, script, video
