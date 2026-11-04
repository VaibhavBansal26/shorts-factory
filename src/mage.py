"""Mage: faceless system-design explainer Shorts. A Hinglish (or English) voice walks through a problem while animated
blueprint-style diagrams build up on screen: title and interview question, numbered steps, data flowing between boxes,
grids that fill with counters and heat, hex cells, a phone mock-up, and a closing follow card.

Claude writes the storyboard (a scene per spoken beat, each naming one diagram type and its data); this module draws every
frame itself, so there are no stock clips or image licences involved. Style notes come from studying a reference Short
frame by frame: dark navy blueprint grid, small mono header with the series line and handle, a "STEP n" sub-header per
scene, one idea per scene, objects appearing as they are spoken, short mono chips instead of subtitles, a yellow
"THIS IS CALLED ..." card when a term is named, and a follow card at the end.
"""
import hashlib
import json
import math
import random
import re
import subprocess
from datetime import date
from pathlib import Path

import anthropic
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import music, seo, tts
from .config import ROOT
from .ff import FFMPEG
from .mage_worlds import THEMES, Worlds
from .render import _find_font

W, H, FPS = 1080, 1920, 30
BG_TOP, BG_BOT = (8, 15, 38), (16, 30, 70)
INK, MUTED = (236, 242, 255), (140, 158, 200)
YEL, CYAN, GREEN, RED, AMBER = (250, 204, 21), (56, 189, 248), (74, 222, 128), (248, 113, 113), (251, 191, 36)
BOX, LINE = (14, 26, 62), (70, 110, 190)

SCENE_TYPES = ["title", "steps", "flow", "grid", "hex", "phone", "counter", "devices", "pipeline", "timer", "citymap", "seatmap",
               "stadium", "profiles", "funnel", "queue", "cdn", "cta"]

SYSTEM = """You write storyboards for a 45-70 second vertical "system design explained" Short. A voice narrates while animated
diagrams build on screen. One idea per scene, 8-12 scenes. The storyboard is read aloud, so write `say` the way a friendly senior
engineer talks: short sentences, concrete numbers, one real insight per scene (a trap, a trade-off or a number), never a list
of buzzwords. Teach something true and specific. Numbers used as examples must be framed as examples.

Scene 1 is type "title" (the system name, a tag, and the interview question). The last scene is type "cta".
In between, build the design step by step: scenes with a `label` like "STEP 1 · LOCATION UPDATES" (max 5 words, shown at the top).
Every scene has `type` and `data`:
- title: {title, tag, question}              big name, small tag chip, then the question in a yellow box
- steps: {items:[...2-5 short lines...], tone:"good"|"bad"}   numbered rows that appear as they are spoken ("bad" = red, for traps)
- flow: {nodes:[{label, sub}] (2-4), packet, spike:true|false, note}   boxes with data packets moving along; spike = a flood and the
        last node turns red
- grid: {rows, cols, mode:"cells"|"counter"|"heat", highlight:[row,col] optional, note}   cells with moving dots / numbers /
        a red-amber-green heat map
- hex: {mode:"compare"|"ring", note}          square vs hexagon neighbours, or a hex cell with its neighbour ring lighting up
- phone: {title, rows:[{label, value}], button, flash:true|false, note}   an app screen; flash = the price row flashes
- counter: {label, from, to, caption}        a big number that counts, with a caption
- devices: {devices:[{kind:"laptop"|"phone"|"server", title, qr:true|false, code:"974 939", lines:[...]}] (2-3), flows:[label,...], note}
        real-looking screens side by side (a laptop showing a QR code or a login box, a phone with an app, a server) with a packet
        (a key, a code) travelling from each device to the next; `flows[i]` labels the packet leaving device i
- pipeline: {inputs:[{label}] (1-3), fn, sub, output, note, bracket}   inputs flow into a function box (HMAC, SHA-256...), and a long
        hex output is revealed; `bracket` labels the output (e.g. "40 AKSHAR KA CODE")
- timer: {label, start_label, end_label, total, divide, unit, caption}   a clock, a timeline from the start date to now, a counter
        up to `total` seconds, then "÷ divide" and the whole-number result in a box
- citymap: {mode:"match"|"route"|"heat", rider, eta, note}   a city map with cabs driving about: "match" = a search ring from the rider
        catching the nearest cab, "route" = a trip drawn from A to B, "heat" = surge zones glowing where demand is high
- seatmap: {mode:"hold"|"race"|"soldout", venue:"cinema"|"concert", stage, note}   a seat map: "hold" = seats held with a countdown, "race" =
        two users click the same seat and the database lock decides, "soldout" = seats selling out
- stadium: {sport:"cricket"|"football", mode:"crowd"|"gates"|"load", count, note}   a field and a rippling crowd; "gates" = fans streaming in,
        "load" = a request-rate meter bursting at kick-off
- profiles: {people:[{name, age, city, tags:[..]} x2], score, criteria:[..], note}   two profile cards, shared interests lighting up and a
        match-score heart between them (matchmaking, dating, hiring, delivery matching)
- funnel: {stages:[{label, value} x3-5], note}   a funnel narrowing, e.g. 10 crore profiles -> 40,000 -> 200 -> 10, with particles falling through
- queue: {title, gate, people, per_sec, note}   a crowd in a waiting room, let through the gate a few at a time
- cdn: {origin, nodes:[city names], note}   one origin and edge servers near groups of viewers, cache hits flowing
- cta: {handle}                              follow card
Optional on any scene: `chips` (1-3 tiny labels, max 5 words each, appear in order while spoken) and `term`
{kicker, name, sub} (a card "THIS IS CALLED / name / sub" shown near the end of the scene when you name a concept).
Pick the picture that actually shows the idea, and SHOW THE PRODUCT instead of describing it:
cab/delivery = citymap; ticketing/booking = seatmap + queue (+ stadium or title art for the venue); sports apps = stadium; matrimony,
dating, hiring = profiles + funnel; video streaming = cdn; chat = flow + devices. Use at most ONE "steps" scene in the whole video, use
at least 4 different illustrated types, and never repeat a type back to back. Set `theme` to the kind of product (it changes the colours and
the art on the title scene). Base every number and claim on the RESEARCH BRIEF you are given; label estimates as examples.
Metadata: title (<=70 chars), description (2 sentences), up to 6 tags."""

TOOL = {
    "name": "submit_storyboard",
    "description": "Submit the storyboard.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"}, "description": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 6},
            "series": {"type": "string", "description": "short header line, e.g. UBER LIVE HEATMAP"},
            "theme": {"type": "string", "enum": ["cab", "ticket", "sport", "match", "video", "chat", "pay", "social", "generic"]},
            "scenes": {"type": "array", "items": {"type": "object", "properties": {
                "say": {"type": "string"}, "label": {"type": "string"},
                "type": {"type": "string", "enum": SCENE_TYPES},
                "data": {"type": "object"},
                "chips": {"type": "array", "items": {"type": "string"}},
                "term": {"type": "object"},
            }, "required": ["say", "type", "data"]}},
        },
        "required": ["title", "scenes"],
    },
}

MOCK = {
    "title": "URL Shortener Kaise Banta Hai?", "series": "URL SHORTENER", "tags": ["systemdesign", "coding", "backend"],
    "description": "How a URL shortener works: IDs, a key-value store and a cache. System design interview in 60 seconds.",
    "scenes": [
        {"say": "Bit dot ly jaise links sirf das characters ke hote hain. Billions links kaise store karoge?", "type": "title",
         "data": {"title": "URL Shortener", "tag": "SYSTEM DESIGN INTERVIEW", "question": "Billions links, ek chhota ID. Kaise?"}},
        {"say": "Pehle ek chhota unique ID banate hain. Counter badhao, aur usse base sixty two mein badal do.", "label": "STEP 1 · SHORT ID",
         "type": "steps", "data": {"items": ["Counter badhao", "Base 62 mein badlo", "7 chars = 3.5 trillion links"]}},
        {"say": "Long link aur short ID ko key value store mein rakhte hain. Lookup ek millisecond ka kaam hai.", "label": "STEP 2 · STORE",
         "type": "flow", "data": {"nodes": [{"label": "Browser", "sub": "short.ly/aB3x"}, {"label": "App server"}, {"label": "KV store", "sub": "id → long url"}],
                                   "packet": "aB3x", "note": "GET aB3x → long url"},
         "term": {"kicker": "THIS IS CALLED", "name": "Key-Value Store", "sub": "id se seedha url"}},
        {"say": "Ab maan lo ek viral link par dus lakh log ek saath click karte hain. Database par bhaari load.", "label": "TRAP · VIRAL LINK",
         "type": "flow", "data": {"nodes": [{"label": "Users"}, {"label": "App server"}, {"label": "Database"}], "packet": "hit", "spike": True, "note": "10x traffic spike"}},
        {"say": "Solution cache hai. Popular links memory mein rakho, database tak jaana hi nahi padega.", "label": "STEP 3 · CACHE", "type": "counter",
         "data": {"label": "CACHE HIT", "from": 0, "to": 95, "caption": "% requests DB tak nahi jaate"},
         "term": {"kicker": "THIS IS CALLED", "name": "Caching", "sub": "hot data memory mein"}},
        {"say": "Engineering isi ko kehte hain. Follow karo aur dost ko bhejo.", "type": "cta", "data": {"handle": "@yourhandle"}},
    ],
}


