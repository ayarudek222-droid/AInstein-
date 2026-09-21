"""Decide which domain an item belongs to.

"Papers" was never a subject — it described where something came from, which
is the pipeline's business and not the reader's. A preprint about a pulsar
and a NASA release about the same pulsar belong on the same tab.

So a feed may declare its own track (a press room knows its subject), and
everything else is routed here by what it is about:

  1. category prefix   precise — arXiv's own taxonomy does the work
  2. keywords          fuzzy — for sources without categories
  3. nothing matched   the item is dropped and counted, never filed at random
"""

from __future__ import annotations

import re

from .models import Item


def _category_track(categories: list[str], tracks: list[dict]) -> str | None:
    for track in tracks:
        prefixes = (track.get("match") or {}).get("categories") or []
        for cat in categories:
            for prefix in prefixes:
                if cat == prefix or cat.startswith(prefix + "."):
                    return track["id"]
    return None


def _keyword_track(text: str, tracks: list[dict]) -> str | None:
    best, best_score = None, 0
    for track in tracks:
        words = (track.get("match") or {}).get("keywords") or []
        score = sum(1 for w in words if re.search(r"\b" + re.escape(w), text))
        if score > best_score:
            best, best_score = track["id"], score
    return best


def route(items: list[Item], tracks: list[dict]) -> tuple[list[Item], list[Item]]:
    """Return (routed, unrouted). Items keep a track a feed already gave them."""
    feed_tracks = {t["id"] for t in tracks}
    routed: list[Item] = []
    unrouted: list[Item] = []

    for item in items:
        # A feed that declared a real track keeps it.
        if item.track in feed_tracks and item.track != "auto":
            routed.append(item)
            continue

        track = _category_track(item.categories, tracks)
        if not track:
            # Everything we legitimately hold about the item, not just the
            # title: a rewritten card has no raw abstract left, and routing
            # on a headline alone is how a launch-contract story ends up
            # filed under astrophysics.
            haystack = " ".join(filter(None, [
                item.title, item.abstract, item.hook, item.body, item.why, item.source,
            ])).lower()
            track = _keyword_track(haystack, tracks)

        # A press room we trust gets a safety net: NASA covers both the
        # science and the industry, and an item of theirs that matches
        # neither vocabulary should not vanish.
        if not track and item.fallback_track in feed_tracks:
            track = item.fallback_track

        if track:
            item.track = track
            routed.append(item)
        else:
            unrouted.append(item)

    return routed, unrouted
