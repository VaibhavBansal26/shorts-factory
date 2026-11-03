"""Hand-drawn icons for explainer visuals, so there are no image licences or emoji fonts to depend on.
draw(name, size, accent) -> RGBA: a white glyph on a dark disc with an accent ring."""
import math

from PIL import Image, ImageDraw

NAMES = ["brain", "tools", "document", "chat", "rocket", "warning", "lock", "clock", "money", "chart", "gear", "search",
         "bulb", "code", "cloud", "check", "cross", "bug", "fire", "bolt", "person", "database", "star", "book"]
S = 512  # drawn big, then shrunk for smooth edges
C = S // 2
WHITE = (245, 247, 250, 255)


def _glyph(name, d, ac):
    w = 22  # line width
    if name == "brain":
        d.ellipse((C - 120, C - 95, C + 5, C + 70), outline=WHITE, width=w)
        d.ellipse((C - 5, C - 95, C + 120, C + 70), outline=WHITE, width=w)
        d.arc((C - 85, C - 55, C - 15, C + 15), 200, 20, fill=ac, width=14)
        d.arc((C + 15, C - 55, C + 85, C + 15), 160, 340, fill=ac, width=14)
        d.line((C, C - 85, C, C + 70), fill=ac, width=14)
        d.rectangle((C - 25, C + 70, C + 25, C + 112), fill=WHITE)
    elif name == "tools":
        d.line((C - 95, C + 95, C + 30, C - 30), fill=WHITE, width=40)
        d.ellipse((C + 5, C - 125, C + 125, C - 5), outline=ac, width=34)
        d.line((C + 95, C + 95, C - 95, C - 95), fill=WHITE, width=26)
    elif name == "document":
        d.rounded_rectangle((C - 85, C - 115, C + 85, C + 115), radius=18, outline=WHITE, width=w)
        for i in range(4):
            d.line((C - 50, C - 60 + i * 42, C + 50 - (i == 3) * 40, C - 60 + i * 42), fill=ac if i == 0 else WHITE, width=16)
    elif name == "chat":
        d.rounded_rectangle((C - 115, C - 90, C + 115, C + 50), radius=40, outline=WHITE, width=w)
        d.polygon([(C - 50, C + 45), (C - 85, C + 115), (C + 5, C + 48)], fill=WHITE)
        for i in (-55, 0, 55):
            d.ellipse((C + i - 14, C - 38, C + i + 14, C - 10), fill=ac)
    elif name == "rocket":
        d.polygon([(C, C - 125), (C + 55, C - 10), (C + 40, C + 70), (C - 40, C + 70), (C - 55, C - 10)], outline=WHITE, width=w)
        d.ellipse((C - 24, C - 45, C + 24, C + 3), fill=ac)
        d.polygon([(C - 50, C + 30), (C - 105, C + 90), (C - 40, C + 70)], fill=WHITE)
        d.polygon([(C + 50, C + 30), (C + 105, C + 90), (C + 40, C + 70)], fill=WHITE)
        d.polygon([(C - 25, C + 85), (C, C + 135), (C + 25, C + 85)], fill=ac)
    elif name == "warning":
        d.polygon([(C, C - 120), (C + 125, C + 90), (C - 125, C + 90)], outline=ac, width=w + 4)
        d.line((C, C - 45, C, C + 20), fill=WHITE, width=26)
        d.ellipse((C - 15, C + 42, C + 15, C + 72), fill=WHITE)
    elif name == "lock":
        d.arc((C - 65, C - 125, C + 65, C + 5), 180, 360, fill=WHITE, width=w)
        d.line((C - 65, C - 60, C - 65, C - 20), fill=WHITE, width=w)
        d.line((C + 65, C - 60, C + 65, C - 20), fill=WHITE, width=w)
        d.rounded_rectangle((C - 95, C - 25, C + 95, C + 105), radius=20, fill=WHITE)
        d.ellipse((C - 18, C + 12, C + 18, C + 48), fill=ac)
        d.rectangle((C - 8, C + 35, C + 8, C + 75), fill=ac)
    elif name == "clock":
        d.ellipse((C - 115, C - 115, C + 115, C + 115), outline=WHITE, width=w)
        d.line((C, C, C, C - 75), fill=WHITE, width=20)
        d.line((C, C, C + 55, C + 30), fill=ac, width=20)
        d.ellipse((C - 14, C - 14, C + 14, C + 14), fill=WHITE)
    elif name == "money":
        d.ellipse((C - 115, C - 115, C + 115, C + 115), outline=WHITE, width=w)
        d.arc((C - 50, C - 85, C + 50, C), 90, 360, fill=ac, width=24)
        d.arc((C - 50, C - 5, C + 50, C + 85), 270, 180, fill=ac, width=24)
        d.line((C, C - 105, C, C + 105), fill=WHITE, width=14)
    elif name == "chart":
        for i, hgt in enumerate((60, 110, 170)):
            x = C - 100 + i * 80
            d.rounded_rectangle((x, C + 100 - hgt, x + 56, C + 100), radius=8, fill=ac if i == 2 else WHITE)
        d.line((C - 110, C - 70, C - 20, C - 100, C + 40, C - 70, C + 105, C - 125), fill=WHITE, width=14)
    elif name == "gear":
        for k in range(8):
            a = k * math.pi / 4
            d.line((C + 80 * math.cos(a), C + 80 * math.sin(a), C + 118 * math.cos(a), C + 118 * math.sin(a)), fill=WHITE, width=38)
        d.ellipse((C - 90, C - 90, C + 90, C + 90), outline=WHITE, width=34)
        d.ellipse((C - 30, C - 30, C + 30, C + 30), fill=ac)
    elif name == "search":
        d.ellipse((C - 105, C - 105, C + 35, C + 35), outline=WHITE, width=w + 4)
        d.line((C + 20, C + 20, C + 110, C + 110), fill=ac, width=34)
    elif name == "bulb":
        d.ellipse((C - 80, C - 125, C + 80, C + 35), outline=WHITE, width=w)
        d.rectangle((C - 40, C + 40, C + 40, C + 62), fill=WHITE)
        d.rectangle((C - 30, C + 74, C + 30, C + 94), fill=WHITE)
        d.line((C - 25, C - 20, C, C + 30, C + 25, C - 20), fill=ac, width=14)
    elif name == "code":
        d.line((C - 45, C - 85, C - 115, C, C - 45, C + 85), fill=WHITE, width=w + 6, joint="curve")
        d.line((C + 45, C - 85, C + 115, C, C + 45, C + 85), fill=WHITE, width=w + 6, joint="curve")
        d.line((C + 20, C - 100, C - 20, C + 100), fill=ac, width=w)
    elif name == "cloud":
        for cx, cy, r in ((C - 55, C + 10, 55), (C + 5, C - 35, 75), (C + 65, C + 15, 55)):
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=WHITE)
        d.rectangle((C - 55, C + 10, C + 65, C + 70), fill=WHITE)
        d.ellipse((C - 110, C + 10, C - 0, C + 70), fill=WHITE)
        d.ellipse((C + 10, C + 10, C + 120, C + 70), fill=WHITE)
    elif name == "check":
        d.line((C - 90, C + 5, C - 25, C + 70, C + 95, C - 70), fill=(80, 220, 140, 255), width=40, joint="curve")
    elif name == "cross":
        d.line((C - 80, C - 80, C + 80, C + 80), fill=(239, 90, 90, 255), width=40)
        d.line((C + 80, C - 80, C - 80, C + 80), fill=(239, 90, 90, 255), width=40)
    elif name == "bug":
        d.ellipse((C - 65, C - 50, C + 65, C + 100), fill=WHITE)
        d.ellipse((C - 40, C - 115, C + 40, C - 35), fill=WHITE)
        for sy in (-20, 30, 78):
            d.line((C - 65, C + sy, C - 120, C + sy - 25), fill=WHITE, width=16)
            d.line((C + 65, C + sy, C + 120, C + sy - 25), fill=WHITE, width=16)
        d.line((C, C - 45, C, C + 100), fill=ac, width=12)
    elif name == "fire":
        d.polygon([(C, C - 125), (C + 80, C + 10), (C + 60, C + 100), (C, C + 120), (C - 60, C + 100), (C - 80, C + 10), (C - 30, C - 40)], fill=(255, 150, 60, 255))
        d.polygon([(C, C - 10), (C + 38, C + 55), (C, C + 105), (C - 38, C + 55)], fill=(255, 224, 120, 255))
    elif name == "bolt":
        d.polygon([(C + 25, C - 125), (C - 70, C + 15), (C - 5, C + 15), (C - 30, C + 125), (C + 75, C - 25), (C + 5, C - 25)], fill=(255, 214, 90, 255))
    elif name == "person":
        d.ellipse((C - 50, C - 120, C + 50, C - 20), fill=WHITE)
        d.pieslice((C - 110, C + 5, C + 110, C + 215), 180, 360, fill=ac)
    elif name == "database":
        for i, y in enumerate((C - 70, C, C + 70)):
            d.ellipse((C - 95, y - 35, C + 95, y + 35), outline=WHITE, width=w - 4)
        d.rectangle((C - 95, C - 70, C - 85, C + 70), fill=WHITE)
        d.rectangle((C + 85, C - 70, C + 95, C + 70), fill=WHITE)
        d.ellipse((C - 95, C - 105, C + 95, C - 35), fill=ac)
    elif name == "star":
        pts = [(C + (125 if k % 2 == 0 else 55) * math.sin(k * math.pi / 5), C - 5 - (125 if k % 2 == 0 else 55) * math.cos(k * math.pi / 5)) for k in range(10)]
        d.polygon(pts, fill=(255, 214, 90, 255))
    elif name == "book":
        d.polygon([(C - 115, C - 80), (C, C - 55), (C, C + 95), (C - 115, C + 70)], outline=WHITE, width=w - 4)
        d.polygon([(C + 115, C - 80), (C, C - 55), (C, C + 95), (C + 115, C + 70)], outline=WHITE, width=w - 4)
        d.line((C - 80, C - 25, C - 30, C - 10), fill=ac, width=12)
    else:  # unknown name: a plain dot, never a crash
        d.ellipse((C - 40, C - 40, C + 40, C + 40), fill=ac)


_cache: dict = {}


def draw(name: str, size: int, accent=(96, 165, 250)) -> Image.Image:
    key = (name, size, tuple(accent))
    if key not in _cache:
        im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.ellipse((6, 6, S - 6, S - 6), fill=(22, 36, 82, 255), outline=(*accent, 255), width=14)
        _glyph(name if name in NAMES else "", d, (*accent, 255))
        _cache[key] = im.resize((size, size), Image.LANCZOS)
    return _cache[key]
