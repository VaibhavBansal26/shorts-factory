"""Architecture and ML scenes for Mage: a real architecture diagram with typed components and a request travelling through it, a
storefront and order lifecycle (e-commerce), recommendation visuals (embeddings, the user-item matrix, a ranked feed), and ML
algorithm animations (gradient descent, clustering, classification, a neural network, a decision tree, attention).
All drawn from shapes, frame by frame."""
import math
import random

INK, MUTED = (236, 242, 255), (140, 158, 200)
CYAN, GREEN, RED, AMBER, VIOLET, PINK = (56, 189, 248), (74, 222, 128), (248, 113, 113), (251, 191, 36), (168, 128, 255), (244, 114, 182)
BOX, LINE = (14, 26, 62), (70, 110, 190)

KIND_COLOR = {"client": CYAN, "gateway": (250, 204, 21), "lb": (250, 204, 21), "service": (96, 165, 250), "db": GREEN, "cache": AMBER,
              "queue": VIOLET, "search": PINK, "cdn": CYAN, "storage": (160, 170, 190), "ml": (192, 132, 252), "external": (148, 163, 184),
              "worker": (96, 165, 250)}


def _ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def _back(x):
    x = max(0.0, min(1.0, x))
    c = 1.70158
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def _mix(a, b, t):
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