RESEARCH_SYSTEM = """You are a staff engineer preparing a research brief for a 60-second system-design explainer Short about the topic you are
given. Use web search when it is available to check real facts (how the company actually builds it, public scale figures). Write a compact
brief with these sections:
THEME: one of cab, ticket, sport, match, video, chat, pay, social, generic.
PRODUCT: one line.
REAL SCALE: 3-5 figures, each marked PUBLIC (with the source name) or ESTIMATE.
CORE FLOW: 5-7 steps of how a request goes through the system.
HARD PROBLEMS: the 3 things that actually break at scale. For each: the problem, the standard fix, and the trade-off.
VISUALS: what should be SHOWN for each problem (for example cabs on a city map, a seat map being bought out, a waiting-room queue, a
match score between two profile cards, edge servers near viewers).
BEGINNER MISTAKES: 2 things people get wrong.
Be accurate. Do not invent company internals: if unsure, say so and give the common industry approach."""


def research(cfg: dict, topic: str) -> str:
    """A fact-checked brief the storyboard is written from. Tries web search; falls back to the model's own knowledge."""
    client = anthropic.Anthropic()
    msg = [{"role": "user", "content": f"Topic: {topic}"}]
    for tools in ([{"type": "web_search_20250305", "name": "web_search", "max_uses": 4}], None):
        try:
            kw = {"tools": tools} if tools else {}
            resp = client.messages.create(model=cfg["llm"]["model"], max_tokens=3000, system=RESEARCH_SYSTEM, messages=msg, **kw)
            text = "\n".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
            if len(text) > 200:
                return text[:6000]
        except Exception as e:
            print(f"  research ({'with web search' if tools else 'without'}) failed: {str(e)[:120]}")
    return ""


def _loads(text):
    """Parse JSON that a model sent as text, tolerating trailing junk such as a stray closing bracket."""
    text = text.strip()
    try:
        return json.loads(text)
    except ValueError:
        val, _ = json.JSONDecoder().raw_decode(text[text.index("[" if text.lstrip().startswith("[") else "{"):])
        return val


def have_key() -> bool:
    import os
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def slug(s: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40]
    return out or "mage-" + hashlib.sha1(s.encode()).hexdigest()[:8]


def write_script(cfg: dict, topic: str, language: str = "hinglish", seconds: int = 60) -> dict:
    if not have_key():
        return json.loads(json.dumps(MOCK))
    lang = {"hinglish": "Write `say`, labels and chips in Hinglish: Hindi in Roman letters mixed with common English tech terms, "
                        "the way Indian engineers talk. Do not use Devanagari.",
            "en": "Write everything in clear, simple English."}.get(language, "Write everything in clear, simple English.")
    brief = research(cfg, topic)
    ask = (f"Topic: {topic}\nTarget length about {seconds} seconds of speech (about {int(seconds * 2.1)} spoken words in total).\n{lang}"
           + (f"\n\nRESEARCH BRIEF (use these facts and visuals):\n{brief}" if brief else ""))
    client = anthropic.Anthropic()
    feedback, last_ok = "", None
    for _ in range(3):
        resp = client.messages.create(model=cfg["llm"]["model"], max_tokens=4000, system=SYSTEM, tools=[TOOL],
                                      tool_choice={"type": "auto"}, messages=[{"role": "user", "content": ask + feedback}])
        block = next((b for b in resp.content if b.type == "tool_use"), None)
        if block is None:
            feedback = "\nAnswer by calling submit_storyboard."
            continue
        s = block.input
        try:
            if isinstance(s.get("scenes"), str):
                s["scenes"] = _loads(s["scenes"])
            for sc in s["scenes"]:
                for k in ("data", "term"):
                    if isinstance(sc.get(k), str):
                        sc[k] = _loads(sc[k])
            words = sum(len(sc["say"].split()) for sc in s["scenes"])
            s["brief"] = brief
            if 5 <= len(s["scenes"]) <= 14:
                last_ok = s
            if 5 <= len(s["scenes"]) <= 14 and seconds * 1.3 <= words <= seconds * 2.5:
                return s
            feedback = f"\nFix: {len(s['scenes'])} scenes and {words} words; use 8-12 scenes and about {int(seconds * 2.1)} words."
        except Exception:
            feedback = "\nFix: scenes must be a list of objects with say, type and data objects."
    if last_ok:  # right shape but a different length than asked: better than failing; the editor shows the word count
        return last_ok
    raise RuntimeError("Claude returned a storyboard in an unexpected shape. Try again.")


# ---------------------------------------------------------------- drawing helpers
def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def back(x):  # overshoot
    x = max(0.0, min(1.0, x))
    c = 1.70158
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def mix(a, b, t):
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


