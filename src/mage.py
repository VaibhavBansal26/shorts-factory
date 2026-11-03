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
from .render import _find_font

W, H, FPS = 1080, 1920, 30
BG_TOP, BG_BOT = (8, 15, 38), (16, 30, 70)
INK, MUTED = (236, 242, 255), (140, 158, 200)
YEL, CYAN, GREEN, RED, AMBER = (250, 204, 21), (56, 189, 248), (74, 222, 128), (248, 113, 113), (251, 191, 36)
BOX, LINE = (14, 26, 62), (70, 110, 190)

SCENE_TYPES = ["title", "steps", "flow", "grid", "hex", "phone", "counter", "cta"]

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
- cta: {handle}                              follow card
Optional on any scene: `chips` (1-3 tiny labels, max 5 words each, appear in order while spoken) and `term`
{kicker, name, sub} (a card "THIS IS CALLED / name / sub" shown near the end of the scene when you name a concept).
Pick the diagram that actually shows the idea. Do not repeat the same type three times in a row.
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
    ask = f"Topic: {topic}\nTarget length about {seconds} seconds of speech (about {int(seconds * 2.1)} spoken words in total).\n{lang}"
    client = anthropic.Anthropic()
    feedback = ""
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
                s["scenes"] = json.loads(s["scenes"])
            for sc in s["scenes"]:
                for k in ("data", "term"):
                    if isinstance(sc.get(k), str):
                        sc[k] = json.loads(sc[k])
            words = sum(len(sc["say"].split()) for sc in s["scenes"])
            if 5 <= len(s["scenes"]) <= 14 and seconds * 1.5 <= words <= seconds * 2.6:
                return s
            feedback = f"\nFix: {len(s['scenes'])} scenes and {words} words; use 8-12 scenes and about {int(seconds * 2.1)} words."
        except Exception:
            feedback = "\nFix: scenes must be a list of objects with say, type and data objects."
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


class Mage:
    def __init__(self, cfg: dict, script: dict, timing: dict):
        self.cfg, self.script, self.timing = cfg, script, timing
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
    def chrome(self, d, label):
        d.text((54, 52), f"SYSTEM DESIGN · {self.series}", font=self.mono(22), fill=MUTED, anchor="lm")
        d.text((W - 54, 52), self.handle, font=self.mono(22), fill=(110, 128, 170), anchor="rm")
        d.line((54, 84, W - 54, 84), fill=(60, 90, 160), width=1)
        if label:
            d.text((54, 118), "— " + label.upper(), font=self.mono(26), fill=YEL, anchor="lm")
        d.text((W // 2, 1858), "Follow", font=self.font(30), fill=(220, 228, 245), anchor="mm")

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
        d.rounded_rectangle((cx - w / 2, cy - h / 2 + off, cx + w / 2, cy + h / 2 + off), radius=22, fill=(12, 22, 54), outline=YEL, width=3)
        d.text((cx, cy - 62 + off), term.get("kicker", "THIS IS CALLED"), font=self.mono(20), fill=MUTED, anchor="mm")
        d.text((cx, cy - 8 + off), term.get("name", ""), font=self.font(58), fill=YEL, anchor="mm")
        d.text((cx, cy + 54 + off), term.get("sub", ""), font=self.mono(24), fill=INK, anchor="mm")

    # ---------------------------------------------------------------- scene drawers
    def d_title(self, d, img, t, dur, data, si):
        a = ease(t / 0.5)
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
            d.rounded_rectangle((x0, y0, x1, y0 + h * s), radius=26, fill=(10, 20, 52), outline=YEL, width=4)
            for i, ln in enumerate(lines):
                col = YEL if i == len(lines) - 2 and len(lines) > 1 else INK
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
        col = RED if bad else YEL
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
            d.rectangle((x0 + c * cell, y0 + r * cell, x0 + (c + 1) * cell, y0 + (r + 1) * cell), outline=mix(RED, YEL, pulse), width=5)
        if data.get("note"):
            self.chip(d, data["note"], W // 2, y0 + gh + 70, YEL, 26, ease((t - 0.6) / 0.4))

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
                    d.line((x0 + 1.5 * cs, y0 + 1.5 * cs, x0 + 1.5 * cs + math.cos(ang) * ln * (1.35 if far else 1), y0 + 1.5 * cs + math.sin(ang) * ln * (1.35 if far else 1)), fill=RED if far else YEL, width=3)
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
                              outline=YEL if dist == 0 and lit else (70, 110, 190), width=3 if lit else 1)
            if t > 0.3:
                d.text((W / 2, 880 + 66), "TUM", font=self.mono(22), fill=YEL, anchor="mm")
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
            self.chip(d, data["note"], W // 2, 1410, YEL, 26, ease((t - 0.8) / 0.4))

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
        d.rounded_rectangle((W / 2 - 420 * s, 900, W / 2 + 420 * s, 1010), radius=22, fill=BOX, outline=YEL, width=3)
        d.text((W // 2, 955), f"FOLLOW {h}", font=self.mono(40), fill=YEL, anchor="mm")
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
        self.chrome(d, sc.get("label", ""))
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
        "format": "mage", "title": script["title"][:90], "description": script.get("description", ""), "tags": script.get("tags", []),
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

    mg = Mage(cfg, script, timing)
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
