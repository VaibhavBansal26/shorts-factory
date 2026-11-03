"""Studio: Claude writes a 30-40s script, you record yourself reading it, and this builds the reel.

Layout (like an explainer Short): the opening and closing lines are full-screen face-cam; in between the screen splits
into an animated graphic on top (nodes, meter, card, steps, compare, stat or a meme) and your face-cam below, with word
by word captions. Your own voice is kept; silences are trimmed and EDM background music is ducked under you.
"""
import json
import math
import re
import subprocess
from datetime import date
from pathlib import Path

import anthropic
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import icons, media, music, seo
from . import memes as memes_mod
from .config import ROOT, resolve
from .ff import FFMPEG, duration
from .render import _find_font

W, H, FPS = 1080, 1920, 30
GH = 1160  # height of the graphic panel in split layout
PH = H - GH  # face-cam panel below it
WPS = 2.5  # spoken words per second when reading naturally
MAX_SECONDS = 48.0
WHITE, MUTED = (245, 247, 250), (170, 182, 205)
BG_TOP, BG_BOT = (14, 24, 52), (30, 52, 108)

SYSTEM = """You write the spoken script for a 30-40 second vertical explainer Short that the channel owner will READ ON CAMERA.
The edit shows their face full-screen for the opening line and the closing line, and in between a graphic on top with their
face below. So every middle beat needs a simple on-screen visual that illustrates what is being said.

Rules:
- Total 80-100 spoken words (about 2.5 words per second). 6-7 beats. Beat 1 is the hook (face only, visual type "face"):
  a surprising question or claim under 14 words. The last beat is a takeaway plus a question for viewers (visual "face").
- Plain, conversational English the owner can say naturally. Short sentences. No jargon without a quick explanation.
- Teach one true, specific idea about AI / software engineering. No invented statistics or quotes; numbers in visuals must be
  illustrative round figures and framed as an example. No emojis, no hashtags in spoken text.
- Prefer "icons" whenever the speaker names concrete things (tools, files, money, time, bugs, a person...): items = the
  1-4 things in the order they are SAID (1-3 words each), icons = one icon per item. Each one pops up the moment it is spoken.
- Visual types for middle beats: icons (see above), nodes (a central AI box with 3-4 labelled inputs in items), meter (a bar that fills: value,
  max, unit, optional label), card (a titled card with 2-4 short lines in items), steps (3-4 short steps in items),
  compare (items = [left text, right text], title = heading), stat (big = a short number/phrase, label under it),
  meme (a meme visual; at most one or two per video; vary the style: relationship / boy-girl, chat, expectation vs reality, Indian or Hinglish humour, or a photo template).
- On-screen text is short: titles under 5 words, items under 6 words.
- Write metadata for YouTube: title (<=70 chars), description (2 sentences), up to 6 tags."""

TOOL = {
    "name": "submit_script",
    "description": "Submit the script and visuals.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"}, "description": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 6},
            "beats": {"type": "array", "items": {"type": "object", "properties": {
                "say": {"type": "string", "description": "exactly what the owner says in this beat"},
                "visual": {"type": "object", "properties": {
                    "type": {"type": "string", "enum": ["face", "icons", "nodes", "meter", "card", "steps", "compare", "stat", "meme"]},
                    "title": {"type": "string"}, "items": {"type": "array", "items": {"type": "string"}},
                    "icons": {"type": "array", "items": {"type": "string", "enum": icons.NAMES}},
                    "value": {"type": "number"}, "max": {"type": "number"}, "unit": {"type": "string"},
                    "label": {"type": "string"}, "big": {"type": "string"},
                    "meme_template": {"type": "string"}, "top_text": {"type": "string"}, "bottom_text": {"type": "string"},
                    "meme_style": {"type": "string", "enum": ["template", "boy_girl", "chat", "expectation", "drake", "nobody"]},
                    "meme_lines": {"type": "array", "items": {"type": "string"}},
                }, "required": ["type"]},
            }, "required": ["say", "visual"]}},
        },
        "required": ["title", "description", "beats"],
    },
}

MOCK = {
    "title": "Why Your AI Forgets What You Told It",
    "description": "A quick explainer on context windows: why long chats make AI assistants drop your instructions. I break it down in 30 seconds.",
    "tags": ["AI", "LLM", "contextwindow", "promptengineering"],
    "beats": [
        {"say": "Ever notice your AI gets worse the longer you chat with it?", "visual": {"type": "face"}},
        {"say": "That's not random. Every model can only hold a limited amount of text in its head at once.",
         "visual": {"type": "nodes", "title": "What fits in its head", "items": ["Messages", "Files", "Instructions", "Search results"]}},
        {"say": "We call that limit the context window, and everything you send eats into it.",
         "visual": {"type": "meter", "title": "Context window", "value": 90, "max": 100, "unit": "k tokens", "label": "Example numbers"}},
        {"say": "When it fills up, the app has to squeeze or drop the oldest parts of the conversation.",
         "visual": {"type": "steps", "title": "When it's full", "items": ["Oldest messages get trimmed", "Details get summarised", "Early instructions can vanish"]}},
        {"say": "So a rule you gave at the start may simply be gone.",
         "visual": {"type": "stat", "big": "Gone", "label": "your first instruction"}},
        {"say": "Fix it by repeating key rules, starting fresh chats for new tasks, and keeping prompts tight. Which one do you forget most?",
         "visual": {"type": "face"}},
    ],
}


