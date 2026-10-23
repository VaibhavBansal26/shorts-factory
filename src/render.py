"""Render a vertical 1080x1920 video frame-by-frame with Pillow and pipe it to ffmpeg."""
import math
import random
import subprocess
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import themes
from .config import ROOT, resolve
from .formats import FORMATS

WHITE = (245, 247, 250)


def _find_font(cfg):
    for p in cfg["video"]["fonts"]:
        if Path(p).exists():
            return p
    return None


def make_placeholder_logo(path: Path, text: str = "YC"):
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((16, 16, 496, 496), radius=120, fill=(56, 189, 248, 255))
    f = ImageFont.load_default(size=240)
    d.text((256, 256), text, font=f, fill=(10, 14, 28, 255), anchor="mm")
    img.save(path)


class Renderer:
    def __init__(self, cfg: dict, script: dict, timeline: dict, media: dict | None = None):
        self.cfg, self.script, self.tl = cfg, script, timeline
        self.media = media or {}
        self._box_mask = None
        self._img_cache = {}
        v = cfg["video"]
        self.W, self.H, self.fps = v["width"], v["height"], v["fps"]
        self.font_path = _find_font(cfg)
        self.accent = FORMATS[script["format"]]["accent"]
        self.label = FORMATS[script["format"]]["label"]
        self.theme = FORMATS[script["format"]].get("theme", "default")
        self.th = themes.THEMES[self.theme]
        self.font_ko_path = next((p for p in v.get("fonts_ko", []) if Path(p).exists()), None)
        self.vig = themes.vignette(self.W, self.H, self.th["vignette"]) if self.th["vignette"] else None
        self._avatars = {}
        self.chars = script.get("characters", [])
        self.rng = random.Random(script["title"])
        self.bg = self._gradient()
        self.blobs = [
            (self.rng.random(), self.rng.random(), self.rng.uniform(0.15, 0.35), self.rng.uniform(0.3, 0.7))
            for _ in range(4)
        ]
        self.blob_sprite = self._blob_sprite()
        self.logo = self._load_logo()
        self._layers = {}

    # ---------- primitives ----------
    @lru_cache(maxsize=64)
    def font(self, size: int):
        if self.font_path:
            return ImageFont.truetype(self.font_path, size)
        return ImageFont.load_default(size=size)

    def _gradient(self):
        col = Image.new("RGB", (1, self.H))
        for y in range(self.H):
            t = y / self.H
            col.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(*self.th["bg"])))
        return col.resize((self.W, self.H))

    def _blob_sprite(self):
        s = 700
        sp = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        ImageDraw.Draw(sp).ellipse((100, 100, s - 100, s - 100), fill=(*self.accent, 70))
        return sp.filter(ImageFilter.GaussianBlur(90))

    def _load_logo(self):
        p = resolve(self.cfg, self.cfg["channel"]["logo"])
        if not p.exists():
            make_placeholder_logo(p)
        img = Image.open(p).convert("RGBA")
        h = 120
        return img.resize((int(img.width * h / img.height), h), Image.LANCZOS)

    def wrap(self, text, size, max_w):
        f, d = self.font(size), ImageDraw.Draw(Image.new("RGB", (1, 1)))
        lines, cur = [], ""
        for w in text.split():
            test = f"{cur} {w}".strip()
            if d.textlength(test, font=f) <= max_w or not cur:
                cur = test
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def fit(self, text, max_w, max_h, start=120, minimum=56):
        size = start
        while size > minimum:
            lines = self.wrap(text, size, max_w)
            if len(lines) * size * 1.18 <= max_h:
                return size, lines
            size -= 6
        return minimum, self.wrap(text, minimum, max_w)

    # ---------- scene content (cached RGBA layers) ----------
    def _content_layer(self, idx: int, reveal: float = 1.0):
        sc = self.script["scenes"][idx]
        layer = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        cx, top, bottom, mw = self.W // 2, 380, 1050, self.W - 180
        layout = sc["layout"]
        head = sc.get("headline", "")
        if self.theme == "sigma":
            head = head.upper()
        if layout == "dialogue" or idx in self.media:  # media scenes: small headline on top, media box is composited per frame
            size, lines = self.fit(head, mw, 140, start=72, minimum=44)
            y = 330
            for ln in lines:
                d.text((cx, y), ln, font=self.font(size), fill=WHITE, anchor="mt",
                       stroke_width=2, stroke_fill=(0, 0, 0, 160))
                y += int(size * 1.18)
            return layer

        def centered(lines, size, y, fill):
            for ln in lines:
                d.text((cx, y), ln, font=self.font(size), fill=fill, anchor="mt",
                       stroke_width=2, stroke_fill=(0, 0, 0, 160))
                y += int(size * 1.18)
            return y

        if layout == "stat" and sc.get("stat"):
            d.text((cx, 520), sc["stat"], font=self.font(260), fill=(*self.accent, 255), anchor="mm")
            size, lines = self.fit(head, mw, 300, start=84)
            centered(lines, size, 700, WHITE)
        elif layout == "bullets" and sc.get("bullets"):
            size, lines = self.fit(head, mw, 220, start=88)
            y = centered(lines, size, top, WHITE) + 40
            for i, b in enumerate(sc["bullets"][:3]):
                if i / max(1, len(sc["bullets"])) > reveal:
                    break
                d.rounded_rectangle((90, y, self.W - 90, y + 150), radius=36, fill=(255, 255, 255, 22),
                                    outline=(*self.accent, 200), width=3)
                d.ellipse((120, y + 35, 200, y + 115), fill=(*self.accent, 255))
                d.text((160, y + 75), str(i + 1), font=self.font(56), fill=(10, 14, 28, 255), anchor="mm")
                bs, bl = self.fit(b, self.W - 400, 120, start=56, minimum=36)
                ty = y + 75 - int(len(bl) * bs * 1.1 / 2)
                for ln in bl:
                    d.text((235, ty), ln, font=self.font(bs), fill=WHITE)
                    ty += int(bs * 1.1)
                y += 180
        elif layout == "question":
            d.text((cx, 380), "?", font=self.font(300), fill=(*self.accent, 255), anchor="mm")
            size, lines = self.fit(head, mw, 420, start=88)
            centered(lines, size, 580, WHITE)
        elif layout == "quote":
            d.text((cx, 400), "“", font=self.font(300), fill=(*self.accent, 255), anchor="mm")
            size, lines = self.fit(head, mw, 480, start=84)
            centered(lines, size, 560, WHITE)
        else:  # big_text
            size, lines = self.fit(head, mw, bottom - top, start=150 if self.theme == "sigma" else 124)
            block = len(lines) * int(size * 1.18)
            y = top + max(0, (bottom - top - block) // 2)
            centered(lines, size, y, WHITE)
            d.rounded_rectangle((cx - 90, y - 40, cx + 90, y - 28), radius=6, fill=(*self.accent, 255))
        return layer

    def _layer(self, idx, reveal=1.0):
        key = (idx, round(reveal, 2) if self.script["scenes"][idx]["layout"] == "bullets" else 1.0)
        if key not in self._layers:
            self._layers[key] = self._content_layer(idx, reveal)
        return self._layers[key]

    # ---------- media ----------
    MEDIA_XY = (80, 470)

    def _media_frame(self, idx: int, local: float):
        from .media import BOX_H, BOX_W
        m = self.media[idx]
        if m["kind"] == "video":
            frames = m["frames"]
            if not frames:
                return None
            path = frames[min(int(local * self.fps), len(frames) - 1)]
            img = Image.open(path).convert("RGB")
        else:
            if m["path"] not in self._img_cache:
                src = Image.open(m["path"]).convert("RGB")
                scale = min(BOX_W / src.width, BOX_H / src.height)
                src = src.resize((int(src.width * scale), int(src.height * scale)), Image.LANCZOS)
                card = Image.new("RGB", (BOX_W, BOX_H), (18, 22, 38))
                card.paste(src, ((BOX_W - src.width) // 2, (BOX_H - src.height) // 2))
                self._img_cache[m["path"]] = card
            img = self._img_cache[m["path"]]
        if self._box_mask is None:
            self._box_mask = Image.new("L", (BOX_W, BOX_H), 0)
            ImageDraw.Draw(self._box_mask).rounded_rectangle((0, 0, BOX_W - 1, BOX_H - 1), radius=40, fill=255)
        return img, self._box_mask

    # ---------- characters (K-drama format) ----------
    AV = 430

    def _avatar(self, i: int, mouth_open: bool, speaking: bool):
        key = (i, mouth_open, speaking)
        if key not in self._avatars:
            c = self.chars[i]
            img = themes.custom_avatar(ROOT, c["id"], self.AV) or themes.avatar(c.get("look", "hero"), mouth_open, self.AV)
            self._avatars[key] = img if speaking else themes.dim(img)
        return self._avatars[key]

    def _dialogue(self, img, idx, t, local, offset):
        if len(self.chars) < 2:
            return
        speaker = self.script["scenes"][idx].get("speaker")
        s = self.tl["scenes"][idx]
        talking = any(w[1] - 0.05 <= t < w[2] + 0.1 for w in s["words"])
        d = ImageDraw.Draw(img)
        for i, cx in enumerate((290, 790)):
            c = self.chars[i]
            on = c["id"] == speaker
            bob = int(7 * math.sin(t * 16)) if (on and talking) else 0
            mouth = on and talking and int(t * 9) % 2 == 0
            av = self._avatar(i, mouth, on)
            x, y = cx - self.AV // 2, 505 + (0 if on else 18) + bob + offset
            if on:
                g = themes.glow(self.AV, self.accent)
                img.paste(g, (x - 60, y - 60), g)
            img.paste(av, (x, y), av)
            if on:
                d.ellipse((x - 6, y - 6, x + self.AV + 6, y + self.AV + 6), outline=(*self.accent, 255), width=8)
            nm = c.get("name", c["id"])
            nsize = 46 if d.textlength(nm, font=self.font(46)) <= 440 else 36
            d.text((cx, y + self.AV + 44), nm, font=self.font(nsize),
                   fill=WHITE if on else (130, 130, 150), anchor="mm")
            role = c.get("role", "")
            if c.get("name_ko") and self.font_ko_path:
                kf = ImageFont.truetype(self.font_ko_path, 34)
                d.text((cx, y + self.AV + 88), c["name_ko"], font=kf, fill=self.accent if on else (110, 110, 130), anchor="mm")
                role = ""
            d.text((cx, y + self.AV + 90), role, font=self.font(30),
                   fill=self.accent if on else (110, 110, 130), anchor="mm")

    def _subtitle(self, img, text, local):
        d = ImageDraw.Draw(img)
        size, lines = self.fit(text, self.W - 160, 330, start=62, minimum=40)
        y = 1215
        for ln in lines:
            d.text((self.W // 2, y), ln, font=self.font(size), fill=(255, 244, 200), anchor="mt",
                   stroke_width=6, stroke_fill=(0, 0, 0, 255))
            y += int(size * 1.2)

    # ---------- chrome ----------
    def _chrome(self, img, t, total):
        d = ImageDraw.Draw(img)
        img.paste(self.logo, (60, 70), self.logo)
        d.text((60 + self.logo.width + 24, 110), self.cfg["channel"]["name"], font=self.font(40),
               fill=WHITE, anchor="lm")
        d.text((60 + self.logo.width + 24, 160), self.cfg["channel"]["handle"], font=self.font(30),
               fill=(160, 170, 190), anchor="lm")
        tw = d.textlength(self.label, font=self.font(34))
        d.rounded_rectangle((60, 215, 60 + tw + 50, 275), radius=30, fill=(*self.accent, 255))
        d.text((60 + tw / 2 + 25, 245), self.label, font=self.font(34), fill=(10, 14, 28), anchor="mm")
        if self.theme == "drama" and self.font_ko_path:
            kf = ImageFont.truetype(self.font_ko_path, 46)
            ser = self.script.get("series")
            d.text((self.W - 60, 120), f"제 {ser['episode']}화" if ser else "드라마", font=kf,
                   fill=(*self.accent, 255), anchor="rm")
            d.text((self.W - 60, 172), f"EP. {ser['episode']}" if ser else "PARODY", font=self.font(30),
                   fill=(200, 190, 210), anchor="rm")
        # progress bar sits above YouTube's bottom UI
        d.rounded_rectangle((60, 1560, self.W - 60, 1568), radius=4, fill=(255, 255, 255, 40))
        d.rounded_rectangle((60, 1560, 60 + (self.W - 120) * min(1, t / total), 1568), radius=4,
                            fill=self.accent)

    def _captions(self, img, t, sc_idx):
        words = self.tl["scenes"][sc_idx]["words"]
        if self.theme == "sigma":
            words = [(w.upper(), a, b) for w, a, b in words]
        # chunk into groups of <=4 words, breaking on punctuation
        chunks, cur = [], []
        for w in words:
            cur.append(w)
            if len(cur) >= 4 or w[0].rstrip()[-1:] in ".?!,;:":
                chunks.append(cur)
                cur = []
        if cur:
            chunks.append(cur)
        active = None
        for ch in chunks:
            if ch[0][1] - 0.05 <= t:
                active = ch
        if not active:
            return
        d = ImageDraw.Draw(img)
        size = 74
        f = self.font(size)
        space = d.textlength(" ", font=f)
        widths = [d.textlength(w[0], font=f) for w in active]
        total_w = sum(widths) + space * (len(active) - 1)
        if total_w > self.W - 120:
            size = 58
            f = self.font(size)
            space = d.textlength(" ", font=f)
            widths = [d.textlength(w[0], font=f) for w in active]
            total_w = sum(widths) + space * (len(active) - 1)
        x, y = (self.W - total_w) / 2, 1230
        for (w, t0, t1), wd in zip(active, widths):
            is_now = t0 - 0.02 <= t < t1 + 0.12
            d.text((x, y), w, font=f, fill=(*self.accent, 255) if is_now else WHITE, anchor="lm",
                   stroke_width=6, stroke_fill=(0, 0, 0, 255))
            x += wd + space

    def _shade(self):
        """Dark top/bottom gradient so chrome and subtitles stay readable over full-bleed footage."""
        if not hasattr(self, "_shade_img"):
            a = Image.new("L", (1, self.H))
            for y in range(self.H):
                top = max(0, 1 - y / 520) * 190
                bot = max(0, (y - 1000) / (self.H - 1000)) * 215
                a.putpixel((0, y), int(max(top, bot)))
            sh = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
            sh.putalpha(a.resize((self.W, self.H)))
            self._shade_img = sh
        return self._shade_img

    def _zoom(self, img, t, local, total, idx):
        """sigma: hard punch-in on every scene + a little shake; drama: slow cinematic push."""
        if self.theme == "sigma":
            z = 1 + 0.16 * max(0.0, 1 - local / 0.45) ** 2 + 0.03 * (t / total)
            r = random.Random(int(t * self.fps))
            dx, dy = (r.uniform(-12, 12), r.uniform(-12, 12)) if local < 0.14 else (0, 0)
        elif self.theme == "drama":
            z = 1 + 0.035 * min(1.0, local / 3.0) + (0.04 * max(0.0, 1 - local / 0.3) ** 2)
            dx = dy = 0
        else:
            return img
        bw, bh = self.W / z, self.H / z
        x0, y0 = (self.W - bw) / 2 + dx, (self.H - bh) / 2 + dy
        return img.resize((self.W, self.H), Image.BILINEAR, box=(x0, y0, x0 + bw, y0 + bh))

    # ---------- main loop ----------
    def frame(self, n: int):
        t = n / self.fps
        total = self.tl["total"]
        idx = next((i for i, s in enumerate(self.tl["scenes"]) if t < s["end"]), len(self.tl["scenes"]) - 1)
        s = self.tl["scenes"][idx]
        full = idx in self.media and self.media[idx].get("full")
        if full:
            frames = self.media[idx]["frames"]
            lt = t - s["start"]
            img = Image.open(frames[min(int(lt * self.fps), len(frames) - 1)]).convert("RGBA")
            img.alpha_composite(self._shade())
        else:
            img = self.bg.copy().convert("RGBA")
            for bx, by, spd, ph in self.blobs:
                x = int((bx + 0.12 * math.sin(t * spd + ph * 6)) * self.W - 350)
                y = int((by + 0.10 * math.cos(t * spd * 0.8 + ph * 6)) * self.H - 350)
                img.paste(self.blob_sprite, (x, y), self.blob_sprite)

        local = t - s["start"]
        prog = min(1.0, local / 0.35)
        ease = 1 - (1 - prog) ** 3
        reveal = min(1.0, local / max(0.5, (s["end"] - s["start"]) * 0.6))
        layer = self._layer(idx, reveal)
        if prog < 1:
            layer = layer.copy()
            layer.putalpha(layer.getchannel("A").point(lambda p: int(p * ease)))
        offset = int((1 - ease) * 60)
        img.paste(layer, (0, offset), layer)
        if idx in self.media and not full:
            got = self._media_frame(idx, local)
            if got:
                mx, my = self.MEDIA_XY
                img.paste(got[0], (mx, my + offset), got[1])
        sc = self.script["scenes"][idx]
        if sc["layout"] == "dialogue":
            self._dialogue(img, idx, t, local, offset)
        img = img.convert("RGB")
        if self.vig is not None:
            img.paste(self.vig, (0, 0), self.vig)
        img = self._zoom(img, t, local, total, idx)
        self._chrome(img, t, total)
        if full and self.media[idx].get("credit"):
            ImageDraw.Draw(img).text((60, 1520), f"Clip: {self.media[idx]['credit']} · used for parody/commentary",
                                     font=self.font(26), fill=(210, 210, 220), stroke_width=3, stroke_fill=(0, 0, 0))
        if sc.get("subtitle") or sc["layout"] in ("dialogue", "clip_dub"):
            self._subtitle(img, sc.get("subtitle") or sc["narration"], local)
        else:
            self._captions(img, t, idx)
        return img

    def render(self, out: Path, voice: Path, music: Path | None = None):
        total = self.tl["total"] + 0.4
        frames = int(total * self.fps)
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{self.W}x{self.H}", "-r", str(self.fps), "-i", "-", "-i", str(voice)]
        if music:
            vol = self.cfg["video"].get("music_volume", 0.06) * self.th["music_gain"]
            cmd += ["-stream_loop", "-1", "-i", str(music), "-filter_complex",
                    f"[1:a]asplit=2[v1][v2];[2:a]volume={vol}[m];"
                    f"[m][v2]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=350[duck];"
                    f"[v1][duck]amix=inputs=2:duration=first:normalize=0,"
                    f"afade=t=out:st={total - 1.2:.2f}:d=1.2[a]",
                    "-map", "0:v", "-map", "[a]"]
        else:
            cmd += ["-map", "0:v", "-map", "1:a"]
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.2f}", "-movflags", "+faststart", str(out)]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        try:
            for n in range(frames):
                p.stdin.write(self.frame(n).tobytes())
        finally:
            p.stdin.close()
            p.wait()
        if p.returncode:
            raise RuntimeError("ffmpeg failed")
        return out
