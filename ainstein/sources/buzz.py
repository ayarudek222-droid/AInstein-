"""Buzz — what people are actually paying attention to.

A feed built only from publication date ranks a routine preprint above the
story everyone is arguing about. This module measures attention and hands
it to the scorer; it never decides what is *true*, only what is *loud*.

Sources
-------
Hacker News, through Algolia's public search API. Free, no key, and it
tells you what a technical audience upvoted in the last N days. It is
mostly technology rather than science, so nothing here is kept on buzz
alone: a trending story only enters the feed if route() can place it in
one of the configured domains. The domain router doubles as the science
filter.

    https://hn.algolia.com/api

Wikipedia's most-viewed articles (Wikimedia REST API). Used differently:
not as items, but to notice when an entry in the directory is suddenly
being looked up — "LUX-ZEPLIN" spiking is a signal about the LZ card.

    https://wikimedia.org/api/rest_v1/

Licensing: a trending story is a title and a link to its publisher, and
is always HEADLINE_ONLY. We link the Hacker News thread as well, because
the discussion is often the most useful thing there.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from ..models import Item, Policy

UA = "AInstein/0.4 (https://github.com/AyaRudek/ainstein; personal science feed)"
HN = "https://hn.algolia.com/api/v1/search"
WIKI_TOP = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/{y}/{m:02d}/{d:02d}"


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def normalise_url(u: str) -> str:
    """Compare URLs by what they point at, not how they were written."""
    u = (u or "").strip().lower()
    u = re.sub(r"^https?://(www\.)?", "", u)
    u = re.sub(r"[?#].*$", "", u)
    return u.rstrip("/")


def hacker_news(days: int = 7, min_points: int = 150, limit: int = 200) -> list[Item]:
    since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    params = urllib.parse.urlencode({
        "tags": "story",
        "numericFilters": f"created_at_i>{since},points>{min_points}",
        "hitsPerPage": limit,
    })
    try:
        hits = _get_json(f"{HN}?{params}").get("hits", [])
    except Exception as exc:
        print(f"  ! hacker news skipped: {exc}")
        return []

    out: list[Item] = []
    for h in hits:
        url, title = h.get("url"), (h.get("title") or "").strip()
        if not url or not title or title.lower().startswith(("ask hn", "tell hn")):
            continue
        host = urllib.parse.urlparse(url).netloc.replace("www.", "")
        points, comments = int(h.get("points") or 0), int(h.get("num_comments") or 0)
        out.append(Item(
            id=f"hn:{h['objectID']}",
            title=title,
            url=url,
            published=h.get("created_at") or datetime.now(timezone.utc).isoformat(),
            source=host,
            policy=Policy.HEADLINE_ONLY,
            track="auto",
            license="Publisher's headline and link only; ranked by Hacker News attention",
            buzz=points + comments,
            buzz_note=f"{points} points · {comments} comments on Hacker News",
            discuss_url=f"https://news.ycombinator.com/item?id={h['objectID']}",
        ))
    print(f"  · hacker news: {len(out)} stories over {min_points} points")
    return out


def merge_buzz(items: list[Item], trending: list[Item]) -> list[Item]:
    """A trending story we already have boosts that item instead of duplicating it.
    Returns only the trending stories that are genuinely new."""
    by_url = {normalise_url(i.url): i for i in items if i.url}
    fresh: list[Item] = []
    for t in trending:
        hit = by_url.get(normalise_url(t.url))
        if hit:
            hit.buzz = max(hit.buzz, t.buzz)
            hit.buzz_note = t.buzz_note
            hit.discuss_url = t.discuss_url
        else:
            fresh.append(t)
    return fresh


def wikipedia_attention(entities: list[dict], days_back: int = 1, top_n: int = 1000) -> dict[str, int]:
    """{entity_id: daily views} for directory entries among Wikipedia's most-read articles."""
    when = datetime.now(timezone.utc) - timedelta(days=days_back)
    try:
        payload = _get_json(WIKI_TOP.format(y=when.year, m=when.month, d=when.day))
        articles = payload["items"][0]["articles"][:top_n]
    except Exception as exc:
        print(f"  ! wikipedia pageviews skipped: {exc}")
        return {}
    views = {a["article"].replace("_", " ").lower(): int(a["views"]) for a in articles}
    out: dict[str, int] = {}
    for e in entities:
        for name in (e.get("name"), e.get("full_name")):
            if name and name.lower() in views:
                out[e["id"]] = max(out.get(e["id"], 0), views[name.lower()])
    time.sleep(0.5)
    if out:
        print(f"  · wikipedia: {len(out)} directory entries trending")
    return out