def have_key() -> bool:
    import os
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def write_script(cfg: dict, topic: str = "", avoid: str = "") -> dict:
    """Claude writes the script; without a key a hand-written example is returned."""
    if not have_key():
        return json.loads(json.dumps(MOCK))
    client = anthropic.Anthropic()
    ask = (f"Topic: {topic}" if topic.strip() else "Pick a fresh, useful topic about AI agents, LLMs or software "
           "engineering that developers keep getting wrong.") + (f"\nDo not repeat: {avoid}" if avoid else "")
    feedback = ""
    names = "; ".join(m["name"] for m in media.meme_templates()[:70])
    if names:
        ask += f"\nMEME TEMPLATES (use these exact names for photo style): {names}\n{memes_mod.HELP}"
    for _ in range(3):
        resp = client.messages.create(model=cfg["llm"]["model"], max_tokens=2500, system=SYSTEM, tools=[TOOL],
                                      tool_choice={"type": "auto"},
                                      messages=[{"role": "user", "content": ask + feedback}])
        block = next((b for b in resp.content if b.type == "tool_use"), None)
        if block is None:
            feedback = "\nAnswer by calling submit_script."
            continue
        s = block.input
        try:
            if isinstance(s.get("beats"), str):  # the model sometimes returns the list as a JSON string
                s["beats"] = json.loads(s["beats"])
            for b in s["beats"]:
                if isinstance(b.get("visual"), str):
                    b["visual"] = json.loads(b["visual"]) if b["visual"].startswith("{") else {"type": b["visual"]}
            words = sum(len(b["say"].split()) for b in s["beats"])
            if 70 <= words <= 110 and s["beats"][0]["visual"]["type"] == "face" and s["beats"][-1]["visual"]["type"] == "face":
                return s
            feedback = (f"\nFix: the script had {words} words; it must be 80-100 words with the first and last beats "
                        "using visual type face.")
        except Exception:
            feedback = "\nFix: beats must be a list of objects with 'say' and a 'visual' object."
            s = None
    if not s:
        raise RuntimeError("Claude returned a script in an unexpected shape. Try again.")
    return s


# ---------------------------------------------------------------- preparing the recording
def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-400:])
    return r.stderr