class Mage(Worlds):
    def __init__(self, cfg: dict, script: dict, timing: dict):
        self.cfg, self.script, self.timing = cfg, script, timing
        theme = script.get("theme") if script.get("theme") in THEMES else "generic"
        self.theme = theme
        self.bg_top, self.bg_bot, self.acc = THEMES[theme]
        self.scenes = script["scenes"]
        self.handle = cfg.get("channel", {}).get("handle", "@channel")
        self.series = (script.get("series") or script["title"]).upper()[:34]
        self.font_path = _find_font(cfg)
        self._f, self._m = {}, {}
        self._warned = set()
        self.bg = self._background()
        self.mono_path = next((p for p in ["/System/Library/Fonts/Menlo.ttc", "C:/Windows/Fonts/consolab.ttf", "C:/Windows/Fonts/consola.ttf",
                                           "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"] if Path(p).exists()), None)

    # fonts
    def font(self, n):
        if n not in self._f:
            self._f[n] = ImageFont.truetype(self.font_path, n) if self.font_path else ImageFont.load_default(size=n)
        return self._f[n]

    def mono(self, n):
        if n not in self._m:
            self._m[n] = ImageFont.truetype(self.mono_path, n) if self.mono_path else self.font(n)
        return self._m[n]

    def _background(self):
        BG_TOP, BG_BOT = self.bg_top, self.bg_bot
        col = Image.new("RGB", (1, H))
        for y in range(H):
            col.putpixel((0, y), mix(BG_TOP, BG_BOT, y / H))
        img = col.resize((W, H)).convert("RGBA")
        g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(g)
        for x in range(0, W, 54):
            d.line((x, 0, x, H), fill=(80, 120, 210, 22))
        for y in range(0, H, 54):
            d.line((0, y, W, y), fill=(80, 120, 210, 22))
        img.alpha_composite(g)
        vig = Image.new("L", (W, H), 0)
        ImageDraw.Draw(vig).ellipse((-W * 0.2, H * 0.1, W * 1.2, H * 0.9), fill=255)
        vig = vig.filter(ImageFilter.GaussianBlur(220))
        dark = Image.new("RGBA", (W, H), (2, 6, 20, 150))
        dark.putalpha(Image.eval(vig, lambda v: 150 - int(v * 150 / 255)))
        img.alpha_composite(dark)
        return img.convert("RGB")

    # timing helpers: when each item should appear, from the spoken words
    def reveal_times(self, si, items, lo=0.12, hi=0.72):
        sc = self.timing["scenes"][si]
        dur = sc["end"] - sc["start"]
        words = [(re.sub(r"\W", "", w.lower()), a - sc["start"]) for w, a, _ in sc["words"]]
        out, pos = [], 0
        for i, it in enumerate(items):
            keys = {re.sub(r"\W", "", w.lower()) for w in str(it).split() if len(re.sub(r"\W", "", w)) > 3}
            hit = next((j for j in range(pos, len(words)) if words[j][0] in keys), None)
            if hit is not None:
                out.append(max(0.15, words[hit][1] - 0.1))
                pos = hit + 1
            else:
                out.append(dur * (lo + (hi - lo) * i / max(1, len(items))))
        for i in range(1, len(out)):
            out[i] = max(out[i], out[i - 1] + 0.35)
        return out

    # ---------------------------------------------------------------- shared chrome
    def _logo(self):
        if not hasattr(self, "_logo_img"):
            self._logo_img = None
            try:
                from .config import resolve
                pth = resolve(self.cfg, self.cfg["channel"]["logo"])
                if pth.exists():
                    im = Image.open(pth).convert("RGBA").resize((92, 92), Image.LANCZOS)
                    m = Image.new("L", (92, 92), 0)
                    ImageDraw.Draw(m).ellipse((0, 0, 91, 91), fill=255)
                    im.putalpha(m)
                    self._logo_img = im
            except Exception:
                pass
        return self._logo_img

    def chrome(self, d, label, img=None, t=0.0):
        d.text((54, 52), f"SYSTEM DESIGN · {self.series}", font=self.mono(22), fill=MUTED, anchor="lm")
        d.text((W - 54, 52), self.handle, font=self.mono(22), fill=(110, 128, 170), anchor="rm")
        d.line((54, 84, W - 54, 84), fill=(60, 90, 160), width=1)
        if label:
            d.text((54, 118), "— " + label.upper(), font=self.mono(26), fill=self.acc, anchor="lm")
        d.text((W // 2, 1858), "Follow", font=self.font(30), fill=(220, 228, 245), anchor="mm")
        lg = self._logo() if img is not None else None
        if lg is not None:  # the channel mark hangs in the top-right corner and sways a little, like a mascot
            sw = 5 * math.sin(t * 1.6)
            d.line((W - 78, 88, W - 78 + sw, 138), fill=(90, 110, 160), width=3)
            img.paste(lg, (int(W - 78 - 46 + sw), 136), lg)

    def chip(self, d, text, cx, cy, tone=CYAN, size=26, a=1.0):
        if a <= 0:
            return
        f = self.mono(size)
        tw = d.textlength(text.upper(), font=f)
        s = 0.9 + 0.1 * back(a)
        w, h = (tw + 40) * s, (size + 26) * s
        d.rounded_rectangle((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), radius=8, fill=BOX, outline=tone, width=2)
        d.text((cx, cy), text.upper(), font=f, fill=tone, anchor="mm")

    def term_card(self, d, term, cx, cy, a):
        if a <= 0 or not term:
            return
        w, h = 700, 190
        off = int((1 - ease(a)) * 60)
        d.rounded_rectangle((cx - w / 2, cy - h / 2 + off, cx + w / 2, cy + h / 2 + off), radius=22, fill=(12, 22, 54), outline=self.acc, width=3)
        d.text((cx, cy - 62 + off), term.get("kicker", "THIS IS CALLED"), font=self.mono(20), fill=MUTED, anchor="mm")
        d.text((cx, cy - 8 + off), term.get("name", ""), font=self.font(58), fill=self.acc, anchor="mm")
        d.text((cx, cy + 54 + off), term.get("sub", ""), font=self.mono(24), fill=INK, anchor="mm")

    # ---------------------------------------------------------------- scene drawers
    def d_title(self, d, img, t, dur, data, si):
        a = ease(t / 0.5)
        self.theme_art(d, t, self.theme)
        title = data.get("title", self.script["title"])
        size = 150 if len(title) < 10 else 110 if len(title) < 16 else 80
        d.text((W // 2, 640 - int((1 - a) * 40)), title, font=self.font(size), fill=INK, anchor="mm")
        tag = data.get("tag", "SYSTEM DESIGN INTERVIEW")
        self.chip(d, tag, W // 2, 760, CYAN, 24, ease((t - 0.3) / 0.4))
        q = data.get("question", "")
        qt = dur * 0.42
        p = back((t - qt) / 0.5)
        if q and p > 0:
            lines = self._wrap(q, self.font(54), 820)
            h = len(lines) * 72 + 70
            s = 0.92 + 0.08 * p
            x0, x1, y0 = W / 2 - 450 * s, W / 2 + 450 * s, 1010
            d.rounded_rectangle((x0, y0, x1, y0 + h * s), radius=26, fill=(10, 20, 52), outline=self.acc, width=4)
            for i, ln in enumerate(lines):
                col = self.acc if i == len(lines) - 2 and len(lines) > 1 else INK
                d.text((W // 2, y0 + 55 + i * 72), ln, font=self.font(54), fill=col, anchor="mm")

    def _wrap(self, text, f, mw):
        d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        lines, cur = [], ""
        for w in text.split():
            tt = f"{cur} {w}".strip()
            if d.textlength(tt, font=f) <= mw or not cur:
                cur = tt
            else:
                lines.append(cur)
                cur = w
        return lines + ([cur] if cur else [])

    def d_steps(self, d, img, t, dur, data, si):
        items = [str(x) for x in data.get("items", [])][:5]
        bad = data.get("tone") == "bad"
        col = RED if bad else self.acc
        rt = self.reveal_times(si, items)
        y0 = 520
        for i, it in enumerate(items):
            p = back((t - rt[i]) / 0.45)
            if p <= 0:
                continue
            cur = i == max([j for j, r in enumerate(rt) if t >= r], default=-1)
            y = y0 + i * 150
            x = 70 - int((1 - ease(p)) * 160)
            d.rounded_rectangle((x, y, x + W - 140, y + 112), radius=22, fill=BOX, outline=col if cur else (50, 80, 150), width=4 if cur else 2)
            d.text((x + 44, y + 56), str(i + 1), font=self.font(54), fill=col if cur else MUTED, anchor="mm")
            size = 46
            while self.font(size).getlength(it) > W - 300 and size > 28:
                size -= 3
            d.text((x + 100, y + 56), it, font=self.font(size), fill=INK if cur else (170, 184, 220), anchor="lm")

    def d_flow(self, d, img, t, dur, data, si):
        nodes = data.get("nodes") or [{"label": "Client"}, {"label": "Server"}]
        nodes = [n if isinstance(n, dict) else {"label": str(n)} for n in nodes][:4]
        n = len(nodes)
        spike = bool(data.get("spike"))
        cw = 250 if n <= 3 else 210
        gap = (W - 2 * 70 - n * cw) / max(1, n - 1) if n > 1 else 0
        cy = 880
        xs = [70 + i * (cw + gap) for i in range(n)]
        for i in range(n - 1):  # edges first
            a = ease((t - 0.2 - i * 0.25) / 0.4)
            x0, x1 = xs[i] + cw, xs[i + 1]
            d.line((x0, cy, x0 + (x1 - x0) * a, cy), fill=LINE, width=4)
            if a >= 1:
                cnt = 14 if spike and i == n - 2 else 4
                rnd = random.Random(i + 7)
                for k in range(cnt):
                    ph = (t * (0.9 if not spike else 1.4) + k / cnt + rnd.random() * 0.05) % 1
                    px = x0 + (x1 - x0) * ph
                    off = (rnd.random() - 0.5) * (70 if spike and i == n - 2 else 0)
                    d.rounded_rectangle((px - 18, cy + off - 9, px + 18, cy + off + 9), radius=4, fill=AMBER)
        for i, nd in enumerate(nodes):
            p = back((t - 0.05 - i * 0.25) / 0.45)
            if p <= 0:
                continue
            s = 0.85 + 0.15 * p
            red = spike and i == n - 1 and t > 1.0
            col = RED if red else (GREEN if i == 0 else CYAN)
            hh = 230 * s
            d.rounded_rectangle((xs[i] + cw / 2 - cw * s / 2, cy - hh / 2, xs[i] + cw / 2 + cw * s / 2, cy + hh / 2), radius=22, fill=BOX, outline=col, width=4)
            d.text((xs[i] + cw / 2, cy - 22), nd.get("label", ""), font=self.font(40), fill=INK, anchor="mm")
            if nd.get("sub"):
                d.text((xs[i] + cw / 2, cy + 38), nd["sub"], font=self.mono(20), fill=MUTED, anchor="mm")
        if data.get("note"):
            self.chip(d, data["note"], W // 2, 1110, RED if spike else CYAN, 26, ease((t - 0.8) / 0.4))
        if spike and t > 1.0:
            self.chip(d, "OVERLOAD", xs[-1] + cw / 2, cy - 160, RED, 24, ease((t - 1.0) / 0.3))

    def d_grid(self, d, img, t, dur, data, si):
        rows, cols = max(3, min(10, int(data.get("rows", 8)))), max(3, min(8, int(data.get("cols", 6))))
        mode = data.get("mode", "cells")
        cell = min((W - 160) // cols, 1000 // rows)
        gw, gh = cell * cols, cell * rows
        x0, y0 = (W - gw) // 2, 330
        a = ease(t / 0.5)
        rnd = random.Random(5)
        vals = [[rnd.choice([0, 0, 0, 1, 1, 2, 3]) for _ in range(cols)] for _ in range(rows)]
        hl = data.get("highlight")
        for r in range(rows):
            for c in range(cols):
                x, y = x0 + c * cell, y0 + r * cell
                if mode == "heat":
                    v = (math.sin(t * 1.3 + r * 0.7 + c * 0.9) + math.sin(r * 1.1 - c * 0.6) + 2) / 4
                    v = min(1, max(0, v * (0.5 + 0.5 * ease((t - (r + c) * 0.05) / 0.6))))
                    colr = mix((70, 160, 140), (230, 120, 110), max(0, (v - 0.55) * 2.2)) if v > 0.55 else mix((70, 160, 140), (215, 170, 90), max(0, (v - 0.3) * 3))
                    d.rectangle((x + 2, y + 2, x + cell - 2, y + cell - 2), fill=colr)
                elif mode == "counter":
                    d.rectangle((x, y, x + cell, y + cell), outline=(60, 95, 170), width=1)
                    if ease((t - 0.15 - (r * cols + c) * 0.012) / 0.3) > 0.5:
                        d.text((x + cell / 2, y + cell / 2), str(vals[r][c]), font=self.mono(int(cell * 0.45)), fill=INK if vals[r][c] else (90, 112, 170), anchor="mm")
                else:
                    d.rectangle((x, y, x + cell, y + cell), outline=(60, 95, 170), width=1)
        if mode == "cells":  # drifting dots (vehicles)
            rr = random.Random(11)
            for k in range(26):
                bx, by, sp = rr.random(), rr.random(), 0.3 + rr.random() * 0.5
                px = x0 + ((bx + t * sp * 0.04 * (1 if k % 2 else -1)) % 1) * gw
                py = y0 + ((by + t * sp * 0.03) % 1) * gh
                d.rounded_rectangle((px - 9, py - 14, px + 9, py + 14), radius=4, fill=AMBER if k % 3 else CYAN)
        if hl and isinstance(hl, (list, tuple)) and len(hl) == 2:
            r, c = int(hl[0]) % rows, int(hl[1]) % cols
            pulse = 0.5 + 0.5 * math.sin(t * 6)
            d.rectangle((x0 + c * cell, y0 + r * cell, x0 + (c + 1) * cell, y0 + (r + 1) * cell), outline=mix(RED, self.acc, pulse), width=5)
        if data.get("note"):
            self.chip(d, data["note"], W // 2, y0 + gh + 70, self.acc, 26, ease((t - 0.6) / 0.4))

    def _hex(self, d, cx, cy, r, fill=None, outline=(70, 110, 190), width=2):
        pts = [(cx + r * math.cos(math.radians(60 * k)), cy + r * math.sin(math.radians(60 * k))) for k in range(6)]
        d.polygon(pts, fill=fill, outline=outline, width=width)

    def d_hex(self, d, img, t, dur, data, si):
        mode = data.get("mode", "ring")
        if mode == "compare":  # squares: 4 near / 4 far; hexagons: 6 equal neighbours
            a = ease(t / 0.5)
            x0, y0, cs = 90, 640, 120
            d.text((x0 + 180, y0 - 60), "SQUARES", font=self.mono(22), fill=MUTED, anchor="mm")
            for r in range(3):
                for c in range(3):
                    d.rectangle((x0 + c * cs, y0 + r * cs, x0 + (c + 1) * cs, y0 + (r + 1) * cs), outline=LINE, width=2,
                                fill=(70, 70, 40) if (r, c) == (1, 1) else None)
            hx, hy, hr = 720, 800, 66
            d.text((hx, y0 - 60), "HEXAGONS", font=self.mono(22), fill=MUTED, anchor="mm")
            for q in range(-1, 2):
                for r in range(-1, 2):
                    if abs(q + r) > 1:
                        continue
                    px, py = hx + hr * 1.5 * q, hy + hr * math.sqrt(3) * (r + q / 2)
                    self._hex(d, px, py, hr - 3, fill=(70, 70, 40) if (q, r) == (0, 0) else None)
            p = ease((t - 0.8) / 0.8)
            if p > 0:
                for k in range(8):
                    ang = k * math.pi / 4
                    ln = 180 * p
                    far = k % 2 == 1
                    d.line((x0 + 1.5 * cs, y0 + 1.5 * cs, x0 + 1.5 * cs + math.cos(ang) * ln * (1.35 if far else 1), y0 + 1.5 * cs + math.sin(ang) * ln * (1.35 if far else 1)), fill=RED if far else self.acc, width=3)
                for k in range(6):
                    ang = k * math.pi / 3 + math.pi / 6
                    d.line((hx, hy, hx + math.cos(ang) * 150 * p, hy + math.sin(ang) * 150 * p), fill=GREEN, width=3)
            if p > 0.9:
                self.chip(d, "SQUARE: 4 PAAS, 4 DOOR", x0 + 170, y0 + 430, RED, 20)
                self.chip(d, "HEX: 6 PADOSI, SAB BARABAR", 730, y0 + 430, GREEN, 20)
        else:  # ring: hex field, the centre cell, then its neighbours light up
            hr = 52
            for q in range(-6, 7):
                for r in range(-8, 9):
                    px, py = W / 2 + hr * 1.5 * q, 880 + hr * math.sqrt(3) * (r + q / 2)
                    if not (60 < px < W - 60 and 280 < py < 1500):
                        continue
                    dist = max(abs(q), abs(r), abs(q + r))
                    lit = (dist == 0 and t > 0.3) or (dist == 1 and t > 1.2) or (dist == 2 and t > 2.2 and data.get("rings", 1) > 1)
                    self._hex(d, px, py, hr - 3, fill=(70, 70, 30) if dist == 0 and lit else (30, 80, 140) if lit else None,
                              outline=self.acc if dist == 0 and lit else (70, 110, 190), width=3 if lit else 1)
            if t > 0.3:
                d.text((W / 2, 880 + 66), "TUM", font=self.mono(22), fill=self.acc, anchor="mm")
        if data.get("note"):
            self.chip(d, data["note"], W // 2, 1330 if mode == "compare" else 1570, CYAN, 26, ease((t - 1.0) / 0.4))

    def d_phone(self, d, img, t, dur, data, si):
        a = back(t / 0.5)
        cx, top, w, h = W // 2, 380, 440, 880
        s = 0.9 + 0.1 * a
        x0, y0 = cx - w * s / 2, top
        d.rounded_rectangle((x0, y0, x0 + w * s, y0 + h * s), radius=56, fill=(8, 12, 28), outline=(200, 210, 235), width=5)
        d.text((cx, y0 + 80), data.get("title", "Choose a ride"), font=self.font(34), fill=INK, anchor="mm")
        rows = data.get("rows", [{"label": "Go", "value": "₹180"}, {"label": "Sedan", "value": "₹244"}])[:4]
        flash = bool(data.get("flash"))
        for i, r in enumerate(rows):
            y = y0 + 150 + i * 130
            hot = flash and i == 0
            col = mix(GREEN, RED, min(1, max(0, (t - 1.0) / 1.0))) if hot else (90, 120, 190)
            d.rounded_rectangle((x0 + 34, y, x0 + w - 34, y + 104), radius=16, fill=BOX, outline=col, width=3 if hot else 2)
            d.text((x0 + 60, y + 52), str(r.get("label", "")), font=self.font(34), fill=INK, anchor="lm")
            val = str(r.get("value", ""))
            if hot and t > 1.0 and val.startswith("₹"):
                try:
                    base = int(re.sub(r"\D", "", val))
                    val = "₹" + str(int(base * (1 + 0.4 * ease((t - 1.0) / 1.0))))
                except ValueError:
                    pass
            val = val.replace("₹", "Rs ")  # the bold UI font has no rupee sign
            room = w - 120 - d.textlength(str(r.get("label", "")), font=self.font(34)) - 24
            vs = 36
            while vs > 20 and d.textlength(val, font=self.font(vs)) > room:
                vs -= 2
            while len(val) > 3 and d.textlength(val, font=self.font(vs)) > room:
                val = val[:-2] + "…"
            d.text((x0 + w - 60, y + 52), val, font=self.font(vs), fill=col if hot else INK, anchor="rm")
        btn = data.get("button", "Book")
        d.rounded_rectangle((x0 + 34, y0 + h - 150, x0 + w - 34, y0 + h - 60), radius=18, fill=(235, 240, 255))
        d.text((cx, y0 + h - 105), btn, font=self.font(36), fill=(10, 16, 40), anchor="mm")
        if data.get("note"):
            self.chip(d, data["note"], W // 2, 1410, self.acc, 26, ease((t - 0.8) / 0.4))


    # ---------------------------------------------------------------- richer scenes (devices, function box, clock)
    def _qr(self, d, x, y, size, seed=7, scan=0.0):
        n = 21
        c = size / n
        rnd = random.Random(seed)
        d.rectangle((x - 6, y - 6, x + size + 6, y + size + 6), fill=(255, 255, 255))
        for r in range(n):
            for k in range(n):
                finder = (r < 7 and k < 7) or (r < 7 and k >= n - 7) or (r >= n - 7 and k < 7)
                if finder:
                    rr, kk = (r if r < 7 else r - (n - 7)), (k if k < 7 else k - (n - 7))
                    on = rr in (0, 6) or kk in (0, 6) or (2 <= rr <= 4 and 2 <= kk <= 4)
                else:
                    on = rnd.random() < 0.5
                if on:
                    d.rectangle((x + k * c, y + r * c, x + (k + 1) * c - 1, y + (r + 1) * c - 1), fill=(14, 18, 36))
        if scan > 0:  # a scan line sweeping over the code
            yy = y + size * ((scan * 1.6) % 1)
            d.rectangle((x - 4, yy - 3, x + size + 4, yy + 3), fill=(80, 230, 140, 200))

    def _device(self, d, kind, cx, cy, w, h, spec, t, k):
        title = str(spec.get("title", ""))
        if kind == "phone":
            d.rounded_rectangle((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), radius=40, fill=(10, 14, 30), outline=(210, 220, 240), width=4)
            d.rounded_rectangle((cx - 34, cy - h / 2 + 12, cx + 34, cy - h / 2 + 28), radius=8, fill=(30, 34, 52))
            d.rounded_rectangle((cx - w / 2 + 14, cy - h / 2 + 44, cx + w / 2 - 14, cy + h / 2 - 16), radius=26, fill=(245, 247, 252))
            d.text((cx, cy - h / 2 + 72), title[:22], font=self.font(22), fill=(40, 50, 90), anchor="mm")
            if spec.get("qr"):
                self._qr(d, cx - 60, cy - 50, 120, 5 + k, scan=t * 0.5)
            lines = [str(x) for x in spec.get("lines", [])][:4]
            code = spec.get("code")
            if code:
                d.text((cx, cy), str(code), font=self.font(46), fill=(30, 100, 230), anchor="mm")
            for i, ln in enumerate(lines):
                d.text((cx - w / 2 + 34, cy + 60 + i * 34), ln[:22], font=self.mono(18), fill=(70, 80, 120), anchor="lm")
        elif kind == "server":
            d.rounded_rectangle((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), radius=14, fill=(12, 20, 50), outline=LINE, width=3)
            d.text((cx, cy - h / 2 - 22), (title or "SERVER").upper(), font=self.mono(20), fill=MUTED, anchor="mm")
            for i in range(4):
                y = cy - h / 2 + 24 + i * 30
                d.rounded_rectangle((cx - w / 2 + 16, y, cx + w / 2 - 16, y + 18), radius=6, fill=(26, 40, 86))
                if (int(t * 2) + i) % 4 == 0:
                    d.ellipse((cx + w / 2 - 36, y + 4, cx + w / 2 - 28, y + 12), fill=GREEN)
            lines = [str(x) for x in spec.get("lines", [])][:3]
            for i, ln in enumerate(lines):
                d.text((cx, cy + 10 + i * 32), ln[:20], font=self.mono(20), fill=self.acc, anchor="mm")
            if spec.get("code"):
                d.text((cx, cy + h / 2 - 34), str(spec["code"]), font=self.font(40), fill=self.acc, anchor="mm")
        else:  # laptop
            d.rounded_rectangle((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2 - 20), radius=14, fill=(245, 247, 252), outline=(210, 220, 240), width=4)
            d.polygon([(cx - w / 2 - 24, cy + h / 2), (cx + w / 2 + 24, cy + h / 2), (cx + w / 2 + 6, cy + h / 2 - 22), (cx - w / 2 - 6, cy + h / 2 - 22)], fill=(170, 184, 214))
            d.text((cx - w / 2 + 22, cy - h / 2 + 24), title[:18].upper(), font=self.mono(18), fill=(200, 60, 60), anchor="lm")
            d.text((cx, cy - h / 2 + 62), str(spec.get("sub", "Setup external TOTP" if spec.get("qr") else "Login"))[:26], font=self.font(24), fill=(30, 40, 80), anchor="mm")
            if spec.get("qr"):
                self._qr(d, cx - 62, cy - h / 2 + 90, 124, 3 + k)
            else:
                d.rounded_rectangle((cx - w / 2 + 40, cy - 14, cx + w / 2 - 40, cy + 36), radius=8, fill=(255, 255, 255), outline=(150, 160, 190), width=2)
                if spec.get("code"):
                    d.text((cx, cy + 11), str(spec["code"]), font=self.mono(28), fill=(30, 40, 80), anchor="mm")
                d.rounded_rectangle((cx - 50, cy + 56, cx + 50, cy + 92), radius=8, fill=(40, 110, 230))
                d.text((cx, cy + 74), "Continue", font=self.font(20), fill=(255, 255, 255), anchor="mm")

    def d_devices(self, d, img, t, dur, data, si):
        devs = [x for x in (data.get("devices") or []) if isinstance(x, dict)][:3] or [{"kind": "phone"}]
        n = len(devs)
        sizes = {"laptop": (400, 300), "phone": (250, 460), "server": (290, 260)}
        cy = 860
        slot = (W - 100) / n
        centres = [50 + slot * (i + 0.5) for i in range(n)]
        rt = self.reveal_times(si, [str(x.get("title", "")) for x in devs], 0.05, 0.4)
        dims = []
        for spec in devs:
            w, h = sizes.get(spec.get("kind", "phone"), sizes["phone"])
            sc = min(1.0, (slot - 74) / (w + 48))  # leave room for the base of a laptop and an arrow
            dims.append((w * sc, h * sc))
        for i, spec in enumerate(devs):
            p = back((t - min(rt[i], 0.2 + i * 0.35)) / 0.5)
            if p <= 0:
                continue
            f = 0.9 + 0.1 * min(1, p)
            self._device(d, spec.get("kind", "phone"), centres[i], cy, dims[i][0] * f, dims[i][1] * f, spec, t, i)
        flows = [str(x) for x in (data.get("flows") or [])]
        for i in range(n - 1):
            a = ease((t - 0.8 - i * 0.7) / 0.5)
            if a <= 0:
                continue
            x0 = centres[i] + dims[i][0] / 2 + 34
            x1 = centres[i + 1] - dims[i + 1][0] / 2 - 34
            if x1 - x0 < 30:
                x0, x1 = centres[i] + 30, centres[i + 1] - 30
            d.line((x0, cy, x0 + (x1 - x0) * a, cy), fill=self.acc, width=4)
            if a >= 1:
                ph = (t * 0.7 + i * 0.3) % 1
                px = x0 + (x1 - x0) * ph
                d.rounded_rectangle((px - 22, cy - 15, px + 22, cy + 15), radius=6, fill=AMBER)
                d.text((px, cy), "KEY", font=self.mono(14), fill=(30, 20, 0), anchor="mm")
                if i < len(flows):
                    self.chip(d, flows[i], (x0 + x1) / 2, cy - 330 + i * 0, self.acc, 20, ease((t - 1.5 - i * 0.7) / 0.4))
        if data.get("note"):
            self.chip(d, str(data["note"]), W // 2, cy + 330, CYAN, 24, ease((t - 1.2) / 0.4))

    def d_pipeline(self, d, img, t, dur, data, si):
        ins = [x if isinstance(x, dict) else {"label": str(x)} for x in (data.get("inputs") or [])][:3] or [{"label": "INPUT"}]
        fn = str(data.get("fn", "HASH"))
        n = len(ins)
        top, fy = 500, 780
        xs = [W / 2 + (i - (n - 1) / 2) * 340 for i in range(n)]
        for i, it in enumerate(ins):
            p = back((t - 0.1 - i * 0.3) / 0.45)
            if p <= 0:
                continue
            s = 0.9 + 0.1 * min(1, p)
            d.rounded_rectangle((xs[i] - 150 * s, top - 40 * s, xs[i] + 150 * s, top + 40 * s), radius=14, fill=BOX, outline=self.acc if i == 0 else CYAN, width=3)
            d.text((xs[i], top), str(it.get("label", ""))[:20], font=self.mono(22), fill=INK, anchor="mm")
            a = ease((t - 0.5 - i * 0.3) / 0.5)
            if a > 0:
                d.line((xs[i], top + 42, xs[i] + (W / 2 - xs[i]) * a, top + 42 + (fy - 48 - top - 42) * a), fill=(120, 150, 230), width=3)
        pf = back((t - 1.0) / 0.5)
        if pf > 0:
            s = 0.9 + 0.1 * min(1, pf)
            d.rounded_rectangle((W / 2 - 130 * s, fy - 52 * s, W / 2 + 130 * s, fy + 52 * s), radius=16, fill=(30, 26, 8), outline=self.acc, width=4)
            d.text((W / 2, fy - 4), fn, font=self.font(52), fill=self.acc, anchor="mm")
            d.text((W / 2, fy + 34), str(data.get("sub", "")).upper(), font=self.mono(16), fill=MUTED, anchor="mm")
        out = str(data.get("output", ""))
        if out and t > 1.6:
            oy = 1000
            d.rounded_rectangle((70, oy - 76, W - 70, oy + 76), radius=14, fill=BOX, outline=(70, 110, 190), width=2)
            settle = ease((t - 1.8) / 1.2)
            rnd = random.Random(int(t * 12))
            half = (len(out) + 1) // 2
            for r, chunk in enumerate((out[:half], out[half:])):
                shown = "".join(c if i < settle * len(chunk) else rnd.choice("0123456789abcdef") for i, c in enumerate(chunk))
                d.text((W / 2, oy - 26 + r * 52), shown, font=self.mono(36 if len(chunk) <= 24 else 28), fill=INK, anchor="mm")
            if data.get("bracket") and settle > 0.95:
                d.line((90, oy + 100, 90, oy + 112, W - 90, oy + 112, W - 90, oy + 100), fill=self.acc, width=3)
                self.chip(d, str(data["bracket"]), W // 2, oy + 160, self.acc, 22, ease((t - 3.0) / 0.4))
        if data.get("note"):
            self.chip(d, str(data["note"]), W // 2, 1300, RED, 22, ease((t - 2.6) / 0.4))

    def d_timer(self, d, img, t, dur, data, si):
        cx, cy, r = W // 2, 470, 70
        a = ease(t / 0.5)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=CYAN, width=6)
        ang = t * 3.2
        d.line((cx, cy, cx + 48 * math.sin(ang), cy - 48 * math.cos(ang)), fill=CYAN, width=6)
        d.line((cx, cy, cx + 30 * math.sin(ang / 12), cy - 30 * math.cos(ang / 12)), fill=INK, width=6)
        d.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), fill=CYAN)
        d.text((cx, cy + 118), str(data.get("label", "")), font=self.mono(26), fill=INK, anchor="mm")
        # timeline
        if t > 0.8:
            d.line((90, 640, W - 90, 640), fill=(60, 90, 160), width=4)
            d.line((90, 640, 90 + (W - 180) * ease((t - 0.8) / 1.2), 640), fill=CYAN, width=5)
            d.text((90, 676), str(data.get("start_label", "START")), font=self.mono(18), fill=MUTED, anchor="lm")
            d.text((W - 90, 676), str(data.get("end_label", "ABHI")), font=self.mono(18), fill=MUTED, anchor="rm")
        total = float(data.get("total", 0) or 0)
        if total and t > 1.0:
            v = total * ease((t - 1.0) / 1.4)
            d.text((W // 2, 760), f"{v:,.0f} {data.get('unit', 'sec')}", font=self.font(60), fill=INK, anchor="mm")
        if data.get("caption") and t > 2.4:
            self.chip(d, str(data["caption"]), W // 2, 840, self.acc, 20, ease((t - 2.4) / 0.4))
        div = float(data.get("divide", 0) or 0)
        if total and div and t > 3.0:
            d.text((W // 2, 930), f"÷ {div:,.0f}", font=self.font(46), fill=MUTED, anchor="mm")
            res = int(total // div)
            p = ease((t - 3.3) / 0.8)
            shown = int(res * p) if p < 1 else res
            d.rounded_rectangle((W / 2 - 280, 990, W / 2 + 280, 1100), radius=16, fill=(28, 24, 6), outline=self.acc, width=4)
            d.text((W // 2, 1045), f"{shown:,}".replace(",", ""), font=self.font(64), fill=self.acc, anchor="mm")
            blocks = 30
            for b in range(blocks):
                on = b < int(blocks * (0.5 + 0.5 * math.sin(t * 2)))
                d.rectangle((W / 2 - 280 + b * 18.6, 1130, W / 2 - 280 + b * 18.6 + 14, 1146), fill=CYAN if on else (30, 50, 100))

    def d_counter(self, d, img, t, dur, data, si):
        a, b = float(data.get("from", 0)), float(data.get("to", 100))
        v = a + (b - a) * ease(t / (dur * 0.6))
        shown = f"{v:,.0f}" if abs(b) >= 10 else f"{v:.1f}"
        pulse = 1 + 0.04 * math.sin(t * 7)
        d.text((W // 2, 640), data.get("label", "COUNT").upper(), font=self.mono(34), fill=MUTED, anchor="mm")
        d.text((W // 2, 800), shown + ("%" if str(data.get("caption", "")).startswith("%") else ""), font=self.font(int(250 * pulse)),
               fill=GREEN if b >= a else RED, anchor="mm")
        cap = str(data.get("caption", "")).lstrip("% ").strip()
        if cap:
            self.chip(d, cap, W // 2, 1000, CYAN, 26, ease((t - 0.5) / 0.4))
        w = 700
        d.rounded_rectangle((W / 2 - w / 2, 1100, W / 2 + w / 2, 1130), radius=15, outline=LINE, width=2)
        frac = (v - a) / (b - a) if b != a else 1
        if frac > 0.02:
            d.rounded_rectangle((W / 2 - w / 2 + 4, 1104, W / 2 - w / 2 + 4 + (w - 8) * frac, 1126), radius=12, fill=GREEN)

    def d_cta(self, d, img, t, dur, data, si):
        h = self.handle  # always the channel's own handle, never one the model made up
        a = back(t / 0.5)
        d.text((W // 2, 760 - int((1 - ease(t / 0.5)) * 40)), "Engineering aisi hi hoti hai", font=self.font(54), fill=INK, anchor="mm")
        s = 0.9 + 0.1 * a
        d.rounded_rectangle((W / 2 - 420 * s, 900, W / 2 + 420 * s, 1010), radius=22, fill=BOX, outline=self.acc, width=3)
        d.text((W // 2, 955), f"FOLLOW {h}", font=self.mono(40), fill=self.acc, anchor="mm")
        p = back((t - 0.5) / 0.5)
        if p > 0:
            d.rounded_rectangle((W / 2 - 300 * (0.9 + 0.1 * p), 1070, W / 2 + 300 * (0.9 + 0.1 * p), 1160), radius=22, fill=BOX, outline=CYAN, width=3)
            d.text((W // 2, 1115), "Dost ko bhejo  >", font=self.font(40), fill=INK, anchor="mm")

    # ---------------------------------------------------------------- frames
    def scene_at(self, t):
        return next((i for i, s in enumerate(self.timing["scenes"]) if t < s["end"]), len(self.scenes) - 1)

    def _scene_frame(self, si, t):
        ts = self.timing["scenes"][si]
        local, dur = t - ts["start"], ts["end"] - ts["start"]
        sc = self.scenes[si]
        img = self.bg.copy()
        d = ImageDraw.Draw(img, "RGBA")
        self.chrome(d, sc.get("label", ""), img, local)
        fn = getattr(self, "d_" + sc.get("type", "steps"), self.d_steps)
        try:
            fn(d, img, local, dur, sc.get("data") or {}, si)
        except Exception as e:  # odd data from the storyboard must never kill the render
            if si not in self._warned:
                self._warned.add(si)
                print(f"  scene {si + 1} ({sc.get('type')}) drawn without its diagram: {e}")
        chips = [str(c) for c in (sc.get("chips") or [])][:3]
        if chips:
            rt = self.reveal_times(si, chips, 0.15, 0.6)
            shown = [i for i, r in enumerate(rt) if local >= r]
            if shown:
                i = shown[-1]
                self.chip(d, chips[i], W // 2, 1640, CYAN, 26, ease((local - rt[i]) / 0.3))
        term = sc.get("term")
        if term:
            start = dur * 0.55
            self.term_card(d, term, W // 2, 1500, (local - start) / 0.45)
        return img

    def frame(self, n):
        t = n / FPS
        si = self.scene_at(t)
        img = self._scene_frame(si, t)
        local = t - self.timing["scenes"][si]["start"]
        if si > 0 and local < 0.18:  # short cross-fade from the previous scene
            prev = self._scene_frame(si - 1, min(t, self.timing["scenes"][si - 1]["end"] - 0.01))
            img = Image.blend(prev, img, ease(local / 0.18))
        return img


def make(cfg: dict, script: dict, music_choice: str = "auto", language: str = "hinglish"):
    """Voice, draw and mux the reel. Returns (folder, script, video_path)."""
    scenes = [s for s in script["scenes"] if s.get("say", "").strip()]
    if len(scenes) < 3:
        raise RuntimeError("The storyboard needs at least three scenes")
    script["scenes"] = scenes
    folder = ROOT / "output" / f"{date.today()}_{slug(script['title'])}"
    folder.mkdir(parents=True, exist_ok=True)
    print(f"\n▶ Mage reel: {script['title']}")
    voice_script = {"format": "mage", "language": "hinglish" if language == "hinglish" else "en",
                    "scenes": [{"narration": s["say"], "layout": "mage"} for s in scenes]}
    timing = tts.synthesize(voice_script, cfg, folder)
    voice, total = timing["audio"], timing["total"]
    full = {
        "format": "mage", "style": script.get("style", "diagram"), "title": script["title"][:90], "description": script.get("description", ""), "tags": script.get("tags", []),
        "music": music_choice, "series": script.get("series", ""), "storyboard": scenes,
        "channel_id": cfg["channel"].get("id", "main"),
        "source": {"name": "Original", "title": script["title"], "url": ""},
        "scenes": [{"narration": s["say"], "layout": "mage", "headline": s.get("label", ""), "visual": {"type": "none"}} for s in scenes],
    }
    (folder / "script.json").write_text(json.dumps(full, indent=2, ensure_ascii=False))
    if seo.ensure(cfg, full):
        print(f"  seo: {full['seo']['title']}")
        (folder / "script.json").write_text(json.dumps(full, indent=2, ensure_ascii=False))
    track = music.pick(cfg, "studio", music_choice)
    print(f"  music: {track.name if track else 'none'}")

    mg = (News if script.get("style") == "news" else Mage)(cfg, script, timing)
    out = folder / "video.mp4"
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(voice)]
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
    try:
        for n in range(int(total * FPS)):
            enc.stdin.write(mg.frame(n).tobytes())
    finally:
        enc.stdin.close()
        enc.wait()
    if enc.returncode:
        raise RuntimeError("ffmpeg failed")
    print(f"  rendered {out.name} ({total:.0f}s)")
    return folder, full, out


# =============================================================================== AI news style
# Studied from a reference AI-news Short: a hook headline with one red word, then full-frame cards that alternate between dark and
# paper (a spec list with the key line highlighted in a black box, bar charts with one highlighted bar and a hand-drawn arrow,
# price/score face-offs), and one-word-at-a-time italic serif captions along the bottom. Facts come only from the notes the
# owner pastes in; nothing here invents a number.
NEWS_TYPES = ["hook", "points", "bars", "vs", "stat", "cta"]
PAPER, PAPER_INK = (238, 234, 226), (24, 24, 28)
DARK, DARK_INK = (12, 12, 16), (240, 240, 244)
PURPLE, BLUEBAR = (126, 80, 230), (30, 120, 250)

NEWS_SYSTEM = """You write storyboards for a 45-60 second vertical AI-news Short. A voice narrates over full-frame cards, with one-word-at-a-time
captions. Use ONLY the facts in the NOTES the owner gives you: do not add numbers, names, rankings or claims that are not in them.
If a detail is not in the notes, leave it out. Never quote a real person unless the notes contain the quote.

Structure: scene 1 is a "hook": the most surprising true claim from the notes in 6-12 words. Then 6-9 scenes that unpack it
(what it is, the key numbers, how it compares, why it matters), and the last scene is a "cta". Narration is punchy, spoken, 12-22 words
per scene. Each scene has `type` and `data`:
- hook: {headline, hot}          headline text (<= 12 words); hot = the one word or phrase shown in red
- points: {title, items:[2-5 short lines], mark}   a spec list; `mark` = index of the line to highlight in a black box
- bars: {title, unit, bars:[{label, value, hot}] (3-6), note}   horizontal bars; hot:true marks the one that matters most
- vs: {left:{name, value, note}, right:{name, value, note}, unit, better:"left"|"right"|"lower"|"higher"}   two cards, numbers compared
- stat: {big, label}             one big number or phrase and what it is
- cta: {text}                    closing line, e.g. "Check the pinned comment for the link."
Optional `tone`: "dark" or "paper" (cards alternate; the model may leave it out). Metadata: title (<=70 chars), description (2 sentences), up to 6 tags."""

NEWS_TOOL = {
    "name": "submit_storyboard", "description": "Submit the storyboard.",
    "input_schema": {"type": "object", "properties": {
        "title": {"type": "string"}, "description": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 6},
        "scenes": {"type": "array", "items": {"type": "object", "properties": {
            "say": {"type": "string"}, "type": {"type": "string", "enum": NEWS_TYPES},
            "tone": {"type": "string", "enum": ["dark", "paper"]}, "data": {"type": "object"}}, "required": ["say", "type", "data"]}},
    }, "required": ["title", "scenes"]},
}

NEWS_MOCK = {
    "title": "Open-source model just beat the paid ones", "tags": ["AI", "news", "opensource"],
    "description": "An open-source model matches paid ones on benchmarks at a fraction of the price. Example numbers only.",
    "scenes": [
        {"say": "An open source model just caught up with the paid giants.", "type": "hook", "tone": "dark",
         "data": {"headline": "Open source just caught the giants", "hot": "caught"}},
        {"say": "It is free to download, and it keeps up on the big coding benchmark.", "type": "points", "tone": "dark",
         "data": {"title": "Model X", "items": ["Open weights", "1M token context", "Free to run yourself", "Strong at coding"], "mark": 2}},
        {"say": "On the coding benchmark it scores higher than the paid model next to it.", "type": "bars", "tone": "paper",
         "data": {"title": "Coding benchmark (example numbers)", "unit": "%", "bars": [{"label": "Model X", "value": 58, "hot": True},
                  {"label": "Paid A", "value": 46}, {"label": "Paid B", "value": 42}, {"label": "Older open", "value": 41}]}},
        {"say": "And the same landing page costs a few dollars, not tens.", "type": "vs", "tone": "dark",
         "data": {"left": {"name": "Model X", "value": 1.47}, "right": {"name": "Paid A", "value": 9.16}, "unit": "$", "better": "lower"}},
        {"say": "Open models are not the cheap alternative anymore. Check the pinned comment for the link.", "type": "cta", "tone": "paper",
         "data": {"text": "Check the pinned comment for the link."}},
    ],
}


def write_news(cfg: dict, topic: str, notes: str, language: str = "en", seconds: int = 55) -> dict:
    if not have_key():
        return json.loads(json.dumps(NEWS_MOCK))
    if not notes.strip():
        raise RuntimeError("paste the facts you want covered (an announcement, thread or article text) into Notes")
    lang = {"hinglish": "Write `say` in Hinglish: Hindi in Roman letters mixed with common English tech terms. No Devanagari.",
            "en": "Write in clear, simple English."}.get(language, "Write in clear, simple English.")
    ask = (f"Topic: {topic or '(infer from the notes)'}\nNOTES (the only allowed facts):\n{notes.strip()[:6000]}\n\n"
           f"Target about {seconds} seconds of speech (about {int(seconds * 2.0)} words). {lang}")
    client = anthropic.Anthropic()
    feedback = ""
    for _ in range(3):
        resp = client.messages.create(model=cfg["llm"]["model"], max_tokens=4000, system=NEWS_SYSTEM, tools=[NEWS_TOOL],
                                      tool_choice={"type": "auto"}, messages=[{"role": "user", "content": ask + feedback}])
        block = next((b for b in resp.content if b.type == "tool_use"), None)
        if block is None:
            feedback = "\nAnswer by calling submit_storyboard."
            continue
        s = block.input
        try:
            if isinstance(s.get("scenes"), str):
                s["scenes"] = _loads(s["scenes"])
            for sc in s["scenes"]:
                if isinstance(sc.get("data"), str):
                    sc["data"] = _loads(sc["data"])
            words = sum(len(sc["say"].split()) for sc in s["scenes"])
            if 5 <= len(s["scenes"]) <= 12 and s["scenes"][0]["type"] == "hook" and seconds * 1.3 <= words <= seconds * 2.3:
                s["style"] = "news"
                return s
            feedback = (f"\nFix: {len(s['scenes'])} scenes and {words} spoken words. Use 6-9 scenes, the first of type hook, and "
                        f"about {int(seconds * 2.0)} words in total: cut the less important facts.")
        except Exception:
            feedback = "\nFix: scenes must be objects with say, type and a data object."
    raise RuntimeError("Claude returned a storyboard in an unexpected shape. Try again.")


class News(Mage):
    def __init__(self, cfg, script, timing):
        super().__init__(cfg, script, timing)
        self.serif_path = next((p for p in ["/System/Library/Fonts/Supplemental/Georgia Italic.ttf", "C:/Windows/Fonts/georgiai.ttf",
                                            "/System/Library/Fonts/Supplemental/Times New Roman Italic.ttf",
                                            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf"] if Path(p).exists()), None)
        self._s = {}
        self.bg_dark = self._flat(DARK, 22)
        self.bg_paper = self._flat(PAPER, 10)

    def serif(self, n):
        if n not in self._s:
            self._s[n] = ImageFont.truetype(self.serif_path, n) if self.serif_path else self.font(n)
        return self._s[n]

    def _flat(self, col, shade):
        yy = np_gradient(col, shade)
        return yy

    def tone(self, si):
        sc = self.scenes[si]
        return sc.get("tone") if sc.get("tone") in ("dark", "paper") else ("dark" if si % 2 == 0 else "paper")

    # ---- scenes
    def d_hook(self, d, img, t, dur, data, si):
        text = str(data.get("headline", self.script["title"]))
        hot = str(data.get("hot", "")).lower()
        f = self.font(104)
        lines = self._wrap(text, f, 900)[:4]
        total = len(lines) * 128
        y = 760 - total // 2
        k = 0
        for ln in lines:
            words = ln.split()
            widths = [d.textlength(w + " ", font=f) for w in words]
            x = (W - sum(widths) + d.textlength(" ", font=f)) / 2
            for w, wd in zip(words, widths):
                p = back((t - 0.12 * k) / 0.35)
                k += 1
                if p > 0:
                    isHot = hot and re.sub(r"\W", "", w.lower()) in re.sub(r"\W", "", hot)
                    off = int((1 - min(1, p)) * 30)
                    if isHot:
                        d.rectangle((x - 8, y + off - 4, x + wd - 12, y + off + 116), fill=(20, 0, 0))
                    d.text((x, y + off), w, font=f, fill=(255, 60, 60) if isHot else DARK_INK)
                x += wd
            y += 128
        d.rounded_rectangle((W / 2 - 70, y + 60, W / 2 + 70, y + 66), radius=3, fill=(255, 60, 60))

    def d_points(self, d, img, t, dur, data, si, ink=None):
        items = [str(x) for x in data.get("items", [])][:5]
        paper = self.tone(si) == "paper"
        ink = PAPER_INK if paper else DARK_INK
        title = str(data.get("title", ""))
        d.text((90, 420), title, font=self.serif(66), fill=ink, anchor="lm")
        d.line((90, 470, W - 90, 470), fill=(120, 120, 130), width=2)
        rt = self.reveal_times(si, items)
        mark = data.get("mark")
        for i, it in enumerate(items):
            p = ease((t - rt[i]) / 0.4)
            if p <= 0:
                continue
            y = 540 + i * 150
            hl = isinstance(mark, int) and i == mark
            if hl:
                w = self.font(50).getlength(it) + 50
                wipe = ease((t - rt[i] - 0.3) / 0.5)
                d.rectangle((90, y - 6, 90 + w * wipe, y + 82), fill=(0, 0, 0) if paper else (250, 250, 250))
            col = (255, 255, 255) if (hl and paper) else (0, 0, 0) if hl else ink
            d.text((110 - int((1 - p) * 40), y + 38), it, font=self.font(50), fill=(*col,), anchor="lm")
            d.ellipse((60, y + 30, 76, y + 46), fill=BLUEBAR)

    def d_bars(self, d, img, t, dur, data, si):
        bars = [b for b in data.get("bars", []) if isinstance(b, dict)][:6] or [{"label": "A", "value": 1}]
        paper = self.tone(si) == "paper"
        ink = PAPER_INK if paper else DARK_INK
        d.text((90, 400), str(data.get("title", "")), font=self.serif(54), fill=ink, anchor="lm")
        mx = max(float(b.get("value", 0)) for b in bars) or 1
        unit = str(data.get("unit", ""))
        rt = self.reveal_times(si, [b.get("label", "") for b in bars], 0.1, 0.5)
        hot_y = None
        for i, b in enumerate(bars):
            y = 520 + i * 140
            p = ease((t - rt[i]) / 0.7)
            hot = bool(b.get("hot"))
            d.text((90, y + 14), str(b.get("label", "")), font=self.mono(26), fill=ink, anchor="lm")
            d.rounded_rectangle((90, y + 44, W - 90, y + 88), radius=22, fill=(214, 210, 202) if paper else (34, 34, 42))
            wv = (W - 180) * float(b.get("value", 0)) / mx * p
            if wv > 8:
                d.rounded_rectangle((90, y + 44, 90 + wv, y + 88), radius=22, fill=BLUEBAR if hot else (120, 126, 140))
            if p > 0.6:
                d.text((W - 90 - (W - 180) * (1 - float(b.get("value", 0)) / mx) - 14, y + 66), f"{b.get('value', 0)}{' ' if unit[:1].isalpha() else ''}{unit}",
                       font=self.mono(26), fill=(255, 255, 255) if hot or not paper else (255, 255, 255), anchor="rm")
            if hot:
                hot_y = y + 66
                d.rounded_rectangle((84, y + 38, W - 84, y + 94), radius=26, outline=ink, width=3) if p > 0.9 else None
        if hot_y and t > rt[min(len(rt) - 1, [i for i, b in enumerate(bars) if b.get("hot")][0])] + 0.8:  # a hand-drawn arrow onto the hot bar
            a = ease((t - rt[[i for i, b in enumerate(bars) if b.get("hot")][0]] - 0.8) / 0.5)
            pts = [(W - 130 + 40 * math.sin(k / 12 * 2.6) * 0 - k * 6, 420 + (hot_y - 420) * (k / 12) ** 1.6) for k in range(13)]
            pts = [(x0, y0) for (x0, y0) in pts][: max(2, int(13 * a))]
            d.line(pts, fill=PURPLE, width=7)
            if a > 0.9:
                ex, ey = pts[-1]
                d.polygon([(ex, ey + 4), (ex - 22, ey - 24), (ex + 22, ey - 24)], fill=PURPLE)
        if data.get("note"):
            self.chip(d, str(data["note"]), W // 2, 1420, CYAN, 24, ease((t - 1.0) / 0.4))

    def d_vs(self, d, img, t, dur, data, si):
        paper = self.tone(si) == "paper"
        ink = PAPER_INK if paper else DARK_INK
        L, R = data.get("left") or {}, data.get("right") or {}
        unit = str(data.get("unit", ""))
        better = data.get("better", "lower")
        lv, rv = float(L.get("value", 0) or 0), float(R.get("value", 0) or 0)
        win = "left" if (better in ("left",) or (better == "lower" and lv <= rv) or (better == "higher" and lv >= rv)) else "right"
        mx = max(lv, rv) or 1
        for i, (side, card, v) in enumerate((("left", L, lv), ("right", R, rv))):
            y = 440 + i * 420
            p = back((t - 0.15 - i * 0.5) / 0.5)
            if p <= 0:
                continue
            good = side == win
            col = GREEN if good else RED
            s = 0.92 + 0.08 * min(1, p)
            d.rounded_rectangle((90, y, W - 90, y + 360 * s), radius=30, fill=(28, 28, 36) if not paper else (255, 255, 255),
                                outline=col if t > 1.4 else (90, 90, 100), width=4)
            d.text((140, y + 66), str(card.get("name", "")), font=self.font(54), fill=ink, anchor="lm")
            shown = v * ease((t - 0.4 - i * 0.5) / 0.8)
            d.text((W - 140, y + 150), f"{unit}{shown:,.2f}" if v < 100 else f"{unit}{shown:,.0f}", font=self.font(120), fill=col, anchor="rm")
            d.rounded_rectangle((140, y + 250, W - 140, y + 286), radius=18, fill=(70, 70, 80) if not paper else (220, 216, 208))
            wv = (W - 280) * v / mx * ease((t - 0.6 - i * 0.5) / 0.8)
            if wv > 6:
                d.rounded_rectangle((140, y + 250, 140 + wv, y + 286), radius=18, fill=col)
            if card.get("note"):
                d.text((140, y + 322), str(card["note"]), font=self.mono(22), fill=MUTED, anchor="lm")

    def d_stat(self, d, img, t, dur, data, si):
        ink = PAPER_INK if self.tone(si) == "paper" else DARK_INK
        big = str(data.get("big", ""))
        s = back(t / 0.5)
        size = int(min(260, 1700 / max(3, len(big))) * (0.8 + 0.2 * s))
        d.text((W // 2, 760), big, font=self.font(max(60, size)), fill=(255, 60, 60) if self.tone(si) == "dark" else BLUEBAR, anchor="mm")
        if data.get("label"):
            for k, ln in enumerate(self._wrap(str(data["label"]), self.serif(62), 860)[:3]):
                d.text((W // 2, 960 + k * 84), ln, font=self.serif(62), fill=ink, anchor="mm")

    def d_cta(self, d, img, t, dur, data, si):
        ink = PAPER_INK if self.tone(si) == "paper" else DARK_INK
        lines = self._wrap(str(data.get("text", "Follow for more")), self.serif(66), 860)[:6]
        for k, ln in enumerate(lines):
            p = ease((t - k * 0.2) / 0.4)
            d.text((W // 2, 700 + k * 92 + int((1 - p) * 30)), ln, font=self.serif(66), fill=ink, anchor="mm")
        p = back((t - 0.6) / 0.5)
        if p > 0:
            d.rounded_rectangle((W / 2 - 330 * (0.9 + 0.1 * p), 1160, W / 2 + 330 * (0.9 + 0.1 * p), 1260), radius=24,
                                fill=(255, 60, 60))
            d.text((W // 2, 1210), "FOLLOW " + self.handle, font=self.mono(34), fill=(255, 255, 255), anchor="mm")

    def captions(self, d, si, t):
        ts = self.timing["scenes"][si]
        ink = PAPER_INK if self.tone(si) == "paper" else DARK_INK
        cur = None
        for w, a, b in ts["words"]:
            if a - 0.02 <= t < b + 0.12:
                cur = w
        if cur:
            word = re.sub(r"[^\w'$%.\-]", "", cur) or cur
            f = self.serif(78)
            d.text((W // 2 + 3, 1560 + 3), word, font=f, fill=(0, 0, 0, 90) if ink == DARK_INK else (255, 255, 255, 140), anchor="mm")
            d.text((W // 2, 1560), word, font=f, fill=ink, anchor="mm")

    def _scene_frame(self, si, t):
        ts = self.timing["scenes"][si]
        local, dur = t - ts["start"], ts["end"] - ts["start"]
        sc = self.scenes[si]
        img = (self.bg_dark if self.tone(si) == "dark" else self.bg_paper).copy()
        d = ImageDraw.Draw(img, "RGBA")
        fn = getattr(self, "d_" + sc.get("type", "points"), self.d_points)
        try:
            fn(d, img, local, dur, sc.get("data") or {}, si)
        except Exception as e:
            if si not in self._warned:
                self._warned.add(si)
                print(f"  scene {si + 1} ({sc.get('type')}) drawn without its card: {e}")
        self.captions(d, si, t)
        return img


def np_gradient(col, shade):
    import numpy as np
    y = np.linspace(0, 1, H)[:, None, None]
    x = np.linspace(-1, 1, W)[None, :, None]
    base = np.array(col, np.float32)[None, None, :] * np.ones((H, W, 1), np.float32)
    base = base - shade * (0.6 * y + 0.4 * x ** 2)
    return Image.fromarray(np.clip(base, 0, 255).astype("uint8"))
