"""Meme visuals. Photo templates come from Imgflip plus your own pack (assets/memes/), and these hand-drawn formats need no
images at all: boy vs girl, WhatsApp-style chat, expectation vs reality, drake-style yes/no and "nobody / me".

Visual fields used: meme_style, meme_lines (list of short strings), and for photo templates meme_template/top_text/bottom_text.
Text may be English or Hinglish (Hindi in Roman letters), which suits Indian-style humour.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import themes

STYLES = ("template", "boy_girl", "chat", "expectation", "drake", "nobody")
W = 900

HELP = (
    "MEME STYLES (set visual.meme_style; default 'template'): "
    "template = photo meme (meme_template + top_text/bottom_text); "
    "boy_girl = a boy and a girl with speech bubbles, meme_lines=[situation, what he says, what she says]; "
    "chat = a WhatsApp-style conversation, meme_lines=[her message, his reply, her message, ...] (2-5 lines, alternating); "
    "expectation = meme_lines=[expectation, reality]; drake = meme_lines=[what you reject, what you prefer]; "
    "nobody = meme_lines=['Nobody:' situation line, 'Me: ...' punchline]. "
    "Mix them: relationship, boy-girl, Indian-office and Hinglish humour are all welcome (Hinglish in Roman letters is fine), "
    "but always make the joke land on the technical idea and never on a real person, religion, caste or community."
)


def _font(path, size):
    return ImageFont.truetype(path, size) if path else ImageFont.load_default(size=size)


def _wrap(d, text, font, max_w):
    lines, cur = [], ""
    for w in text.split():
        t = f"{cur} {w}".strip()
        if d.textlength(t, font=font) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + ([cur] if cur else [])


def _fit(d, text, path, max_w, max_h, start=52, minimum=26):
    size = start
    while size > minimum:
        f = _font(path, size)
        lines = _wrap(d, text, f, max_w)
        if len(lines) * size * 1.18 <= max_h:
            return f, lines, size
        size -= 3
    f = _font(path, minimum)
    return f, _wrap(d, text, f, max_w), minimum


def _text(d, xy, text, path, max_w, max_h, fill, start=52, anchor="la"):
    f, lines, size = _fit(d, text, path, max_w, max_h, start)
    x, y = xy
    for ln in lines:
        d.text((x, y), ln, font=f, fill=fill, anchor=anchor)
        y += int(size * 1.18)
    return y


def boy_girl(lines, path):
    lines = (list(lines) + ["", "", ""])[:3]
    img = Image.new("RGB", (W, 900), (250, 244, 247))
    d = ImageDraw.Draw(img)
    _text(d, (W // 2, 36), lines[0], path, W - 80, 130, (40, 30, 50), 50, anchor="ma")
    for i, (look, col) in enumerate((("hero", (110, 70, 190)), ("intern", (240, 130, 170)))):
        x0 = 40 + i * 440
        av = themes.avatar(look, False, 230)
        img.paste(av, (x0 + 100, 600), av)
        d.rounded_rectangle((x0, 210, x0 + 400, 560), radius=36, fill=(255, 255, 255), outline=col, width=6)
        d.polygon([(x0 + 150, 560), (x0 + 215, 560), (x0 + 200, 610)], fill=(255, 255, 255), outline=col)
        d.text((x0 + 200, 240), "HIM" if i == 0 else "HER", font=_font(path, 30), fill=col, anchor="ma")
        _text(d, (x0 + 200, 290), lines[1 + i], path, 340, 250, (30, 30, 40), 44, anchor="ma")
    return img


def chat(lines, path):
    lines = [l for l in lines if l][:5] or ["..."]
    h = 190 + 150 * len(lines)
    img = Image.new("RGB", (W, h), (236, 229, 221))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 110), fill=(7, 94, 84))
    d.ellipse((24, 20, 94, 90), fill=(180, 200, 196))
    d.text((120, 44), "Her", font=_font(path, 38), fill="white", anchor="lm")
    d.text((120, 82), "online", font=_font(path, 24), fill=(190, 225, 220), anchor="lm")
    y = 140
    for i, t in enumerate(lines):
        mine = i % 2 == 1
        f, ls, size = _fit(d, t, path, 560, 120, 40, 26)
        bw = int(max(d.textlength(l, font=f) for l in ls)) + 56
        bh = int(len(ls) * size * 1.2) + 34
        x0 = W - 40 - bw if mine else 40
        d.rounded_rectangle((x0, y, x0 + bw, y + bh), radius=26, fill=(220, 248, 198) if mine else (255, 255, 255))
        yy = y + 16
        for l in ls:
            d.text((x0 + 28, yy), l, font=f, fill=(20, 20, 20))
            yy += int(size * 1.2)
        if mine:
            for dx in (0, 11):  # double blue tick
                bx, by = x0 + bw - 62 + dx, y + bh - 22
                d.line([(bx, by), (bx + 6, by + 7), (bx + 18, by - 8)], fill=(52, 152, 219), width=3)
        y += bh + 24
    return img.crop((0, 0, W, min(h, y + 20)))


def expectation(lines, path):
    lines = (list(lines) + ["", ""])[:2]
    img = Image.new("RGB", (W, 900), (18, 24, 44))
    d = ImageDraw.Draw(img)
    for i, (title, col) in enumerate((("EXPECTATION", (52, 211, 153)), ("REALITY", (239, 90, 90)))):
        y0 = 20 + i * 440
        d.rounded_rectangle((20, y0, W - 20, y0 + 420), radius=36, fill=(30, 40, 72), outline=col, width=6)
        d.text((W // 2, y0 + 52), title, font=_font(path, 46), fill=col, anchor="mm")
        _text(d, (W // 2, y0 + 120), lines[i], path, W - 120, 270, "white", 58, anchor="ma")
    return img


def drake(lines, path):
    lines = (list(lines) + ["", ""])[:2]
    img = Image.new("RGB", (W, 880), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for i, (col, bg) in enumerate(((((239, 68, 68)), (254, 226, 226)), ((34, 197, 94), (220, 252, 231)))):
        y0 = i * 440
        d.rectangle((0, y0, 300, y0 + 440), fill=bg)
        cx, cy = 150, y0 + 220
        d.ellipse((cx - 90, cy - 90, cx + 90, cy + 90), fill=col)
        if i == 0:
            d.line((cx - 40, cy - 40, cx + 40, cy + 40), fill="white", width=18)
            d.line((cx - 40, cy + 40, cx + 40, cy - 40), fill="white", width=18)
        else:
            d.line((cx - 44, cy + 2, cx - 10, cy + 38), fill="white", width=18)
            d.line((cx - 10, cy + 38, cx + 48, cy - 36), fill="white", width=18)
        _text(d, (330, y0 + 60), lines[i], path, 530, 330, (20, 20, 30), 56)
        d.line((0, y0 + 440, W, y0 + 440), fill=(210, 210, 210), width=3)
    return img


def nobody(lines, path):
    lines = (list(lines) + ["", ""])[:2]
    img = Image.new("RGB", (W, 760), (15, 15, 18))
    d = ImageDraw.Draw(img)
    d.text((50, 70), lines[0] or "Nobody:", font=_font(path, 54), fill=(150, 156, 170))
    y = _text(d, (50, 330), lines[1], path, W - 100, 380, "white", 66)
    return img.crop((0, 0, W, max(560, min(760, y + 60))))


DRAWN = {"boy_girl": boy_girl, "chat": chat, "expectation": expectation, "drake": drake, "nobody": nobody}


def render(v: dict, out: Path, photo_font: str | None, ui_font: str | None):
    """Render a meme visual to `out` (PNG). Returns the path, or None if it can't be made."""
    style = v.get("meme_style") or "template"
    if style in DRAWN and v.get("meme_lines"):
        DRAWN[style]([str(x) for x in v["meme_lines"]], ui_font).convert("RGB").save(out)
        return out
    return None