def trim_silences(src: Path, out: Path, min_gap: float = 0.5, keep: float = 0.14) -> float:
    """Jump-cut the pauses out of the recording. Returns the new duration."""
    err = subprocess.run([FFMPEG, "-hide_banner", "-i", str(src), "-af", f"silencedetect=n=-34dB:d={min_gap}",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    total = duration(src)
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    segs, cur = [], 0.0
    for i, s in enumerate(starts):
        s = max(0.0, s)
        if s - cur > 0.25:
            segs.append((max(0.0, cur - (keep if cur > 0 else 0)), s + keep))
        cur = ends[i] if i < len(ends) else total
    if total - cur > 0.25:
        segs.append((max(0.0, cur - keep), total))
    if not segs:
        segs = [(0.0, total)]
    parts = "".join(f"[0:v]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS[v{i}];[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS[a{i}];"
                    for i, (a, b) in enumerate(segs))
    ins = "".join(f"[v{i}][a{i}]" for i in range(len(segs)))
    fc = f"{parts}{ins}concat=n={len(segs)}:v=1:a=1[v][a];[v]fps={FPS}[vf]"
    _run([FFMPEG, "-y", "-loglevel", "error", "-i", str(src), "-filter_complex", fc, "-map", "[vf]", "-map", "[a]",
          "-t", str(MAX_SECONDS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-b:a", "192k", str(out)])
    return duration(out)


def extract_voice(src: Path, out: Path):
    _run([FFMPEG, "-y", "-loglevel", "error", "-i", str(src), "-vn", "-af",
          "highpass=f=80,loudnorm=I=-15:TP=-1.5:LRA=9", "-ar", "44100", "-ac", "2", str(out)])


def align(beats: list[dict], voice: Path) -> list[dict]:
    """Word timings for the script, spread over the speech in the recording. Beat edges snap to real pauses."""
    total = duration(voice)
    err = subprocess.run([FFMPEG, "-hide_banner", "-i", str(voice), "-af", "silencedetect=n=-32dB:d=0.16",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    s0 = ends[0] if starts and starts[0] <= 0.05 and ends else 0.0
    e0 = starts[-1] if starts and (len(starts) > len(ends) or (ends and ends[-1] >= total - 0.05)) else total
    if e0 - s0 < 5:
        s0, e0 = 0.0, total
    pauses = [((a + b) / 2) for a, b in zip(starts, ends) if s0 < (a + b) / 2 < e0]

    toks = [(bi, w) for bi, b in enumerate(beats) for w in b["say"].split()]
    weights = []
    for _, w in toks:
        weights.append(len(w) + 2 + (8 if re.search(r"[.?!]$", w) else 4 if re.search(r"[,;:]$", w) else 0))
    cum, acc = [0.0], 0.0
    for wt in weights:
        acc += wt
        cum.append(acc)
    scale = (e0 - s0) / acc
    tstart = [s0 + c * scale for c in cum]

    bounds, i = [0.0], 0  # beat edges: nearest pause to the proportional guess
    for bi, b in enumerate(beats[:-1]):
        i += len(b["say"].split())
        guess = tstart[i]
        near = min(pauses, key=lambda p: abs(p - guess), default=None)
        bounds.append(near if near is not None and abs(near - guess) < 0.7 else guess)
    bounds.append(total)
    bounds = [max(a, bounds[k - 1] + 0.4) if k else 0.0 for k, a in enumerate(bounds)]  # keep beats ordered

    out, idx = [], 0
    for bi, b in enumerate(beats):
        n = len(b["say"].split())
        t0, t1 = bounds[bi], max(bounds[bi + 1], bounds[bi] + 0.5)
        ws = weights[idx:idx + n]
        speech0 = t0 if bi else s0
        speech1 = t1 if bi < len(beats) - 1 else e0
        span, c, words = max(0.3, speech1 - speech0), 0.0, []
        for w, wt in zip(b["say"].split(), ws):
            words.append((w, speech0 + c / sum(ws) * span, speech0 + (c + wt) / sum(ws) * span))
            c += wt
        out.append({"start": t0, "end": t1, "words": words})
        idx += n
    return out


# ---------------------------------------------------------------- drawing
def ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def pop(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1 + 0.12 * math.sin(x * math.pi) if x < 1 else 1.0


class Studio:
    def __init__(self, cfg: dict, script: dict, timing: list[dict], folder: Path):
        self.cfg, self.script, self.timing, self.folder = cfg, script, timing, folder
        self.beats = script["beats"]
        self.accent = tuple(cfg.get("studio", {}).get("accent", (96, 165, 250)))
        self.font_path = _find_font(cfg)
        self._fonts = {}
        self.panel_bg = self._gradient(W, GH)
        self.logo = self._logo()
        self.memes = {}
        self.cache = {}
        self._prep_memes()

    # ---- helpers
    def font(self, size):
        if size not in self._fonts:
            self._fonts[size] = (ImageFont.truetype(self.font_path, size) if self.font_path
                                 else ImageFont.load_default(size=size))
        return self._fonts[size]

    def _gradient(self, w, h):
        col = Image.new("RGB", (1, h))
        for y in range(h):
            t = y / h
            col.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOT)))
        return col.resize((w, h))

    def _logo(self):
        p = resolve(self.cfg, self.cfg["channel"]["logo"])
        if not p.exists():
            return None
        img = Image.open(p).convert("RGBA")
        return img.resize((int(img.width * 96 / img.height), 96), Image.LANCZOS)

    def _prep_memes(self):
        for i, b in enumerate(self.beats):
            v = b["visual"]
            if v["type"] != "meme":
                continue
            try:
                font = next((p for p in ["/System/Library/Fonts/Supplemental/Impact.ttf", "C:/Windows/Fonts/impact.ttf", *self.cfg["video"]["fonts"]]
                             if Path(p).exists()), None)
                p = media.make_meme(v, self.folder / f"meme{i}.png", font, self.cfg)
                self.memes[i] = Image.open(p).convert("RGB")
            except Exception as e:
                print(f"  meme skipped ({e}); showing a card instead")
                v["type"] = "card"
                v.setdefault("title", "Key idea")
                v.setdefault("items", [v.get("top_text", ""), v.get("bottom_text", "")])

    def wrap(self, text, size, max_w):
        f, d = self.font(size), ImageDraw.Draw(Image.new("RGB", (1, 1)))
        lines, cur = [], ""
        for w in text.split():
            t = f"{cur} {w}".strip()
            if d.textlength(t, font=f) <= max_w or not cur:
                cur = t
            else:
                lines.append(cur)
                cur = w
        return lines + ([cur] if cur else [])

    def fit(self, text, max_w, max_h, start=84, minimum=34):
        size = start
        while size > minimum:
            lines = self.wrap(text, size, max_w)
            if len(lines) * size * 1.2 <= max_h:
                return size, lines
            size -= 4
        return minimum, self.wrap(text, minimum, max_w)

    def text_block(self, d, text, cx, y, max_w, max_h, fill=WHITE, start=84, anchor="mt", stroke=0):
        size, lines = self.fit(text, max_w, max_h, start)
        for ln in lines:
            d.text((cx, y), ln, font=self.font(size), fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=(0, 0, 0))
            y += int(size * 1.2)
        return y

    # ---- timing tied to the voice
    def reveals(self, bi, items):
        """Local times at which each item should appear: when the narrator first says one of its words, else spread out."""
        if bi in self.cache:
            return self.cache[bi]
        words = self.timing[bi]["words"]
        start = self.timing[bi]["start"]
        dur = max(1.0, self.timing[bi]["end"] - start)
        out, pos = [], 0
        for i, it in enumerate(items):
            keys = {re.sub(r"\W", "", w.lower()) for w in it.split() if len(re.sub(r"\W", "", w)) > 3}
            hit = next((j for j in range(pos, len(words)) if re.sub(r"\W", "", words[j][0].lower()) in keys), None)
            if hit is not None:
                out.append(max(0.15, words[hit][1] - start - 0.12))
                pos = hit + 1
            else:
                out.append(0.2 + i * dur * 0.7 / max(1, len(items)))
        for i in range(1, len(out)):  # keep them in order and apart
            out[i] = max(out[i], out[i - 1] + 0.3)
        self.cache[bi] = out
        return out

    def kick(self, bi, t):
        """1 at the instant a word starts, fading to 0: a small pulse that follows the speech."""
        ws = [w[1] for w in self.timing[bi]["words"] if w[1] <= t]
        return max(0.0, 1 - (t - ws[-1]) / 0.2) if ws else 0.0

    def _glow(self):
        if "glow" not in self.cache:
            sp = Image.new("RGBA", (520, 520), (0, 0, 0, 0))
            ImageDraw.Draw(sp).ellipse((60, 60, 460, 460), fill=(*self.accent, 70))
            self.cache["glow"] = sp.filter(ImageFilter.GaussianBlur(70))
        return self.cache["glow"]

    # ---- graphics (each draws onto a W x GH RGBA panel)
    def graphic(self, v, lt, idx):
        img = self.panel_bg.copy().convert("RGBA")
        for k, (gx, gy, sp) in enumerate(((0.2, 0.3, 0.7), (0.8, 0.55, 0.5), (0.45, 0.85, 0.6))):  # drifting light, so it's never static
            gl = self._glow()
            x = int((gx + 0.08 * math.sin(lt * sp + k * 2)) * W - 260)
            y = int((gy + 0.06 * math.cos(lt * sp * 0.8 + k)) * GH - 260)
            img.paste(gl, (x, y), gl)
        d = ImageDraw.Draw(img, "RGBA")
        ac = self.accent
        kind = v["type"]
        title = v.get("title", "")
        items = [s for s in v.get("items", []) if s]
        rt = self.reveals(idx, items) if items else []
        if title and kind not in ("stat", "meme"):
            self.text_block(d, title, W // 2, 330, 900, 130, fill=WHITE, start=64)
        if kind == "icons" and items:
            n = min(len(items), 4)
            names = list(v.get("icons") or [])
            size = {1: 400, 2: 330, 3: 270, 4: 270}[n]
            if n == 4:
                cells = [(W // 2 + dx * 280, 560 + dy * 330) for dy in (0, 1) for dx in (-1, 1)]
            else:
                gap = W // n
                cells = [(gap // 2 + i * gap, 640) for i in range(n)]
            for i in range(n):
                p = (lt - rt[i]) / 0.5
                if p <= 0:
                    continue
                q = ease(p) * (1 + 0.14 * math.sin(min(p, 1) * math.pi))  # overshoot pop
                ic = icons.draw(names[i] if i < len(names) else "star", size, ac)
                sz = max(8, int(size * q))
                ic = ic.resize((sz, sz), Image.LANCZOS)
                cx, cy = cells[i]
                bob = int(8 * math.sin(lt * 2.4 + i * 1.7))
                if p < 1.4:  # ring that expands as it lands
                    r = int(size * (0.5 + 0.35 * min(1, p)))
                    d.ellipse((cx - r, cy + bob - r, cx + r, cy + bob + r), outline=(*ac, int(180 * max(0, 1 - p / 1.4))), width=5)
                img.alpha_composite(ic, (cx - sz // 2, cy + bob - sz // 2))
                size_l, lines = self.fit(items[i], size + 60, 120, 46, 28)
                yy = cy + size // 2 + 26
                for ln in lines:
                    d.text((cx, yy), ln, font=self.font(size_l), fill=(*WHITE, int(255 * min(1, p))), anchor="mt", stroke_width=3, stroke_fill=(0, 0, 0))
                    yy += int(size_l * 1.2)
        elif kind == "nodes":
            cx, cy = W // 2, 640
            slots = [(250, 480), (830, 480), (250, 820), (830, 820)]
            for i, txt in enumerate(items[:4]):
                p = ease((lt - rt[i]) / 0.5)
                sx, sy = slots[i]
                if p > 0:
                    d.line([(cx, cy), (cx + (sx - cx) * p, cy + (sy - cy) * p)], fill=(*ac, 150), width=5)
                if p > 0.55:
                    q = pop((p - 0.55) / 0.45)
                    bw, bh = int(390 * q), int(100 * q)
                    d.rounded_rectangle((sx - bw // 2, sy - bh // 2, sx + bw // 2, sy + bh // 2), radius=30,
                                        fill=(24, 40, 88, 255), outline=(*ac, 255), width=4)
                    d.text((sx, sy), txt, font=self.font(36 if len(txt) < 16 else 30), fill=WHITE, anchor="mm")
            s = int(230 * pop(ease(lt / 0.5)))
            d.rounded_rectangle((cx - s // 2, cy - s // 2, cx + s // 2, cy + s // 2), radius=48, fill=(36, 62, 130, 255),
                                outline=(*ac, 255), width=6)
            eye = int(s * 0.17)
            for ex in (-0.22, 0.22):
                d.ellipse((cx + ex * s - eye, cy - 0.08 * s - eye, cx + ex * s + eye, cy - 0.08 * s + eye), fill=(*ac, 255))
            d.rounded_rectangle((cx - 0.22 * s, cy + 0.2 * s, cx + 0.22 * s, cy + 0.27 * s), radius=10, fill=(*ac, 255))
            d.line([(cx, cy - s // 2), (cx, cy - s // 2 - 36)], fill=(*ac, 255), width=8)
            d.ellipse((cx - 14, cy - s // 2 - 52, cx + 14, cy - s // 2 - 24), fill=(*ac, 255))
        elif kind == "meter":
            val, mx = float(v.get("value", 90)), float(v.get("max", 100)) or 100.0
            fill_to = ease(lt / 1.4) * val / mx
            x0, y0, x1, y1 = 100, 560, W - 100, 700
            d.rounded_rectangle((x0, y0, x1, y1), radius=36, fill=(20, 32, 70, 255), outline=(255, 255, 255, 60), width=3)
            col = (239, 90, 90) if fill_to > 0.88 else (*ac,)
            if fill_to > 0.01:
                d.rounded_rectangle((x0 + 8, y0 + 8, x0 + 8 + (x1 - x0 - 16) * fill_to, y1 - 8), radius=28, fill=(*col, 255))
            unit = v.get("unit", "")
            d.text((W // 2, y0 + 70), f"{val * ease(lt / 1.4):,.0f} / {mx:,.0f} {unit}".strip(), font=self.font(46),
                   fill=WHITE, anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0))
            if v.get("label"):
                d.text((W // 2, y1 + 70), v["label"], font=self.font(38), fill=MUTED, anchor="mm")
            if fill_to > 0.88 and lt > 1.3:
                d.text((W // 2, y1 + 150), "Almost full!", font=self.font(58), fill=(239, 90, 90), anchor="mm")
        elif kind == "card":
            d.rounded_rectangle((90, 470, W - 90, 960), radius=44, fill=(20, 32, 70, 255), outline=(*ac, 200), width=4)
            y = 520
            for i, txt in enumerate(items[:4]):
                p = ease((lt - rt[i]) / 0.4)
                if p <= 0:
                    continue
                size, lines = self.fit(txt, 800, 120, 52, 36)
                for ln in lines:
                    d.text((140 + (1 - p) * 60, y), ln, font=self.font(size), fill=(*WHITE, int(255 * p)), anchor="lt")
                    y += int(size * 1.2)
                y += 36
        elif kind == "steps":
            for i, txt in enumerate(items[:4]):
                p = ease((lt - rt[i]) / 0.45)
                if p <= 0:
                    continue
                y = 430 + i * 140
                ox = int((1 - p) * -300)
                d.rounded_rectangle((90 + ox, y, W - 90 + ox, y + 120), radius=34, fill=(20, 32, 70, 255), outline=(*ac, 200), width=3)
                d.ellipse((120 + ox, y + 20, 200 + ox, y + 100), fill=(*ac, 255))
                d.text((160 + ox, y + 60), str(i + 1), font=self.font(46), fill=(10, 18, 40), anchor="mm")
                size, lines = self.fit(txt, 740, 110, 46, 30)
                yy = y + 60 - len(lines) * int(size * 1.2) // 2
                for ln in lines:
                    d.text((230 + ox, yy), ln, font=self.font(size), fill=WHITE, anchor="lt")
                    yy += int(size * 1.2)
        elif kind == "compare":
            for i, txt in enumerate((items + ["", ""])[:2]):
                p = ease((lt - rt[i]) / 0.45)
                if p <= 0:
                    continue
                x0 = 70 + i * 490
                d.rounded_rectangle((x0, 480, x0 + 450, 480 + int(470 * p)), radius=40, fill=(20, 32, 70, 255),
                                    outline=((239, 90, 90) if i == 0 else (*ac,)), width=5)
                if p > 0.7:
                    self.text_block(d, txt, x0 + 225, 560, 380, 340, start=50)
            if lt > 0.8:
                d.ellipse((W // 2 - 48, 670, W // 2 + 48, 766), fill=(*ac, 255))
                d.text((W // 2, 718), "VS", font=self.font(40), fill=(10, 18, 40), anchor="mm")
        elif kind == "stat":
            s = pop(ease(lt / 0.5))
            big = v.get("big", "")
            m = re.search(r"\d[\d,]*\.?\d*", big)
            if m:  # numbers count up to their value
                raw = m.group(0)
                val = float(raw.replace(",", ""))
                cur = val * ease(lt / 0.9)
                txt = f"{cur:,.{len(raw.split('.')[1]) if '.' in raw else 0}f}" if "," in raw else (f"{cur:.{len(raw.split('.')[1])}f}" if "." in raw else f"{int(round(cur))}")
                big = big[:m.start()] + txt + big[m.end():]
            size = int(min(300, 1700 / max(3, len(big))) * s)
            d.text((W // 2, 600), big, font=self.font(max(60, size)), fill=(*ac, 255), anchor="mm", stroke_width=4,
                   stroke_fill=(0, 0, 0))
            if v.get("label"):
                self.text_block(d, v["label"], W // 2, 780, 900, 160, fill=WHITE, start=62)
        elif kind == "meme" and idx in self.memes:
            m = self.memes[idx]
            p = ease(lt / 0.4)
            sc = min(900 / m.width, 700 / m.height) * (0.85 + 0.15 * p)
            mm = m.resize((int(m.width * sc), int(m.height * sc)))
            img.paste(mm, ((W - mm.width) // 2, 330 + (700 - mm.height) // 2))
        return img

    def chrome(self, img, y0=48):
        d = ImageDraw.Draw(img)
        x = 60
        if self.logo:
            img.paste(self.logo, (x, y0), self.logo)
            x += self.logo.width + 20
        d.text((x, y0 + 30), self.cfg["channel"]["name"], font=self.font(36), fill=WHITE, anchor="lm", stroke_width=2, stroke_fill=(0, 0, 0))
        d.text((x, y0 + 72), self.cfg["channel"]["handle"], font=self.font(28), fill=(200, 210, 230), anchor="lm", stroke_width=2, stroke_fill=(0, 0, 0))

    def captions(self, img, t, bi, y, size=70):
        words = self.timing[bi]["words"]
        if not words:
            return
        cur = max([i for i, w in enumerate(words) if w[1] <= t] or [0])
        # chunks of up to 4 words, closed by punctuation
        chunks, c = [], []
        for i, w in enumerate(words):
            c.append(i)
            if len(c) >= 4 or re.search(r"[.?!,;:]$", w[0]):
                chunks.append(c)
                c = []
        if c:
            chunks.append(c)
        chunk = next((c for c in chunks if cur in c), chunks[-1])
        d = ImageDraw.Draw(img)
        f = self.font(size)
        parts = [words[i][0] for i in chunk]
        total = sum(d.textlength(p + " ", font=f) for p in parts)
        while total > W - 120 and size > 40:
            size -= 4
            f = self.font(size)
            total = sum(d.textlength(p + " ", font=f) for p in parts)
        x = (W - total) / 2
        for i, p in zip(chunk, parts):
            col = self.accent if i == cur else WHITE
            d.text((x, y), p, font=f, fill=col, anchor="lm", stroke_width=7, stroke_fill=(0, 0, 0))
            x += d.textlength(p + " ", font=f)

    def beat_at(self, t):
        for i, b in enumerate(self.timing):
            if t < b["end"]:
                return i
        return len(self.timing) - 1

    def compose(self, t, face_full: Image.Image, face_panel: Image.Image, total):
        bi = self.beat_at(t)
        v = self.beats[bi]["visual"]
        lt = t - self.timing[bi]["start"]
        full_layout = v["type"] == "face"

        def full():
            img = face_full.copy()
            self.chrome(img)
            self.captions(img, t, bi, 1480, 76)
            return img

        def split():
            img = Image.new("RGB", (W, H))
            g = self.graphic(v, lt, bi).convert("RGB")
            z = 1 + 0.025 * min(1.0, lt / 4) + 0.012 * self.kick(bi, t)  # slow push-in plus a small beat on every spoken word
            if z > 1.002:
                bw, bh = W / z, GH / z
                g = g.resize((W, GH), Image.BILINEAR, box=((W - bw) / 2, (GH - bh) / 2, (W + bw) / 2, (GH + bh) / 2))
            img.paste(g, (0, 0))
            img.paste(face_panel, (0, GH))
            d = ImageDraw.Draw(img)
            d.rectangle((0, GH - 4, W, GH), fill=self.accent)
            self.chrome(img)
            self.captions(img, t, bi, GH - 70, 64)
            return img

        # short cross-fade where the layout changes
        edge = lt < 0.18 and bi > 0 and (self.beats[bi - 1]["visual"]["type"] == "face") != full_layout
        a = full() if full_layout else split()
        if edge:
            b = split() if full_layout else full()
            a = Image.blend(b, a, ease(lt / 0.18))
        d = ImageDraw.Draw(a)
        d.rounded_rectangle((60, 1884, W - 60, 1892), radius=4, fill=(255, 255, 255, 60))
        d.rounded_rectangle((60, 1884, 60 + (W - 120) * min(1, t / total), 1892), radius=4, fill=self.accent)
        return a


def find_face(src: Path):
    """Where the head is in the recording, as fractions of the frame: (centre x, top y, head width), or None when it can't be told.
    Uses the same local person-segmentation model as the background clean-up, sampled over the whole clip."""
    try:
        import cv2
        import numpy as np
        from mediapipe import Image as MpImage, ImageFormat
        from mediapipe.tasks.python import BaseOptions, vision
        from .enhance import MODEL, _size
        w0, h0 = _size(src)
        w = 288
        h = int(h0 * w / w0) // 2 * 2
        seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
            base_options=BaseOptions(model_asset_path=str(MODEL)), running_mode=vision.RunningMode.IMAGE,
            output_confidence_masks=True, output_category_mask=False))
        raw = subprocess.run([FFMPEG, "-loglevel", "error", "-i", str(src), "-vf", f"fps=2,scale={w}:{h}", "-frames:v", "40",
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        xs, tops, hws = [], [], []
        for k in range(len(raw) // (w * h * 3)):
            fr = np.frombuffer(raw, np.uint8, w * h * 3, k * w * h * 3).reshape(h, w, 3).copy()
            m = seg.segment(MpImage(image_format=ImageFormat.SRGB, data=fr)).confidence_masks[-1].numpy_view().reshape(h, w) > 0.5
            rows = np.where(m.sum(axis=1) > w * 0.04)[0]
            if len(rows) < h * 0.15:
                continue
            top = int(rows[0])
            band = m[top:top + max(6, int(h * 0.16))]  # the head: the first stretch below the top of the person
            cols = np.where(band.any(axis=0))[0]
            xs.append((cols[0] + cols[-1]) / 2 / w)
            hws.append((cols[-1] - cols[0]) / w)
            tops.append(top / h)
        if len(xs) < 3:
            return None
        return float(np.median(xs)), float(np.median(tops)), float(np.median(hws))
    except Exception as e:
        print(f"  face finder skipped ({e})")
        return None


def _decoder(src: Path, w, h, face_x, face=None, zoom_out=False):
    """Scale the recording to fill w x h and place it so the head sits in the middle, with a little room above it.
    With zoom_out, a close-up is shrunk until the head is about 40% of the width; the sides continue the picture's edge colour."""
    if face:
        sw, sh = _dims(src)
        cx, top, hw = face
        k = max(w / sw, h / sh)
        if zoom_out:
            k = max(h / sh, min(k, 0.40 * w / max(hw * sw, 1)))
        zw, zh = int(round(sw * k / 2)) * 2, int(round(sh * k / 2)) * 2
        ox = int(w / 2 - cx * zw)
        oy = min(0, max(h - zh, int(0.16 * h - top * zh)))
        if zw >= w:  # fills the width: just crop
            vf = f"scale={zw}:{zh},crop={w}:{h}:{-min(0, max(w - zw, ox))}:{-oy}"
        else:  # narrower than the panel: carry the picture's own edge colour out to the sides (no ghost of the person)
            lw = max(0, min(w - zw, ox))
            rw = w - zw - lw
            labels = "[f][fb]" + ("[l0]" if lw else "") + ("[r0]" if rw else "")
            parts = [f"scale={zw}:{zh},crop={zw}:{h}:0:{-oy},format=yuva420p,split={labels.count('[')}{labels}"]
            row = []
            if lw:
                parts.append(f"[l0]format=yuv420p,crop=6:{h}:0:0,scale={lw}:{h}[l]")
                row.append("[l]")
            parts.append("[fb]format=yuv420p[fc]")
            row.append("[fc]")
            if rw:
                parts.append(f"[r0]format=yuv420p,crop=6:{h}:{zw - 6}:0,scale={rw}:{h}[r]")
                row.append("[r]")
            parts.append(f"{''.join(row)}hstack={len(row)},boxblur=40:4[bg]")  # soft colour field the picture sits on
            fl, fr = "min(1,X/60)" if lw else "1", f"min(1,({zw - 1}-X)/60)" if rw else "1"
            parts.append(f"[f]geq=lum='p(X,Y)':cb='p(X,Y)':cr='p(X,Y)':a='255*{fl}*{fr}'[ff]")  # feathered edges: no hard seam
            parts.append(f"[bg][ff]overlay={lw}:0:shortest=1,format=rgb24")
            vf = ";".join(parts)
        cmd = [FFMPEG, "-loglevel", "error", "-i", str(src), "-filter_complex", vf]
    else:
        vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}:x='(iw-ow)*{face_x}':y='(ih-oh)*0.35'"
        cmd = [FFMPEG, "-loglevel", "error", "-i", str(src), "-vf", vf]
    return subprocess.Popen(cmd + ["-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)


def _dims(src: Path):
    """Size as it is played: phone clips are stored sideways with a rotation flag."""
    err = subprocess.run([FFMPEG, "-hide_banner", "-i", str(src)], capture_output=True, text=True).stderr
    m = re.search(r"Video:.*?, (\d{2,5})x(\d{2,5})", err)
    w, h = int(m.group(1)), int(m.group(2))
    r = re.search(r"rotation of (-?\d+)", err)
    return (h, w) if r and abs(int(r.group(1))) % 180 == 90 else (w, h)


def _read(p, w, h, last):
    buf = p.stdout.read(w * h * 3)
    if len(buf) < w * h * 3:
        return last
    return Image.frombytes("RGB", (w, h), buf)


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40]


def make(cfg: dict, script: dict, clip: Path, music_choice: str = "auto", face_x: float | None = None,
         background: str = "none", polish: bool = False):
    """Build the reel from the edited script + the uploaded recording. Returns (folder, script, video_path)."""
    clip = Path(clip).resolve()
    beats = [b for b in script["beats"] if b["say"].strip()]
    if len(beats) < 2:
        raise RuntimeError("The script needs at least two beats")
    script["beats"] = beats
    folder = ROOT / "output" / f"{date.today()}_{slug(script['title'])}"
    folder.mkdir(parents=True, exist_ok=True)
    print(f"\n▶ Studio reel: {script['title']}")
    clean, voice = folder / "clean.mp4", folder / "voice.wav"
    dur = trim_silences(clip, clean)
    print(f"  recording trimmed to {dur:.1f}s")
    extract_voice(clean, voice)
    if background != "none" or polish:  # optional: new backdrop and lighting balance for the face-cam
        print(f"  enhancing recording (background: {background}, lighting polish: {polish})")
        enh = folder / "enhanced.mp4"
        try:
            from . import enhance
            enhance.run(clean, enh, background, polish, tuple(cfg.get("studio", {}).get("accent", (96, 165, 250))))
            clean.unlink()
            enh.rename(clean)
        except Exception as e:
            print(f"  enhancement skipped ({e})")
            enh.unlink(missing_ok=True)
    try:
        from . import asr
        if not asr.available():
            raise RuntimeError("speech model not installed")
        timing = asr.align(beats, voice)
        print("  timing: from the real speech")
    except Exception as e:
        print(f"  timing: estimated ({e})")
        timing = align(beats, voice)

    full = {
        "format": "studio", "title": script["title"][:90], "description": script.get("description", ""),
        "tags": script.get("tags", []), "music": music_choice, "beats": beats,
        "channel_id": cfg["channel"].get("id", "main"), "accent": script.get("accent"),
        "source": {"name": "Original", "title": script["title"], "url": ""},
        "scenes": [{"narration": b["say"], "layout": "studio", "headline": b["visual"].get("title", ""),
                    "visual": {"type": "none" if b["visual"]["type"] == "face" else b["visual"]["type"]}} for b in beats],
    }
    (folder / "script.json").write_text(json.dumps(full, indent=2))
    if seo.ensure(cfg, full):
        print(f"  seo: {full['seo']['title']}")
        (folder / "script.json").write_text(json.dumps(full, indent=2))
    track = music.pick(cfg, "studio", music_choice)
    print(f"  music: {track.name if track else 'none'}")

    st = Studio(cfg, script, timing, folder)
    total = dur + 0.3
    frames = int(total * FPS)
    out = folder / "video.mp4"
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(voice)]
    if track:
        vol = cfg["video"].get("music_volume", 0.14) * 0.9
        cmd += ["-stream_loop", "-1", "-i", str(track), "-filter_complex",
                f"[1:a]asplit=2[v1][v2];[2:a]volume={vol}[m];[m][v2]sidechaincompress=threshold=0.02:ratio=8:attack=15:release=400[duck];"
                f"[v1][duck]amix=inputs=2:duration=first:normalize=0,afade=t=out:st={max(0, total - 1.0):.2f}:d=1.0[a]",
                "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
            "-t", f"{total:.2f}", "-movflags", "+faststart", str(out)]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    face = find_face(clean) if face_x is None else None  # None = find it; a number = the position the user chose
    print(f"  face: {'auto ' + str(tuple(round(v, 2) for v in face)) if face else 'manual/centre'}")
    fx = 0.5 if face_x is None else face_x
    dec_full, dec_panel = _decoder(clean, W, H, fx, face), _decoder(clean, W, PH, fx, face, zoom_out=True)
    lf = lp = Image.new("RGB", (W, H), (0, 0, 0))
    lp = Image.new("RGB", (W, PH), (0, 0, 0))
    try:
        for n in range(frames):
            lf, lp = _read(dec_full, W, H, lf), _read(dec_panel, W, PH, lp)
            enc.stdin.write(st.compose(n / FPS, lf, lp, total).tobytes())
    finally:
        enc.stdin.close()
        enc.wait()
        for p in (dec_full, dec_panel):
            p.kill()
    if enc.returncode:
        raise RuntimeError("ffmpeg failed")
    clean.unlink(missing_ok=True)
    print(f"  rendered {out.name}")
    return folder, full, out
