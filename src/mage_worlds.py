"""Illustrated, domain-specific scenes for Mage: the picture should be the product, not a box with text in it.

A cab app shows cars moving on a city map and a rider's search ring catching the nearest one; ticketing shows a seat map being
bought out and a waiting-room queue; a stadium shows the crowd and the gates; matrimony shows profile cards, a match score and a
funnel from crores of profiles to a handful; a streaming app shows the origin and the edge servers near viewers.
Everything is drawn from shapes, frame by frame, so there are no image licences.
"""
import math
import random

from PIL import ImageDraw

INK, MUTED = (236, 242, 255), (140, 158, 200)
CYAN, GREEN, RED, AMBER = (56, 189, 248), (74, 222, 128), (248, 113, 113), (251, 191, 36)
BOX, LINE = (14, 26, 62), (70, 110, 190)

# one palette per kind of product: (background top, background bottom, accent)
THEMES = {
    "cab": ((8, 14, 34), (18, 28, 62), (250, 204, 21)),
    "ticket": ((22, 8, 38), (46, 14, 70), (244, 63, 94)),
    "sport": ((6, 24, 28), (10, 46, 44), (74, 222, 128)),
    "match": ((34, 8, 30), (62, 14, 52), (251, 113, 133)),
    "video": ((10, 10, 14), (30, 12, 18), (239, 68, 68)),
    "chat": ((6, 24, 26), (10, 44, 44), (34, 197, 94)),
    "pay": ((8, 16, 36), (12, 38, 62), (45, 212, 191)),
    "social": ((16, 10, 40), (34, 18, 76), (168, 128, 255)),
    "generic": ((8, 15, 38), (16, 30, 70), (250, 204, 21)),
}


def _ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def _back(x):
    x = max(0.0, min(1.0, x))
    c = 1.70158
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def _mix(a, b, t):
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


