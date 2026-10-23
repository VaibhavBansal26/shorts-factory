"""Fetch fresh articles/papers from the configured feeds and pick the best unused ones."""
import calendar
import html
import math
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from html.parser import HTMLParser

import feedparser
import requests

from . import db

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
}


@dataclass
class Item:
    url: str
    title: str
    summary: str
    source: str
    kind: str  # blog | paper
    published: float
    weight: float = 1.0
    text: str = ""
    score: float = 0.0


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self._skip, self._in_p = [], 0, False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "header", "aside"):
            self._skip += 1
        if tag in ("p", "li", "h1", "h2", "h3"):
            self._in_p = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "header", "aside"):
            self._skip = max(0, self._skip - 1)
        if tag in ("p", "li", "h1", "h2", "h3"):
            self._in_p = False
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip and self._in_p:
            self.parts.append(data)


def html_to_text(raw: str) -> str:
    p = _Text()
    try:
        p.feed(raw)
    except Exception:
        return re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape("".join(p.parts))
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", text)).strip()


def _fetch_feed(src: dict) -> list[Item]:
    try:
        r = requests.get(src["url"], headers=HEADERS, timeout=25)
        r.raise_for_status()
        feed = feedparser.parse(r.content)
    except Exception as e:
        print(f"  ! {src['name']}: {e}")
        return []
    items = []
    for e in feed.entries:
        url = e.get("link")
        if not url:
            continue
        body = ""
        if e.get("content"):
            body = html_to_text(e.content[0].get("value", ""))
        summary = html_to_text(e.get("summary", "")) or body
        ts = e.get("published_parsed") or e.get("updated_parsed")
        items.append(
            Item(
                url=url.split("?")[0] if src["kind"] == "blog" else url,
                title=html.unescape(re.sub(r"\s+", " ", e.get("title", "")).strip()),
                summary=summary[:1500],
                source=src["name"],
                kind=src["kind"],
                published=calendar.timegm(ts) if ts else time.time(),
                weight=src.get("weight", 1.0),
                text=body[:6000],
            )
        )
    print(f"  {src['name']}: {len(items)} items")
    return items


def fetch_article_text(item: Item) -> str:
    """Enrich a blog item with the article body when the feed only had a teaser."""
    if len(item.text) > 1200 or item.kind == "paper":
        return item.text or item.summary
    try:
        r = requests.get(item.url, headers=HEADERS, timeout=25)
        r.raise_for_status()
        text = html_to_text(r.text)
        if len(text) > len(item.text):
            item.text = text[:6000]
    except Exception:
        pass
    return item.text or item.summary


def _score(item: Item, sel: dict) -> float:
    blob = f"{item.title} {item.summary}".lower()
    if any(x in blob for x in sel.get("exclude", [])):
        return -1
    hits = sum(1 for k in sel.get("keywords", []) if k in blob)
    age_days = max(0, (time.time() - item.published) / 86400)
    if age_days > sel.get("max_age_days", 14):
        return -1
    recency = math.exp(-age_days / 5)
    return item.weight * (1 + 0.6 * min(hits, 5)) * (0.4 + recency)


def collect(cfg: dict) -> list[Item]:
    print("Fetching sources…")
    with ThreadPoolExecutor(8) as ex:
        batches = list(ex.map(_fetch_feed, cfg["sources"]))
    seen, out = set(), []
    for batch in batches:
        for it in batch:
            if it.url not in seen:
                seen.add(it.url)
                out.append(it)
    return out


def ranked(cfg: dict, n: int = 20) -> list[Item]:
    """Top-scoring unused items, no random sampling (for the UI's 'fresh from your sources' list)."""
    sel = cfg["selection"]
    con = db.connect()
    items = [i for i in collect(cfg) if not db.is_used(con, i.url)]
    for i in items:
        i.score = _score(i, sel)
    return sorted((i for i in items if i.score > 0), key=lambda i: -i.score)[:n]


def pick(cfg: dict, n: int = 1, source_filter: str | None = None) -> list[Item]:
    sel = cfg["selection"]
    con = db.connect()
    items = [i for i in collect(cfg) if not db.is_used(con, i.url)]
    if source_filter:
        items = [i for i in items if source_filter.lower() in i.source.lower()]
    for i in items:
        i.score = _score(i, sel)
    items = sorted((i for i in items if i.score > 0), key=lambda i: -i.score)
    pool = items[: sel.get("candidates_per_run", 30)]
    # weighted sample so a channel doesn't always show the same top source
    chosen, pool = [], pool[:]
    while pool and len(chosen) < n:
        pick_ = random.choices(pool, weights=[p.score for p in pool])[0]
        chosen.append(pick_)
        pool.remove(pick_)
    return chosen
