"""Visual themes and the original (flat-illustration) characters used by the K-drama parody format.

The avatars are drawn from scratch: they are not based on any real actor or show. To use your own character art,
drop PNGs named after the character id into assets/characters/ (e.g. assets/characters/chairman.png).
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

THEMES = {
    "default": {"bg": ((10, 14, 28), (4, 6, 14)), "vignette": 0.0, "music_gain": 1.0},
    "sigma": {"bg": ((26, 26, 28), (0, 0, 0)), "vignette": 0.85, "music_gain": 1.0},
    "drama": {"bg": ((54, 18, 52), (10, 8, 32)), "vignette": 0.6, "music_gain": 1.0},
}

SKIN = (238, 202, 172)

LOOKS = {  # background, suit, accent-colour details
    "chairman": {"bg": ((30, 42, 84), (12, 16, 40)), "suit": (24, 24, 30), "tie": (190, 30, 50), "hair": (176, 176, 182)},
    "intern": {"bg": ((240, 130, 170), (150, 60, 120)), "suit": (236, 228, 214), "tie": (240, 130, 170), "hair": (24, 20, 26)},
    "hero": {"bg": ((110, 70, 190), (50, 30, 100)), "suit": (70, 74, 90), "tie": (230, 230, 240), "hair": (22, 20, 24)},
    "rival": {"bg": ((170, 36, 54), (70, 14, 28)), "suit": (240, 240, 244), "tie": (20, 20, 24), "hair": (30, 24, 22)},
    "ai": {"bg": ((20, 150, 160), (8, 60, 80)), "suit": (170, 182, 196), "tie": (60, 220, 230), "hair": (0, 0, 0)},
}


def vignette(w: int, h: int, strength: float) -> Image.Image:
    """RGBA black overlay, transparent in the middle, dark at the edges."""
    radial = Image.radial_gradient("L").resize((w, h))  # 0 centre -> 255 edge
    alpha = radial.point(lambda p: int(max(0, p - 90) * strength * 1.6))
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.putalpha(alpha)
    return out


def _gradient_circle(size, c1, c2):
    g = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / size
        g.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(c1, c2)))
    return g.resize((size, size))


def avatar(look: str, mouth_open: bool, size: int = 440) -> Image.Image:
    look = look if look in LOOKS else "hero"
    pal = LOOKS[look]
    S = size * 2
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bgc = _gradient_circle(S, *pal["bg"]).convert("RGBA")
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, S - 1, S - 1), fill=255)
    img.paste(bgc, (0, 0), mask)
    d = ImageDraw.Draw(img)
    cx = S // 2

    # shoulders / suit, clipped to the circle later
    d.ellipse((cx - 330, S * 0.70, cx + 330, S * 1.35), fill=pal["suit"])
    if look != "ai":
        d.polygon([(cx - 70, S * 0.72), (cx + 70, S * 0.72), (cx, S * 0.92)], fill=(245, 245, 248))  # shirt
        d.polygon([(cx - 22, S * 0.78), (cx + 22, S * 0.78), (cx + 16, S * 0.93), (cx, S * 0.99), (cx - 16, S * 0.93)],
                  fill=pal["tie"])
        d.rectangle((cx - 42, S * 0.60, cx + 42, S * 0.74), fill=SKIN)  # neck

    if look == "ai":
        d.rounded_rectangle((cx - 40, S * 0.62, cx + 40, S * 0.74), radius=10, fill=(120, 130, 146))
        d.rounded_rectangle((cx - 190, S * 0.22, cx + 190, S * 0.66), radius=70, fill=(184, 196, 210))
        d.rounded_rectangle((cx - 160, S * 0.28, cx + 160, S * 0.60), radius=50, fill=(14, 22, 36))
        d.line((cx, S * 0.22, cx, S * 0.12), fill=(184, 196, 210), width=10)
        d.ellipse((cx - 16, S * 0.09, cx + 16, S * 0.13), fill=pal["tie"])
        for ex in (-70, 70):
            d.ellipse((cx + ex - 30, S * 0.38, cx + ex + 30, S * 0.46), fill=pal["tie"])
        if mouth_open:
            d.rounded_rectangle((cx - 50, S * 0.50, cx + 50, S * 0.56), radius=20, fill=pal["tie"])
        else:
            d.line((cx - 50, S * 0.53, cx + 50, S * 0.53), fill=pal["tie"], width=10)
    else:
        hair = pal["hair"]
        if look == "intern":  # bob behind the head
            d.rounded_rectangle((cx - 175, S * 0.20, cx + 175, S * 0.68), radius=120, fill=hair)
        d.ellipse((cx - 150, S * 0.24, cx + 150, S * 0.66), fill=SKIN)  # head
        if look == "intern":
            d.pieslice((cx - 165, S * 0.18, cx + 165, S * 0.52), 180, 360, fill=hair)
            d.polygon([(cx - 150, S * 0.36), (cx - 40, S * 0.30), (cx - 120, S * 0.46)], fill=hair)
        else:
            d.pieslice((cx - 160, S * 0.17, cx + 160, S * 0.50), 175, 365, fill=hair)
            if look == "hero":
                d.polygon([(cx - 160, S * 0.35), (cx + 40, S * 0.22), (cx + 20, S * 0.36)], fill=hair)
        ey = S * 0.42
        for ex in (-62, 62):
            d.ellipse((cx + ex - 19, ey - 12, cx + ex + 19, ey + 12), fill=(30, 26, 30))  # almond eyes
            d.ellipse((cx + ex - 7, ey - 8, cx + ex + 1, ey - 1), fill=(255, 255, 255))
        brow_y = ey - 44
        if look in ("chairman", "rival"):  # stern, angled brows
            d.line((cx - 92, brow_y - 8, cx - 30, brow_y + 10), fill=hair if look == "chairman" else (30, 24, 22), width=14)
            d.line((cx + 92, brow_y - 8, cx + 30, brow_y + 10), fill=hair if look == "chairman" else (30, 24, 22), width=14)
        else:
            d.line((cx - 92, brow_y, cx - 34, brow_y - 4), fill=(40, 32, 36), width=10)
            d.line((cx + 92, brow_y, cx + 34, brow_y - 4), fill=(40, 32, 36), width=10)
        if look == "chairman":  # glasses
            for ex in (-62, 62):
                d.rounded_rectangle((cx + ex - 40, ey - 30, cx + ex + 40, ey + 30), radius=12, outline=(20, 20, 24), width=8)
            d.line((cx - 22, ey - 4, cx + 22, ey - 4), fill=(20, 20, 24), width=8)
        if look == "intern":  # a single tear
            d.ellipse((cx + 70, ey + 26, cx + 92, ey + 64), fill=(120, 190, 255))
        my = S * 0.56
        if mouth_open:
            d.ellipse((cx - 34, my - 14, cx + 34, my + 34), fill=(120, 30, 40))
        else:
            d.arc((cx - 40, my - 10, cx + 40, my + 20), 15, 165, fill=(150, 60, 66), width=9)

    ring = Image.new("L", (S, S), 0)
    ImageDraw.Draw(ring).ellipse((0, 0, S - 1, S - 1), fill=255)
    clipped = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    clipped.paste(img, (0, 0), ring)
    return clipped.resize((size, size), Image.LANCZOS)


def dim(img: Image.Image, factor: float = 0.42) -> Image.Image:
    rgb = ImageEnhance.Brightness(img.convert("RGB")).enhance(factor)
    out = rgb.convert("RGBA")
    out.putalpha(img.getchannel("A"))
    return out


def glow(size: int, color) -> Image.Image:
    g = Image.new("RGBA", (size + 120, size + 120), (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse((40, 40, size + 80, size + 80), fill=(*color, 150))
    return g.filter(ImageFilter.GaussianBlur(28))


def custom_avatar(root: Path, char_id: str, size: int = 440) -> Image.Image | None:
    p = root / "assets" / "characters" / f"{char_id}.png"
    if not p.exists():
        return None
    img = Image.open(p).convert("RGBA")
    scale = size / min(img.size)
    img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    left, top = (img.width - size) // 2, (img.height - size) // 2
    img = img.crop((left, top, left + size, top + size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    img.putalpha(mask)
    return img