class Worlds:
    """Mixin for Mage: needs self.font, self.mono, self.chip, self.acc, self.reveal_times."""

    # ------------------------------------------------------------------ title art, one per kind of product
    def theme_art(self, d, t, theme):
        rnd = random.Random(3)
        y0 = 1280
        if theme == "cab":  # night skyline with lit windows and cars sliding along the road
            for i in range(14):
                bw = rnd.randint(60, 110)
                bx = i * 80 - 20
                bh = rnd.randint(140, 380)
                d.rectangle((bx, y0 + 380 - bh, bx + bw, y0 + 380), fill=(14, 22, 52))
                for wy in range(y0 + 380 - bh + 14, y0 + 360, 30):
                    for wx in range(bx + 10, bx + bw - 10, 22):
                        if rnd.random() < 0.35:
                            d.rectangle((wx, wy, wx + 8, wy + 12), fill=(250, 220, 120, 190))
            d.rectangle((0, y0 + 380, 1080, y0 + 450), fill=(10, 14, 30))
            for k in range(5):
                x = ((t * 140 * (1 if k % 2 else -1) + k * 230) % 1300) - 110
                self._car(d, x, y0 + 415, (250, 204, 21) if k % 2 else (56, 189, 248), 1 if k % 2 else -1, 1.0)
        elif theme == "ticket":  # stage lights over a crowd
            for k in range(7):
                cx = 90 + k * 150
                sw = math.sin(t * 1.3 + k)
                d.polygon([(cx, y0 - 20), (cx - 90 + sw * 50, y0 + 380), (cx + 90 + sw * 50, y0 + 380)], fill=(*self.acc, 34))
                d.ellipse((cx - 12, y0 - 32, cx + 12, y0 - 8), fill=(255, 255, 255))
            for r in range(3):
                for i in range(15):
                    x = i * 76 + (r % 2) * 38
                    y = y0 + 300 + r * 52 + 8 * math.sin(t * 3 + i + r)
                    d.ellipse((x - 20, y - 20, x + 20, y + 20), fill=(8 + r * 6, 4, 18 + r * 8))
                    d.rectangle((x - 22, y + 14, x + 22, y + 120), fill=(8 + r * 6, 4, 18 + r * 8))
                    if (i + r) % 4 == 0:  # raised phone torches
                        d.rectangle((x + 14, y - 40 - 6 * math.sin(t * 5 + i), x + 24, y - 14), fill=(255, 245, 200))
        elif theme == "sport":  # floodlit stadium ring
            cx, cy = 540, y0 + 230
            d.ellipse((cx - 470, cy - 160, cx + 470, cy + 160), outline=(40, 90, 70), width=3)
            d.ellipse((cx - 330, cy - 100, cx + 330, cy + 100), fill=(18, 84, 56), outline=(120, 200, 150), width=3)
            d.rectangle((cx - 36, cy - 56, cx + 36, cy + 56), fill=(170, 150, 100))
            for k in range(60):
                a = k / 60 * math.tau
                rr = 1.0 + 0.1 * math.sin(t * 4 + k)
                d.ellipse((cx + 400 * math.cos(a) * rr - 6, cy + 128 * math.sin(a) * rr - 6, cx + 400 * math.cos(a) * rr + 6, cy + 128 * math.sin(a) * rr + 6),
                          fill=(255, 220, 120) if k % 3 else (90, 200, 255))
            for sx in (-1, 1):
                d.line((cx + sx * 480, cy - 160, cx + sx * 480, cy - 330), fill=(120, 140, 170), width=6)
                d.ellipse((cx + sx * 480 - 28, cy - 360, cx + sx * 480 + 28, cy - 304), fill=(255, 250, 220))
        elif theme == "match":  # hearts drifting up
            for k in range(14):
                x = (k * 83 + 40) % 1000 + 40
                y = y0 + 420 - ((t * 60 + k * 61) % 520)
                s = 18 + (k % 4) * 8
                self._heart(d, x + 14 * math.sin(t + k), y, s, (*self.acc, 150))
        elif theme == "video":  # a play button with film perforations
            d.rounded_rectangle((300, y0 + 40, 780, y0 + 330), radius=26, fill=(24, 12, 16), outline=self.acc, width=4)
            d.polygon([(500, y0 + 110), (500, y0 + 260), (620, y0 + 185)], fill=self.acc)
            for i in range(10):
                d.rectangle((60 + i * 100, y0 + 360, 100 + i * 100, y0 + 388), fill=(30, 20, 24))
            d.rectangle((300, y0 + 350, 300 + 480 * ((t * 0.15) % 1), y0 + 358), fill=self.acc)
        elif theme == "chat":  # floating message bubbles
            for k in range(6):
                x = 140 + (k % 2) * 520
                y = y0 + 60 + k * 62 - 8 * math.sin(t * 2 + k)
                w = 200 + (k * 37) % 150
                d.rounded_rectangle((x, y, x + w, y + 46), radius=22, fill=(*self.acc, 80) if k % 2 else (30, 60, 60, 200))
        elif theme == "pay":  # coins
            for k in range(9):
                x = 120 + k * 105
                y = y0 + 260 + 40 * math.sin(t * 2 + k) - (k % 3) * 40
                d.ellipse((x - 34, y - 34, x + 34, y + 34), fill=(*self.acc, 70), outline=self.acc, width=3)
                d.text((x, y), "Rs" if k % 2 else "$", font=self.font(30), fill=self.acc, anchor="mm")
        elif theme == "social":
            for k in range(18):
                x, y = 120 + (k * 97) % 860, y0 + 100 + (k * 53) % 300
                d.ellipse((x - 26, y - 26, x + 26, y + 26), fill=(*self.acc, 70), outline=(*self.acc, 200), width=2)
                for j in range(2):
                    k2 = (k * 5 + j * 7 + 3) % 18
                    d.line((x, y, 120 + (k2 * 97) % 860, y0 + 100 + (k2 * 53) % 300), fill=(*self.acc, 40), width=2)

    def _car(self, d, x, y, col, direction=1, s=1.0, vertical=False):
        w, h = (46 * s, 22 * s)
        if vertical:
            w, h = h, w
        d.rounded_rectangle((x - w / 2, y - h / 2, x + w / 2, y + h / 2), radius=6 * s, fill=col)
        if vertical:
            d.rectangle((x - w / 2 + 3 * s, y - h / 4, x + w / 2 - 3 * s, y + h / 4), fill=(20, 24, 40, 170))
        else:
            d.rectangle((x - w / 4, y - h / 2 + 3 * s, x + w / 4, y + h / 2 - 3 * s), fill=(20, 24, 40, 170))
            d.ellipse((x + direction * w / 2 - 4 * s, y - 4 * s, x + direction * w / 2 + 2 * s, y + 4 * s), fill=(255, 250, 210))

    def _heart(self, d, x, y, s, fill):
        d.ellipse((x - s, y - s, x, y), fill=fill)
        d.ellipse((x, y - s, x + s, y), fill=fill)
        d.polygon([(x - s, y - s * 0.35), (x + s, y - s * 0.35), (x, y + s * 1.05)], fill=fill)

    def _person(self, d, x, y, s, col):
        d.ellipse((x - 6 * s, y - 15 * s, x + 6 * s, y - 3 * s), fill=col)
        d.rounded_rectangle((x - 8 * s, y - 2 * s, x + 8 * s, y + 18 * s), radius=6 * s, fill=col)

    # ------------------------------------------------------------------ city map: cabs, riders, the nearest driver
    def d_citymap(self, d, img, t, dur, data, si):
        mode = data.get("mode", "match")
        L, T, Wm, Hm = 40, 250, 1000, 1180
        d.rounded_rectangle((L, T, L + Wm, T + Hm), radius=24, fill=(10, 18, 40), outline=(50, 80, 150), width=2)
        cols, rows = 6, 8
        bw, bh = Wm / cols, Hm / rows
        for r in range(rows):  # city blocks
            for c in range(cols):
                d.rounded_rectangle((L + c * bw + 16, T + r * bh + 16, L + (c + 1) * bw - 16, T + (r + 1) * bh - 16), radius=10,
                                    fill=(16, 28, 58) if (r * 7 + c * 3) % 5 else (22, 48, 52))
        rnd = random.Random(9)
        lanes = [(rnd.randint(0, rows), rnd.random(), rnd.choice((-1, 1)), rnd.random() < 0.5) for _ in range(16)]
        pos = []
        for k, (lane, ph, sg, vert) in enumerate(lanes):
            if vert:
                lc = lane % (cols + 1)
                x = L + lc * bw
                y = T + ((ph + sg * t * 0.05) % 1) * Hm
            else:
                lr = lane % (rows + 1)
                y = T + lr * bh
                x = L + ((ph + sg * t * 0.05) % 1) * Wm
            pos.append((x, y, sg, vert))
        px, py = L + 3 * bw, T + 4 * bh  # the rider stands on a street corner
        acc = self.acc
        radius = 340 * _ease((t - 0.8) / 1.6) if mode == "match" else 0
        best, bd = None, 1e9
        for k, (x, y, sg, vert) in enumerate(pos):
            dist = math.hypot(x - px, y - py)
            if dist < bd:
                best, bd = k, dist
        for k, (x, y, sg, vert) in enumerate(pos):
            inside = mode == "match" and math.hypot(x - px, y - py) < radius
            col = GREEN if (mode == "match" and k == best and t > 2.6) else (acc if inside else (150, 160, 190))
            self._car(d, x, y, col, sg, 1.7, vertical=vert)
            if inside and t > 1.6:
                d.line((x, y, px, py), fill=(*acc, 70), width=2)
        if mode == "match":
            pulse = 0.5 + 0.5 * math.sin(t * 4)
            d.ellipse((px - radius, py - radius, px + radius, py + radius), outline=(*acc, 150), width=3)
            d.ellipse((px - 22 - 8 * pulse, py - 22 - 8 * pulse, px + 22 + 8 * pulse, py + 22 + 8 * pulse), outline=(*CYAN, 160), width=3)
            d.ellipse((px - 18, py - 18, px + 18, py + 18), fill=CYAN)
            self._person(d, px, py + 4, 0.9, (8, 16, 40))
            if t > 2.6:
                x, y, sg, vert = pos[best]
                d.line((x, y, px, py), fill=GREEN, width=5)
                self.chip(d, str(data.get("eta", "3 MIN AWAY")), (x + px) / 2, (y + py) / 2 - 40, GREEN, 22, _ease((t - 2.6) / 0.4))
            if t > 1.0:
                self.chip(d, str(data.get("rider", "RIDER")), px, py + 62, CYAN, 20, _ease((t - 1.0) / 0.4))
        elif mode == "route":  # a trip from A to B: the path draws itself and a car follows it
            ax, ay, bx, by = L + bw, T + 6 * bh, L + 5 * bw, T + 2 * bh
            path = [(ax, ay), (ax, by + bh * 2), (bx, by + bh * 2), (bx, by)]
            p = _ease((t - 0.6) / 2.4)
            total = sum(math.dist(path[i], path[i + 1]) for i in range(3))
            run, drawn = p * total, [path[0]]
            for i in range(3):
                seg = math.dist(path[i], path[i + 1])
                if run >= seg:
                    drawn.append(path[i + 1])
                    run -= seg
                else:
                    f = run / seg
                    drawn.append((path[i][0] + (path[i + 1][0] - path[i][0]) * f, path[i][1] + (path[i + 1][1] - path[i][1]) * f))
                    break
            d.line(drawn, fill=acc, width=8, joint="curve")
            d.ellipse((ax - 16, ay - 16, ax + 16, ay + 16), fill=CYAN)
            d.ellipse((bx - 16, by - 16, bx + 16, by + 16), fill=GREEN)
            self._car(d, drawn[-1][0], drawn[-1][1], acc, 1, 1.5)
            self.chip(d, "A", ax, ay + 50, CYAN, 20)
            self.chip(d, "B", bx, by - 50, GREEN, 20)
        else:  # heat: surge zones glow where demand is high
            for k, (hx, hy, hr) in enumerate(((3, 3, 210), (2, 6, 170), (5, 5, 140))):
                a = _ease((t - 0.4 - k * 0.5) / 0.6)
                pulse = 0.85 + 0.15 * math.sin(t * 3 + k)
                d.ellipse((L + hx * bw - hr * pulse, T + hy * bh - hr * pulse, L + hx * bw + hr * pulse, T + hy * bh + hr * pulse), fill=(*RED, int(90 * a)), outline=(*RED, int(200 * a)), width=3)
                if a > 0.8:
                    d.text((L + hx * bw, T + hy * bh), "1.8x" if k == 0 else "1.4x", font=self.font(44), fill=INK, anchor="mm")
        if data.get("note"):
            self.chip(d, str(data["note"]), 540, T + Hm + 80, acc, 24, _ease((t - 1.2) / 0.4))

    # ------------------------------------------------------------------ seat map: holds, races and sell-outs
    def d_seatmap(self, d, img, t, dur, data, si):
        mode = data.get("mode", "hold")
        acc = self.acc
        rows, cols = 9, 16
        gx0, gy0, cs = 90, 560, 56
        label = str(data.get("stage", "SCREEN" if data.get("venue") == "cinema" else "STAGE")).upper()
        d.rounded_rectangle((220, 400, 860, 450), radius=14, fill=(*acc, 70), outline=acc, width=3)
        d.text((540, 425), label, font=self.mono(24), fill=INK, anchor="mm")
        rnd = random.Random(4)
        order = list(range(rows * cols))
        rnd.shuffle(order)
        for r in range(rows):
            for c in range(cols):
                x = gx0 + c * cs + 14
                y = gy0 + r * (cs + 6) + 40 * math.sin((c / (cols - 1)) * math.pi) * -0.5 + 20
                idx = r * cols + c
                rank = order.index(idx)
                state = "free"
                if mode == "soldout":
                    state = "sold" if t > 0.6 + rank * 0.012 else "free"
                elif mode == "hold":
                    if rank < 50 and t > 0.5:
                        state = "sold"
                    if rank in (60, 61, 62) and t > 1.4:
                        state = "hold" if t < 4.2 else "free"
                else:  # race: two buyers click the same seat
                    if rank < 70:
                        state = "sold"
                    if rank == 70 and t > 1.4:
                        state = "hold" if t < 3.2 else "sold"
                col = {"free": (40, 70, 130), "sold": (120, 40, 56), "hold": AMBER}[state]
                d.rounded_rectangle((x, y, x + cs - 12, y + cs - 12), radius=10, fill=col)
                if state == "hold":
                    d.rounded_rectangle((x - 3, y - 3, x + cs - 9, y + cs - 9), radius=12, outline=(255, 255, 255), width=2)
        # legend
        for i, (nm, col) in enumerate((("FREE", (40, 70, 130)), ("HELD", AMBER), ("SOLD", (120, 40, 56)))):
            d.rounded_rectangle((200 + i * 240, 1160, 226 + i * 240, 1186), radius=6, fill=col)
            d.text((238 + i * 240, 1173), nm, font=self.mono(20), fill=MUTED, anchor="lm")
        if mode == "hold" and 1.4 < t < 4.4:  # the hold timer ring
            frac = max(0.0, 1 - (t - 1.4) / 2.8)
            d.arc((470, 1260, 610, 1400), -90, -90 + 360 * frac, fill=AMBER, width=10)
            d.text((540, 1330), f"{int(5 * frac):d}:{int((5 * frac % 1) * 60):02d}", font=self.mono(32), fill=INK, anchor="mm")
            self.chip(d, "SEAT HOLD, 5 MIN", 540, 1440, AMBER, 22)
        if mode == "race":
            for i, (nm, col, xo) in enumerate((("USER A", CYAN, -190), ("USER B", GREEN, 190))):
                a = _ease((t - 0.8 - i * 0.1) / 0.5)
                if a > 0:
                    d.rounded_rectangle((540 + xo - 80, 1290, 540 + xo + 80, 1340), radius=14, fill=BOX, outline=col, width=3)
                    d.text((540 + xo, 1315), nm, font=self.mono(22), fill=col, anchor="mm")
            if 1.8 < t < 3.4:
                self.chip(d, "SAME SEAT, SAME MOMENT", 540, 1240, RED, 24, _ease((t - 1.8) / 0.3))
            if t > 3.2:
                self.chip(d, "DB LOCK: A WINS, B GETS RETRY", 540, 1400, GREEN, 22, _ease((t - 3.2) / 0.4))
        if data.get("note"):
            self.chip(d, str(data["note"]), 540, 1510, acc, 24, _ease((t - 1.0) / 0.4))

    # ------------------------------------------------------------------ stadium: a field, a crowd and gates
    def d_stadium(self, d, img, t, dur, data, si):
        mode = data.get("mode", "crowd")
        acc = self.acc
        cx, cy = 540, 820
        d.ellipse((cx - 480, cy - 330, cx + 480, cy + 330), fill=(14, 40, 36), outline=(60, 120, 100), width=3)
        d.ellipse((cx - 330, cy - 210, cx + 330, cy + 210), fill=(18, 92, 60), outline=(150, 220, 170), width=3)
        for k in range(8):  # mowing stripes
            d.arc((cx - 330 + k * 20, cy - 210 + k * 12, cx + 330 - k * 20, cy + 210 - k * 12), 0, 360, fill=(22, 104, 68), width=8)
        if data.get("sport", "cricket") == "cricket":
            d.rectangle((cx - 40, cy - 90, cx + 40, cy + 90), fill=(176, 150, 98))
            d.line((cx - 40, cy - 70, cx + 40, cy - 70), fill=(255, 255, 255), width=3)
            d.line((cx - 40, cy + 70, cx + 40, cy + 70), fill=(255, 255, 255), width=3)
            bx = cx + 150 * math.cos(t * 1.2) * 0.2
            d.ellipse((cx - 8 + bx * 0, cy - 8 + 60 * math.sin(t * 2.4), cx + 8, cy + 8 + 60 * math.sin(t * 2.4)), fill=(220, 40, 40))
        else:
            d.line((cx, cy - 210, cx, cy + 210), fill=(255, 255, 255), width=3)
            d.ellipse((cx - 50, cy - 50, cx + 50, cy + 50), outline=(255, 255, 255), width=3)
        rnd = random.Random(2)
        n = 160
        for k in range(n):  # the crowd in the stands, rippling like a wave
            a = k / n * math.tau
            ring = 1 + rnd.choice((0.0, 0.05, 0.1))
            wave = 7 * math.sin(t * 3 - a * 3)
            rx, ry = 395 * ring, 285 * ring
            colr = rnd.choice(((250, 204, 21), (56, 189, 248), (240, 240, 250), (244, 114, 182), (74, 222, 128)))
            fill_in = _ease((t - 0.2 - k / n * 1.5) / 0.4)
            if fill_in > 0:
                d.ellipse((cx + rx * math.cos(a) - 6, cy + ry * math.sin(a) - 6 + wave, cx + rx * math.cos(a) + 6, cy + ry * math.sin(a) + 6 + wave), fill=colr)
        if mode == "gates":  # fans stream in through the gates
            gates = [(cx, cy - 330), (cx + 480, cy), (cx, cy + 330), (cx - 480, cy)]
            for gx, gy in gates:
                d.rounded_rectangle((gx - 40, gy - 14, gx + 40, gy + 14), radius=8, fill=BOX, outline=acc, width=3)
            for k in range(60):
                g = gates[k % 4]
                ph = ((t * 0.35 + k * 0.137) % 1)
                ox, oy = (g[0] - cx) * 1.35, (g[1] - cy) * 1.35
                x = g[0] + (cx - g[0]) * ph * 0.6 + ox * (1 - ph) * 0.25
                y = g[1] + (cy - g[1]) * ph * 0.6 + oy * (1 - ph) * 0.25
                d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(255, 255, 255))
        if mode == "load":  # a request meter bursting when the match starts
            lvl = min(1.0, max(0.0, (t - 0.6) / 2.4))
            d.rounded_rectangle((90, 1290, 990, 1330), radius=18, outline=LINE, width=2)
            d.rounded_rectangle((94, 1294, 94 + 892 * lvl, 1326), radius=14, fill=_mix(GREEN, RED, lvl))
            d.text((540, 1380), f"{int(lvl * 400000):,} REQUESTS / SEC", font=self.mono(28), fill=INK, anchor="mm")
        if data.get("count"):
            d.text((540, 1215), str(data["count"]), font=self.font(64), fill=acc, anchor="mm")
        if data.get("note"):
            self.chip(d, str(data["note"]), 540, 1470, acc, 24, _ease((t - 1.0) / 0.4))

    # ------------------------------------------------------------------ profile cards, match score, funnel
    def d_profiles(self, d, img, t, dur, data, si):
        acc = self.acc
        people = [p for p in (data.get("people") or []) if isinstance(p, dict)][:2] or [
            {"name": "Aarav", "age": 28, "city": "Pune", "tags": ["Engineer", "Travel", "Music"]},
            {"name": "Meera", "age": 26, "city": "Pune", "tags": ["Doctor", "Books", "Music"]}]
        shared = {x.lower() for x in (people[0].get("tags") or [])} & {x.lower() for x in (people[-1].get("tags") or [])}
        for i, pr in enumerate(people):
            x0 = 70 if i == 0 else 560
            p = _back((t - 0.1 - i * 0.35) / 0.55)
            if p <= 0:
                continue
            off = int((1 - min(1, p)) * (-260 if i == 0 else 260))
            x0 += off
            d.rounded_rectangle((x0, 420, x0 + 450, 1040), radius=30, fill=(28, 14, 34), outline=(*acc, 200), width=3)
            col = acc if i == 0 else CYAN
            d.ellipse((x0 + 125, 450, x0 + 325, 650), fill=(*col, 60), outline=col, width=4)
            self._person(d, x0 + 225, 585, 5.5, col)
            d.text((x0 + 225, 700), f"{pr.get('name', '')}, {pr.get('age', '')}", font=self.font(46), fill=INK, anchor="mm")
            d.text((x0 + 225, 750), str(pr.get("city", "")), font=self.mono(24), fill=MUTED, anchor="mm")
            for j, tg in enumerate((pr.get("tags") or [])[:4]):
                hit = str(tg).lower() in shared and t > 1.8
                w = self.mono(20).getlength(str(tg)) + 36
                tx = x0 + 225 - 130 + (j % 2) * 150
                ty = 820 + (j // 2) * 62
                d.rounded_rectangle((tx - w / 2 + 70, ty - 22, tx + w / 2 + 70, ty + 22), radius=20, fill=(*GREEN, 60) if hit else (40, 30, 56), outline=GREEN if hit else (90, 70, 120), width=2)
                d.text((tx + 70, ty), str(tg), font=self.mono(20), fill=GREEN if hit else INK, anchor="mm")
        if t > 1.2:  # the match score builds between the two cards
            a = _ease((t - 1.2) / 0.5)
            score = int(float(data.get("score", 92)) * _ease((t - 1.4) / 1.4))
            d.ellipse((540 - 74, 700 - 74, 540 + 74, 700 + 74), fill=(24, 10, 28), outline=acc, width=4)
            d.text((540, 700), f"{score}%", font=self.font(54), fill=acc, anchor="mm")
            self._heart(d, 540, 590 - 6 * math.sin(t * 5), 18 * (0.9 + 0.1 * math.sin(t * 5)), (*acc, int(255 * a)))
            d.line((450, 700, 466, 700), fill=acc, width=4)
            d.line((614, 700, 630, 700), fill=acc, width=4)
        crit = [str(x) for x in (data.get("criteria") or ["Age", "City", "Education", "Interests"])][:4]
        rt = self.reveal_times(si, crit, 0.1, 0.6)
        for j, cr in enumerate(crit):
            a = _ease((t - rt[j]) / 0.3)
            if a > 0:
                self.chip(d, cr, 175 + j * 243, 1160, GREEN if t > rt[j] + 0.4 else CYAN, 20, a)
        if data.get("note"):
            self.chip(d, str(data["note"]), 540, 1280, acc, 24, _ease((t - 1.6) / 0.4))

    def d_funnel(self, d, img, t, dur, data, si):
        acc = self.acc
        stages = [s for s in (data.get("stages") or []) if isinstance(s, dict)][:5] or [{"label": "All", "value": "100%"}, {"label": "Match", "value": "1%"}]
        n = len(stages)
        top, hh = 420, 150
        rt = self.reveal_times(si, [str(s.get("label", "")) for s in stages], 0.08, 0.6)
        for i, st in enumerate(stages):
            a = _ease((t - rt[i]) / 0.5)
            if a <= 0:
                continue
            wi, wo = 940 * (1 - i / n * 0.8), 940 * (1 - (i + 1) / n * 0.8)
            y = top + i * (hh + 14)
            d.polygon([(540 - wi / 2, y), (540 + wi / 2, y), (540 + wo / 2, y + hh * a), (540 - wo / 2, y + hh * a)], fill=_mix((24, 20, 52), (*acc,), 0.18 + 0.12 * i), outline=acc)
            if a > 0.8:
                d.text((540, y + hh / 2 - 22), str(st.get("value", "")), font=self.font(52), fill=INK, anchor="mm")
                d.text((540, y + hh / 2 + 28), str(st.get("label", "")).upper(), font=self.mono(20), fill=MUTED, anchor="mm")
        rnd = random.Random(6)
        for k in range(50):  # particles falling down through the funnel
            ph = ((t * 0.4 + k * 0.071) % 1)
            y = top + ph * (n * (hh + 14))
            frac = (y - top) / (n * (hh + 14))
            half = 940 * (1 - frac * 0.8) / 2 - 24
            x = 540 + (rnd.random() * 2 - 1) * half * (1 - 0.3 * frac)
            d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(255, 255, 255, 170))
        if data.get("note"):
            self.chip(d, str(data["note"]), 540, top + n * (hh + 14) + 60, acc, 24, _ease((t - 1.5) / 0.4))

    # ------------------------------------------------------------------ waiting room queue
    def d_queue(self, d, img, t, dur, data, si):
        acc = self.acc
        d.text((540, 380), str(data.get("title", "WAITING ROOM")).upper(), font=self.mono(28), fill=MUTED, anchor="mm")
        rows, cols = 12, 14
        gate_y = 1230
        rate = float(data.get("per_sec", 3))
        served = int(t * rate * 6)
        for r in range(rows):
            for c in range(cols):
                idx = r * cols + c
                x = 110 + c * 66 + (r % 2) * 20
                y = gate_y - 90 - r * 62
                if idx < served:
                    continue
                shift = min(1.0, max(0.0, (served - idx + cols) / cols))
                col = (150, 160, 200) if idx > served + 6 else acc
                self._person(d, x, y + 4 * math.sin(t * 3 + idx), 1.0, col)
        d.rounded_rectangle((220, gate_y, 860, gate_y + 70), radius=16, fill=BOX, outline=GREEN if (int(t * 2) % 2) else acc, width=4)
        d.text((540, gate_y + 35), str(data.get("gate", "BOOKING PAGE")).upper(), font=self.mono(26), fill=INK, anchor="mm")
        for k in range(6):  # a few people being let through
            ph = (t * 0.8 + k / 6) % 1
            self._person(d, 540 + (k - 2.5) * 36, gate_y + 90 + ph * 150, 0.9, GREEN)
        self.chip(d, f"IN LINE: {max(0, int(data.get('people', 50000)) - served * 40):,}", 540, 1500, acc, 26)
        if data.get("note"):
            self.chip(d, str(data["note"]), 540, 1580, CYAN, 22, _ease((t - 1.0) / 0.4))

    # ------------------------------------------------------------------ CDN / regions: origin and edge servers
    def d_cdn(self, d, img, t, dur, data, si):
        acc = self.acc
        nodes = [str(x) for x in (data.get("nodes") or ["Mumbai", "Delhi", "Chennai", "Singapore"])][:5]
        ox, oy = 540, 560
        d.rounded_rectangle((ox - 130, oy - 60, ox + 130, oy + 60), radius=18, fill=BOX, outline=RED, width=4)
        d.text((ox, oy - 12), str(data.get("origin", "ORIGIN")).upper(), font=self.mono(26), fill=INK, anchor="mm")
        d.text((ox, oy + 22), "1 copy", font=self.mono(18), fill=MUTED, anchor="mm")
        n = len(nodes)
        rt = self.reveal_times(si, nodes, 0.1, 0.6)
        for i, nm in enumerate(nodes):
            ex = 120 + i * (840 / max(1, n - 1)) if n > 1 else 540
            ey = 960 + 90 * math.sin(i * 1.7)
            a = _ease((t - rt[i]) / 0.5)
            if a <= 0:
                continue
            d.line((ox, oy + 60, ox + (ex - ox) * a, oy + 60 + (ey - 40 - oy - 60) * a), fill=LINE, width=3)
            d.rounded_rectangle((ex - 90, ey - 40, ex + 90, ey + 40), radius=14, fill=BOX, outline=acc, width=3)
            d.text((ex, ey - 8), nm.upper(), font=self.mono(20), fill=INK, anchor="mm")
            d.text((ex, ey + 20), "CACHE", font=self.mono(14), fill=GREEN, anchor="mm")
            for k in range(5):  # viewers close to this edge
                ang = k / 5 * math.tau + i
                vx, vy = ex + 120 * math.cos(ang) * 0.9, ey + 150 + 40 * math.sin(ang)
                d.line((vx, vy, ex, ey + 40), fill=(*GREEN, 90), width=2)
                self._person(d, vx, vy, 0.8, (210, 220, 240))
            if a >= 1:
                ph = (t * 0.6 + i * 0.2) % 1
                d.ellipse((ex - 6 + (vx - ex) * ph, ey + 40 + (vy - ey - 40) * ph - 6, ex + 6 + (vx - ex) * ph, ey + 40 + (vy - ey - 40) * ph + 6), fill=AMBER)
        if data.get("note"):
            self.chip(d, str(data["note"]), 540, 1360, acc, 24, _ease((t - 1.5) / 0.4))