class Arch:
    """Mixin for Mage: needs self.font, self.mono, self.chip, self.acc, self.reveal_times."""

    # ------------------------------------------------------------------ component icons
    def _icon(self, d, kind, cx, cy, s, col):
        w = max(2, int(3 * s))
        if kind == "client":
            d.rounded_rectangle((cx - 11 * s, cy - 17 * s, cx + 11 * s, cy + 17 * s), radius=4 * s, outline=col, width=w)
            d.ellipse((cx - 2 * s, cy + 11 * s, cx + 2 * s, cy + 15 * s), fill=col)
        elif kind in ("gateway", "lb"):
            d.line((cx, cy + 16 * s, cx, cy - 2 * s), fill=col, width=w)
            d.line((cx, cy - 2 * s, cx - 14 * s, cy - 16 * s), fill=col, width=w)
            d.line((cx, cy - 2 * s, cx + 14 * s, cy - 16 * s), fill=col, width=w)
            d.polygon([(cx - 16 * s, cy - 8 * s), (cx - 16 * s, cy - 18 * s), (cx - 6 * s, cy - 18 * s)], fill=col)
            d.polygon([(cx + 16 * s, cy - 8 * s), (cx + 16 * s, cy - 18 * s), (cx + 6 * s, cy - 18 * s)], fill=col)
        elif kind in ("service", "worker"):
            for k in range(8):
                a = k * math.pi / 4
                d.line((cx + 11 * s * math.cos(a), cy + 11 * s * math.sin(a), cx + 17 * s * math.cos(a), cy + 17 * s * math.sin(a)), fill=col, width=int(5 * s) or 3)
            d.ellipse((cx - 12 * s, cy - 12 * s, cx + 12 * s, cy + 12 * s), outline=col, width=w)
            d.ellipse((cx - 4 * s, cy - 4 * s, cx + 4 * s, cy + 4 * s), fill=col)
        elif kind == "db":
            for yy in (-10, 0, 10):
                d.ellipse((cx - 15 * s, cy + (yy - 6) * s, cx + 15 * s, cy + (yy + 6) * s), outline=col, width=w)
            d.line((cx - 15 * s, cy - 10 * s, cx - 15 * s, cy + 10 * s), fill=col, width=w)
            d.line((cx + 15 * s, cy - 10 * s, cx + 15 * s, cy + 10 * s), fill=col, width=w)
        elif kind == "cache":
            d.polygon([(cx + 4 * s, cy - 18 * s), (cx - 12 * s, cy + 2 * s), (cx - 1 * s, cy + 2 * s), (cx - 5 * s, cy + 18 * s), (cx + 12 * s, cy - 4 * s), (cx + 1 * s, cy - 4 * s)], fill=col)
        elif kind == "queue":
            for i, yy in enumerate((-12, -2, 8)):
                d.rounded_rectangle((cx - 16 * s, cy + yy * s, cx + (10 + 4 * i) * s, cy + (yy + 7) * s), radius=3 * s, outline=col, width=max(2, int(2 * s)))
            d.polygon([(cx + 12 * s, cy - 16 * s), (cx + 20 * s, cy - 8 * s), (cx + 12 * s, cy)], fill=col)
        elif kind == "search":
            d.ellipse((cx - 14 * s, cy - 14 * s, cx + 6 * s, cy + 6 * s), outline=col, width=w)
            d.line((cx + 4 * s, cy + 4 * s, cx + 16 * s, cy + 16 * s), fill=col, width=w + 1)
        elif kind == "cdn":
            for ox, oy, r in ((-8, 4, 8), (2, -4, 11), (11, 5, 8)):
                d.ellipse((cx + (ox - r) * s, cy + (oy - r) * s, cx + (ox + r) * s, cy + (oy + r) * s), fill=col)
        elif kind == "storage":
            d.polygon([(cx - 14 * s, cy - 10 * s), (cx + 14 * s, cy - 10 * s), (cx + 10 * s, cy + 16 * s), (cx - 10 * s, cy + 16 * s)], outline=col, width=w)
            d.ellipse((cx - 14 * s, cy - 15 * s, cx + 14 * s, cy - 5 * s), outline=col, width=w)
        elif kind == "ml":
            pts = [(-12, -8), (-12, 8), (0, -12), (0, 12), (12, 0)]
            for i, (ax, ay) in enumerate(pts):
                for (bx, by) in pts[i + 1:]:
                    if (ax < bx):
                        d.line((cx + ax * s, cy + ay * s, cx + bx * s, cy + by * s), fill=(*col, 120), width=max(1, int(1.5 * s)))
            for ax, ay in pts:
                d.ellipse((cx + ax * s - 4 * s, cy + ay * s - 4 * s, cx + ax * s + 4 * s, cy + ay * s + 4 * s), fill=col)
        else:  # external / unknown: a globe
            d.ellipse((cx - 15 * s, cy - 15 * s, cx + 15 * s, cy + 15 * s), outline=col, width=w)
            d.ellipse((cx - 6 * s, cy - 15 * s, cx + 6 * s, cy + 15 * s), outline=col, width=max(1, int(2 * s)))
            d.line((cx - 15 * s, cy, cx + 15 * s, cy), fill=col, width=max(1, int(2 * s)))

    # ------------------------------------------------------------------ architecture diagram
    def d_arch(self, d, img, t, dur, data, si):
        layers = []
        for ly in data.get("layers") or []:
            row = [n if isinstance(n, dict) else {"label": str(n)} for n in (ly if isinstance(ly, list) else [ly])][:5]
            if row:
                layers.append(row)
        layers = layers[:6] or [[{"label": "Client", "kind": "client"}], [{"label": "Server", "kind": "service"}], [{"label": "DB", "kind": "db"}]]
        n = len(layers)
        top, bottom = 360, 1330
        step = (bottom - top) / max(1, n - 1) if n > 1 else 0
        pos, order = {}, []
        for li, row in enumerate(layers):
            m = len(row)
            bw = min(240, (1000 - (m - 1) * 26) / m)
            for ni, nd in enumerate(row):
                cx = 540 + (ni - (m - 1) / 2) * (bw + 26)
                cy = top + li * step if n > 1 else 840
                pos[nd.get("label", f"{li}-{ni}")] = (cx, cy, bw, nd.get("kind", "service"), li)
                order.append(nd.get("label", f"{li}-{ni}"))
        rt = self.reveal_times(si, order, 0.06, 0.5)
        shown = {lb: _ease((t - rt[i]) / 0.45) for i, lb in enumerate(order)}
        # edges (explicit, else each node to the nearest nodes of the next layer)
        edges = [(a, b) for a, b in (data.get("edges") or []) if a in pos and b in pos]
        if not edges:
            for li in range(n - 1):
                for nd in layers[li]:
                    a = nd.get("label")
                    nxt = [x.get("label") for x in layers[li + 1]]
                    ax = pos[a][0]
                    for b in sorted(nxt, key=lambda q: abs(pos[q][0] - ax))[:2 if len(nxt) > 1 else 1]:
                        edges.append((a, b))
        for a, b in edges:
            pa, pb = pos[a], pos[b]
            k = min(shown[a], shown[b])
            if k <= 0:
                continue
            x0, y0, x1, y1 = pa[0], pa[1] + 48, pb[0], pb[1] - 48
            d.line((x0, y0, x0 + (x1 - x0) * k, y0 + (y1 - y0) * k), fill=(*LINE, 200), width=3)
        flow = [f for f in (data.get("flow") or []) if f in pos]
        t0 = max(rt) + 0.9 if rt else 1.5
        seg = 0
        if len(flow) > 1 and t > t0:
            seg = int((t - t0) / 0.75) % (len(flow) - 1)
        lit = set()
        if len(flow) > 1 and t > t0:
            lit = set(flow[:seg + 2])
        for lb in order:
            cx, cy, bw, kind, li = pos[lb]
            a = _back((t - rt[order.index(lb)]) / 0.45)
            if a <= 0:
                continue
            col = KIND_COLOR.get(kind, CYAN)
            s = 0.88 + 0.12 * min(1, a)
            hw, hh = bw * s / 2, 58 * s
            on = lb in lit
            d.rounded_rectangle((cx - hw, cy - hh, cx + hw, cy + hh), radius=16, fill=(24, 36, 78) if on else BOX, outline=(255, 255, 255) if on else col, width=4 if on else 3)
            self._icon(d, kind, cx, cy - 16 * s, 0.9 * s, col)
            size = 26
            while self.font(size).getlength(lb) > bw - 18 and size > 15:
                size -= 2
            d.text((cx, cy + 32 * s), lb, font=self.font(size), fill=INK, anchor="mm")
        if len(flow) > 1 and t > t0:  # the request travels along the path
            f = ((t - t0) / 0.75) % (len(flow) - 1)
            i = min(int(f), len(flow) - 2)
            fr = f - i
            pa, pb = pos[flow[i]], pos[flow[i + 1]]
            px = pa[0] + (pb[0] - pa[0]) * fr
            py = (pa[1] + 48) + ((pb[1] - 48) - (pa[1] + 48)) * fr
            d.ellipse((px - 16, py - 16, px + 16, py + 16), fill=(*self.acc, 90))
            d.ellipse((px - 8, py - 8, px + 8, py + 8), fill=self.acc)
            d.line((pa[0], pa[1] + 48, pb[0], pb[1] - 48), fill=self.acc, width=5)
        if data.get("note"):
            self.chip(d, str(data["note"]), 540, 1440, self.acc, 24, _ease((t - 1.0) / 0.4))

    # ------------------------------------------------------------------ storefront and oversell race (e-commerce)
    def d_storefront(self, d, img, t, dur, data, si):
        acc = self.acc
        mode = data.get("mode", "browse")
        prods = [p if isinstance(p, dict) else {"name": str(p)} for p in (data.get("products") or [])][:6] or [
            {"name": "Sneakers", "price": "Rs 2,499"}, {"name": "Headphones", "price": "Rs 1,999"}, {"name": "Backpack", "price": "Rs 1,299"},
            {"name": "Watch", "price": "Rs 3,499"}, {"name": "Bottle", "price": "Rs 499"}, {"name": "Lamp", "price": "Rs 899"}]
        hues = [(255, 140, 66), (96, 165, 250), (74, 222, 128), (244, 114, 182), (250, 204, 21), (168, 128, 255)]
        if mode == "browse":
            cart_x, cart_y = 930, 400
            d.rounded_rectangle((60, 340, 1020, 440), radius=18, fill=BOX, outline=LINE, width=2)
            d.text((110, 390), str(data.get("store", "STORE")).upper(), font=self.mono(26), fill=INK, anchor="lm")
            d.rounded_rectangle((560, 362, 800, 418), radius=26, outline=(90, 110, 160), width=2)
            d.text((590, 390), "search...", font=self.mono(20), fill=MUTED, anchor="lm")
            d.polygon([(cart_x - 22, cart_y - 14), (cart_x + 22, cart_y - 14), (cart_x + 14, cart_y + 14), (cart_x - 14, cart_y + 14)], outline=INK, width=3)
            d.ellipse((cart_x - 14, cart_y + 20, cart_x - 6, cart_y + 28), fill=INK)
            d.ellipse((cart_x + 6, cart_y + 20, cart_x + 14, cart_y + 28), fill=INK)
            rt = self.reveal_times(si, [p.get("name", "") for p in prods], 0.05, 0.5)
            count = 0
            for i, pr in enumerate(prods):
                r, c = divmod(i, 2)
                x0, y0 = 70 + c * 480, 480 + r * 270
                a = _back((t - rt[i]) / 0.5)
                if a <= 0:
                    continue
                s = 0.9 + 0.1 * min(1, a)
                d.rounded_rectangle((x0, y0, x0 + 460 * s, y0 + 250 * s), radius=20, fill=BOX, outline=(60, 90, 160), width=2)
                col = hues[i % len(hues)]
                d.rounded_rectangle((x0 + 16, y0 + 16, x0 + 170 * s, y0 + 170 * s), radius=14, fill=(*col, 90), outline=col, width=2)
                d.ellipse((x0 + 60, y0 + 56, x0 + 130, y0 + 126), fill=col)
                d.text((x0 + 192, y0 + 50), str(pr.get("name", "")), font=self.font(32), fill=INK, anchor="lm")
                d.text((x0 + 192, y0 + 100), str(pr.get("price", "")), font=self.mono(26), fill=GREEN, anchor="lm")
                d.rounded_rectangle((x0 + 192, y0 + 150, x0 + 430, y0 + 200), radius=14, fill=acc if a >= 1 else (60, 60, 90))
                d.text((x0 + 311, y0 + 175), "Add to cart", font=self.mono(20), fill=(20, 16, 10), anchor="mm")
                fly = (t - rt[i] - 0.7) / 0.6
                if 0 < fly < 1:  # the item flies into the cart
                    fx = x0 + 100 + (cart_x - x0 - 100) * _ease(fly)
                    fy = y0 + 90 + (cart_y - y0 - 90) * _ease(fly) - 90 * math.sin(fly * math.pi)
                    d.ellipse((fx - 16, fy - 16, fx + 16, fy + 16), fill=col)
                if fly >= 1:
                    count += 1
            if count:
                d.ellipse((cart_x + 6, cart_y - 38, cart_x + 40, cart_y - 6), fill=RED)
                d.text((cart_x + 23, cart_y - 22), str(count), font=self.mono(20), fill=(255, 255, 255), anchor="mm")
        else:  # oversell: the last item, two buyers, with or without a lock
            fix = bool(data.get("fix"))
            nm = str(data.get("item", "Last pair of sneakers"))
            d.rounded_rectangle((250, 420, 830, 760), radius=26, fill=BOX, outline=(60, 90, 160), width=3)
            d.ellipse((440, 450, 640, 650), fill=(255, 140, 66))
            d.text((540, 700), nm, font=self.font(34), fill=INK, anchor="mm")
            stock = 1
            if t > 2.0:
                stock = 0
            if t > 2.4 and not fix:
                stock = -1
            col = GREEN if stock > 0 else AMBER if stock == 0 else RED
            d.text((540, 840), f"STOCK: {stock}", font=self.mono(44), fill=col, anchor="mm")
            for i, (nm2, col2, xo) in enumerate((("USER A", CYAN, -250), ("USER B", GREEN, 250))):
                a = _ease((t - 0.8 - i * 0.05) / 0.4)
                if a > 0:
                    d.rounded_rectangle((540 + xo - 100, 930, 540 + xo + 100, 1000), radius=16, fill=BOX, outline=col2, width=3)
                    d.text((540 + xo, 965), nm2 + ": BUY", font=self.mono(22), fill=col2, anchor="mm")
                    if 1.2 < t:
                        sx = 540 + xo * (1 - _ease((t - 1.2) / 0.8))
                        d.line((540 + xo, 930, sx, 780), fill=(*col2, 150), width=3)
            if t > 2.5:
                msg, mc = ("TWO ORDERS, ONE ITEM: OVERSOLD", RED) if not fix else ("ROW LOCK: B GETS 'OUT OF STOCK'", GREEN)
                self.chip(d, msg, 540, 1090, mc, 24, _ease((t - 2.5) / 0.4))
            if data.get("sql"):
                d.rounded_rectangle((120, 1170, 960, 1260), radius=12, fill=(10, 14, 30), outline=(60, 90, 160), width=2)
                d.text((540, 1215), str(data["sql"])[:60], font=self.mono(22), fill=GREEN, anchor="mm")
        if data.get("note"):
            self.chip(d, str(data["note"]), 540, 1420 if mode == "browse" else 1330, acc, 24, _ease((t - 1.2) / 0.4))

    # ------------------------------------------------------------------ lifecycle / pipeline with a moving token
    def d_lifecycle(self, d, img, t, dur, data, si):
        acc = self.acc
        stages = [s if isinstance(s, dict) else {"label": str(s)} for s in (data.get("stages") or [])][:6] or [
            {"label": "Placed"}, {"label": "Paid"}, {"label": "Packed"}, {"label": "Shipped"}, {"label": "Delivered"}]
        n = len(stages)
        per = 3 if n > 4 else n
        rows = (n + per - 1) // per
        fail = data.get("fail") if isinstance(data.get("fail"), dict) else None
        cells = []
        for i in range(n):
            r, c = divmod(i, per)
            x = 540 + ((c if r % 2 == 0 else per - 1 - c) - (per - 1) / 2) * (900 / max(1, per))
            y = 560 + r * 330
            cells.append((x, y))
        w = min(260, 900 / per - 40)
        rt = self.reveal_times(si, [s.get("label", "") for s in stages], 0.06, 0.55)
        t0 = max(rt) + 0.6
        prog = max(0.0, (t - t0) / 1.0)
        for i in range(n - 1):
            k = _ease((t - rt[i + 1]) / 0.4)
            if k > 0:
                (x0, y0), (x1, y1) = cells[i], cells[i + 1]
                d.line((x0, y0, x0 + (x1 - x0) * k, y0 + (y1 - y0) * k), fill=LINE, width=4)
        for i, st in enumerate(stages):
            a = _back((t - rt[i]) / 0.45)
            if a <= 0:
                continue
            x, y = cells[i]
            done = prog > i
            bad = fail and fail.get("at") == i and prog > i
            col = RED if bad else GREEN if done else acc
            s = 0.88 + 0.12 * min(1, a)
            d.rounded_rectangle((x - w * s / 2, y - 62 * s, x + w * s / 2, y + 62 * s), radius=18, fill=BOX, outline=col, width=4)
            d.text((x, y - 14), str(st.get("label", "")), font=self.font(32 if len(str(st.get("label", ""))) < 12 else 24), fill=INK, anchor="mm")
            if st.get("sub"):
                d.text((x, y + 30), str(st["sub"])[:22], font=self.mono(16), fill=MUTED, anchor="mm")
            if done and not bad:
                d.ellipse((x + w / 2 - 22, y - 70, x + w / 2 + 6, y - 42), fill=GREEN)
                d.line((x + w / 2 - 15, y - 56, x + w / 2 - 9, y - 49, x + w / 2 - 1, y - 62), fill=(8, 20, 14), width=3)
        if prog > 0:  # the order / job token
            f = min(prog, n - 1)
            if fail:
                f = min(f, fail.get("at", n - 1))
            i = min(int(f), n - 2)
            fr = f - i
            (x0, y0), (x1, y1) = cells[i], cells[min(i + 1, n - 1)]
            px, py = x0 + (x1 - x0) * fr, y0 + (y1 - y0) * fr
            d.rounded_rectangle((px - 20, py - 20 - 62, px + 20, py + 20 - 62), radius=6, fill=AMBER, outline=(255, 255, 255), width=2)
        if fail and prog > fail.get("at", 0) + 0.3:
            self.chip(d, str(fail.get("label", "FAILED: RETRY")), 540, 560 + (fail.get("at", 0) // per) * 330 + 130, RED, 24, _ease((prog - fail.get("at", 0) - 0.3) / 0.4))
        if data.get("note"):
            self.chip(d, str(data["note"]), 540, 560 + rows * 330 + 40, acc, 24, _ease((t - 1.5) / 0.4))

    # ------------------------------------------------------------------ recommendations
    def d_recsys(self, d, img, t, dur, data, si):
        acc = self.acc
        mode = data.get("mode", "embeddings")
        rnd = random.Random(8)
        if mode == "matrix":
            rows, cols = 9, 7
            x0, y0, cs = 170, 460, 110
            d.text((540, 395), "ITEMS  >", font=self.mono(22), fill=MUTED, anchor="mm")
            d.text((90, 900), "U\nS\nE\nR\nS", font=self.mono(22), fill=MUTED, anchor="mm")
            target = (4, 3)
            for r in range(rows):
                for c in range(cols):
                    x, y = x0 + c * (cs - 12) , y0 + r * (cs - 18)
                    have = rnd.random() < 0.32
                    a = _ease((t - 0.1 - (r + c) * 0.04) / 0.4)
                    if a <= 0:
                        continue
                    if (r, c) == target:
                        pulse = 0.5 + 0.5 * math.sin(t * 6)
                        d.rounded_rectangle((x - 4, y - 4, x + 80, y + 70), radius=12, outline=_mix(acc, (255, 255, 255), pulse), width=4)
                        if t > 2.2:
                            val = 4.6
                            d.rounded_rectangle((x, y, x + 76, y + 66), radius=10, fill=(*GREEN, 140))
                            d.text((x + 38, y + 33), f"{val}", font=self.mono(28), fill=INK, anchor="mm")
                        else:
                            d.text((x + 38, y + 33), "?", font=self.font(44), fill=acc, anchor="mm")
                        continue
                    if have:
                        v = rnd.choice((2, 3, 4, 5))
                        d.rounded_rectangle((x, y, x + 76, y + 66), radius=10, fill=_mix((40, 50, 110), GREEN, v / 5 * 0.8))
                        d.text((x + 38, y + 33), str(v), font=self.mono(26), fill=INK, anchor="mm")
                    else:
                        d.rounded_rectangle((x, y, x + 76, y + 66), radius=10, outline=(50, 70, 130), width=1)
            if t > 2.2:
                self.chip(d, "PREDICTED FROM SIMILAR USERS", 540, 1500, GREEN, 22, _ease((t - 2.2) / 0.4))
        elif mode == "feed":
            items = [str(x) for x in (data.get("items") or ["Item A", "Item B", "Item C", "Item D", "Item E"])][:6]
            n = len(items)
            scores = [round(0.3 + 0.12 * ((i * 7) % n) + 0.05 * i, 2) for i in range(n)]
            rank = sorted(range(n), key=lambda i: -scores[i])
            mv = _ease((t - 1.6) / 0.9)  # cards slide from their first order to the ranked order
            for i, it in enumerate(items):
                y_from, y_to = 480 + i * 150, 480 + rank.index(i) * 150
                y = y_from + (y_to - y_from) * mv
                top = rank.index(i) == 0 and mv > 0.95
                d.rounded_rectangle((90, y, 990, y + 120), radius=18, fill=BOX, outline=GREEN if top else (70, 100, 170), width=4 if top else 2)
                d.rounded_rectangle((110, y + 18, 194, y + 102), radius=12, fill=_mix((40, 50, 110), acc, 0.5))
                d.text((230, y + 60), it, font=self.font(36), fill=INK, anchor="lm")
                sc = scores[i] * _ease((t - 0.3) / 0.8)
                d.rounded_rectangle((640, y + 50, 960, y + 70), radius=10, outline=(70, 100, 170), width=2)
                d.rounded_rectangle((644, y + 54, 644 + 312 * sc, y + 66), radius=8, fill=GREEN if top else acc)
                d.text((960, y + 26), f"{sc:.2f}", font=self.mono(20), fill=MUTED, anchor="rm")
            if mv > 0.95:
                self.chip(d, "RANKED BY PREDICTED CLICK", 540, 480 + n * 150 + 30, GREEN, 22)
        else:  # embeddings: items cluster in space, the user lands among them, nearest neighbours are the recommendations
            labels = [str(x) for x in (data.get("clusters") or ["Action", "Comedy", "Romance", "Sci-fi"])][:4]
            centres = [(300, 600), (760, 560), (330, 1010), (770, 1000)]
            cols = [PINK, CYAN, AMBER, GREEN]
            pts = []
            for k, (cx, cy) in enumerate(centres[:len(labels)]):
                for j in range(15):
                    a = rnd.random() * math.tau
                    r = (rnd.random() ** 0.6) * 110
                    pts.append((cx + r * math.cos(a), cy + r * math.sin(a) * 0.8, k))
            for i, (x, y, k) in enumerate(pts):
                a = _ease((t - 0.1 - i * 0.012) / 0.4)
                if a > 0:
                    r = 8 + 3 * math.sin(t * 2 + i)
                    d.ellipse((x - r * a, y - r * a, x + r * a, y + r * a), fill=(*cols[k], 200))
            for k, lb in enumerate(labels):
                d.text((centres[k][0], centres[k][1] - 150), lb.upper(), font=self.mono(22), fill=cols[k], anchor="mm")
            ux, uy = 540, 800
            tx, ty = centres[0][0] + 40, centres[0][1] + 40
            m = _ease((t - 1.6) / 1.4)
            px, py = ux + (tx - ux) * m, uy + (ty - uy) * m
            if t > 1.0:
                d.ellipse((px - 22, py - 22, px + 22, py + 22), fill=(255, 255, 255), outline=acc, width=5)
                d.text((px, py), "U", font=self.mono(24), fill=(10, 10, 30), anchor="mm")
                self.chip(d, "USER VECTOR", px, py + 56, acc, 18)
            if t > 3.0:
                near = sorted(pts, key=lambda p: (p[0] - px) ** 2 + (p[1] - py) ** 2)[:5]
                for (x, y, k) in near:
                    d.line((px, py, x, y), fill=(*GREEN, 190), width=3)
                    d.ellipse((x - 18, y - 18, x + 18, y + 18), outline=GREEN, width=4)
                self.chip(d, "NEAREST ITEMS = RECOMMENDATIONS", 540, 1330, GREEN, 22, _ease((t - 3.0) / 0.4))
        if data.get("note"):
            self.chip(d, str(data["note"]), 540, 1580, acc, 22, _ease((t - 1.0) / 0.4))

    # ------------------------------------------------------------------ ML algorithm animations
    def d_mlviz(self, d, img, t, dur, data, si):
        acc = self.acc
        mode = data.get("mode", "gradient")
        rnd = random.Random(12)
        if mode == "gradient":
            lr = str(data.get("lr", "good"))
            L, R, T, B = 110, 970, 450, 1130
            d.rounded_rectangle((L - 20, T - 20, R + 20, B + 20), radius=16, fill=(10, 16, 40), outline=(50, 80, 150), width=2)
            pts = [(L + (R - L) * u, B - (B - T) * (1 - (2 * u - 1) ** 2) * 0.0 - (B - T) * ((2 * u - 1) ** 2) * 0.9 - 20) for u in [i / 60 for i in range(61)]]
            d.line(pts, fill=(*acc, 220), width=5)
            u = 0.12
            traj = [u]
            for _ in range(14):
                grad = 2 * (2 * u - 1) * 2
                step = {"high": 0.42, "low": 0.03}.get(lr, 0.14)
                u = u - step * grad * 0.5
                u = min(0.98, max(0.02, u))
                traj.append(u)
            f = min(len(traj) - 1.001, max(0.0, (t - 0.6) * 3.2))
            i = int(f)
            uu = traj[i] + (traj[i + 1] - traj[i]) * (f - i)
            bx = L + (R - L) * uu
            by = B - (B - T) * ((2 * uu - 1) ** 2) * 0.9 - 20
            for k in range(0, i + 1):
                bxk = L + (R - L) * traj[k]
                byk = B - (B - T) * ((2 * traj[k] - 1) ** 2) * 0.9 - 20
                d.ellipse((bxk - 6, byk - 6, bxk + 6, byk + 6), fill=(*AMBER, 120))
            d.ellipse((bx - 18, by - 18, bx + 18, by + 18), fill=AMBER, outline=(255, 255, 255), width=3)
            loss = (2 * uu - 1) ** 2
            d.text((540, 1210), f"LOSS: {loss:.3f}", font=self.mono(40), fill=GREEN if loss < 0.05 else INK, anchor="mm")
            label = {"high": "LEARNING RATE TOO HIGH: IT BOUNCES", "low": "LEARNING RATE TOO LOW: SO SLOW"}.get(lr, "GRADIENT STEP DOWNHILL")
            self.chip(d, label, 540, 1300, RED if lr in ("high", "low") else GREEN, 22)
        elif mode == "cluster":
            k = 3
            cen = [(280, 640), (780, 640), (540, 1100)]
            pts = []
            for c, (cx, cy) in enumerate(cen):
                for _ in range(22):
                    pts.append((cx + rnd.gauss(0, 90) + (60 if c == 0 else -40), cy + rnd.gauss(0, 80)))
            cents = [(300, 800), (500, 780), (700, 820)]
            hist = [cents]
            for _ in range(6):
                groups = [[] for _ in range(k)]
                for p in pts:
                    groups[min(range(k), key=lambda j: (p[0] - cents[j][0]) ** 2 + (p[1] - cents[j][1]) ** 2)].append(p)
                cents = [((sum(p[0] for p in g) / len(g)), (sum(p[1] for p in g) / len(g))) if g else cents[j] for j, g in enumerate(groups)]
                hist.append(cents)
            f = min(len(hist) - 1.001, max(0.0, (t - 0.8) / 0.9))
            i = int(f)
            cur = [(hist[i][j][0] + (hist[i + 1][j][0] - hist[i][j][0]) * (f - i), hist[i][j][1] + (hist[i + 1][j][1] - hist[i][j][1]) * (f - i)) for j in range(k)]
            cols = [PINK, CYAN, AMBER]
            for p in pts:
                j = min(range(k), key=lambda q: (p[0] - cur[q][0]) ** 2 + (p[1] - cur[q][1]) ** 2)
                d.ellipse((p[0] - 9, p[1] - 9, p[0] + 9, p[1] + 9), fill=(*cols[j], 210) if t > 0.8 else (180, 190, 220, 200))
            for j, (cx, cy) in enumerate(cur):
                pts5 = [(cx + 26 * math.sin(a * 0.4 * math.pi), cy - 26 * math.cos(a * 0.4 * math.pi)) for a in range(10)]
                d.ellipse((cx - 22, cy - 22, cx + 22, cy + 22), fill=cols[j], outline=(255, 255, 255), width=4)
                d.text((cx, cy), "C", font=self.mono(22), fill=(10, 10, 30), anchor="mm")
            d.text((540, 1330), f"ITERATION {min(int(f) + 1, len(hist) - 1)}", font=self.mono(32), fill=INK, anchor="mm")
            self.chip(d, "ASSIGN TO NEAREST CENTRE, THEN MOVE THE CENTRE", 540, 1410, acc, 20)
        elif mode == "classify":
            a_pts = [(rnd.gauss(330, 110), rnd.gauss(700, 150)) for _ in range(36)]
            b_pts = [(rnd.gauss(740, 110), rnd.gauss(950, 150)) for _ in range(36)]
            for p in a_pts:
                d.ellipse((p[0] - 10, p[1] - 10, p[0] + 10, p[1] + 10), fill=(*CYAN, 220))
            for p in b_pts:
                d.rectangle((p[0] - 10, p[1] - 10, p[0] + 10, p[1] + 10), fill=(*PINK, 220))
            f = _ease((t - 0.8) / 2.4)
            ang = math.radians(10 + (-40 - 10) * 0) + (1 - f) * math.radians(70)
            mx, my = 540 + (1 - f) * 200, 820 - (1 - f) * 160
            ln = 900
            d.line((mx - math.cos(ang) * ln, my - math.sin(ang) * ln, mx + math.cos(ang) * ln, my + math.sin(ang) * ln), fill=acc, width=6)
            acc_v = 0.52 + 0.46 * f
            d.text((540, 1330), f"ACCURACY: {acc_v * 100:.0f}%", font=self.mono(40), fill=GREEN if f > 0.9 else INK, anchor="mm")
            self.chip(d, "A LINE THAT SEPARATES THE TWO CLASSES", 540, 1410, acc, 20)
        elif mode == "nn":
            sizes = [int(x) for x in (data.get("layers") or [4, 6, 6, 3])][:5]
            xs = [150 + i * (780 / (len(sizes) - 1)) for i in range(len(sizes))]
            nodes = []
            for li, m in enumerate(sizes):
                nodes.append([(xs[li], 840 + (j - (m - 1) / 2) * 110) for j in range(m)])
            for li in range(len(sizes) - 1):
                for a in nodes[li]:
                    for b in nodes[li + 1]:
                        d.line((a[0], a[1], b[0], b[1]), fill=(70, 100, 190, 70), width=1)
            wave = (t - 0.6) * 1.6
            for li, layer in enumerate(nodes):
                for j, (x, y) in enumerate(layer):
                    on = max(0.0, 1 - abs(wave - li) * 1.2)
                    col = _mix((30, 50, 110), acc, on)
                    d.ellipse((x - 26, y - 26, x + 26, y + 26), fill=col, outline=(150, 180, 240), width=2)
            names = [str(x) for x in (data.get("names") or ["INPUT", "HIDDEN", "HIDDEN", "OUTPUT"])]
            for li, nm in enumerate(names[:len(sizes)]):
                d.text((xs[li], 400), nm, font=self.mono(20), fill=MUTED, anchor="mm")
            if wave > len(sizes) - 1:
                outs = nodes[-1]
                best = int(t * 1.7) % len(outs)
                for j, (x, y) in enumerate(outs):
                    d.text((x + 70, y), f"{0.7 if j == 0 else 0.15:.2f}", font=self.mono(22), fill=GREEN if j == 0 else MUTED, anchor="mm")
            self.chip(d, "FORWARD PASS: INPUT > HIDDEN > OUTPUT", 540, 1450, acc, 20)
        elif mode == "tree":
            root = (540, 480)
            lv1 = [(300, 800), (780, 800)]
            lv2 = [(170, 1130), (430, 1130), (650, 1130), (910, 1130)]
            splits = [str(x) for x in (data.get("splits") or ["Income > 50k?", "Age > 30?", "Owns house?"])]
            rt = [0.2, 0.9, 1.5, 2.1]
            def node(p, txt, a, leaf=False, col=acc):
                if a <= 0:
                    return
                w, h = (200, 70) if not leaf else (150, 70)
                d.rounded_rectangle((p[0] - w / 2, p[1] - h / 2, p[0] + w / 2, p[1] + h / 2), radius=14, fill=BOX, outline=col, width=3)
                d.text((p[0], p[1]), txt, font=self.mono(18), fill=INK, anchor="mm")
            for a_, b_, r in ((root, lv1[0], 0.9), (root, lv1[1], 0.9), (lv1[0], lv2[0], 1.5), (lv1[0], lv2[1], 1.5), (lv1[1], lv2[2], 2.1), (lv1[1], lv2[3], 2.1)):
                k = _ease((t - r) / 0.5)
                if k > 0:
                    d.line((a_[0], a_[1] + 35, a_[0] + (b_[0] - a_[0]) * k, a_[1] + 35 + (b_[1] - 35 - a_[1] - 35) * k), fill=LINE, width=3)
            node(root, splits[0], _ease((t - rt[0]) / 0.4))
            node(lv1[0], splits[1 % len(splits)], _ease((t - rt[1]) / 0.4))
            node(lv1[1], splits[2 % len(splits)], _ease((t - rt[1]) / 0.4))
            for i, p in enumerate(lv2):
                node(p, ("YES" if i in (0, 3) else "NO"), _ease((t - rt[2 + i // 2]) / 0.4), True, GREEN if i in (0, 3) else RED)
            if t > 2.8:  # a sample drops down the tree
                f = min(1.0, (t - 2.8) / 2.0)
                path = [root, lv1[1], lv2[3]]
                seg = min(1, int(f * 2))
                fr = f * 2 - seg
                a_, b_ = path[seg], path[seg + 1]
                d.ellipse((a_[0] + (b_[0] - a_[0]) * fr - 14, a_[1] + (b_[1] - a_[1]) * fr - 14, a_[0] + (b_[0] - a_[0]) * fr + 14, a_[1] + (b_[1] - a_[1]) * fr + 14), fill=AMBER, outline=(255, 255, 255), width=3)
        else:  # attention
            toks = [str(x) for x in (data.get("tokens") or ["The", "cat", "sat", "on", "the", "mat"])][:8]
            n = len(toks)
            xs = [90 + i * (900 / max(1, n - 1)) for i in range(n)]
            y = 1000
            focus = int((t - 0.6) / 1.2) % n if t > 0.6 else n - 1
            for i, tk in enumerate(toks):
                d.rounded_rectangle((xs[i] - 52, y - 30, xs[i] + 52, y + 30), radius=12, fill=BOX, outline=acc if i == focus else (70, 100, 170), width=4 if i == focus else 2)
                d.text((xs[i], y), tk, font=self.mono(22), fill=INK, anchor="mm")
            wts = [abs(math.sin(focus * 1.7 + i * 2.3)) ** 2 for i in range(n)]
            tot = sum(wts) or 1
            for i in range(n):
                if i == focus:
                    continue
                w = wts[i] / tot
                mid = (xs[i] + xs[focus]) / 2
                hgt = 80 + abs(xs[i] - xs[focus]) * 0.5
                pts = [(xs[focus] + (xs[i] - xs[focus]) * u, y - 34 - hgt * 4 * u * (1 - u)) for u in [k / 18 for k in range(19)]]
                d.line(pts, fill=(*acc, int(60 + 190 * min(1, w * 2.2))), width=max(2, int(w * 40)))
            d.text((540, 1180), "EACH WORD LOOKS AT THE OTHERS, WEIGHTED BY RELEVANCE", font=self.mono(20), fill=MUTED, anchor="mm")
        if data.get("note"):
            self.chip(d, str(data["note"]), 540, 1560, acc, 22, _ease((t - 1.2) / 0.4))
