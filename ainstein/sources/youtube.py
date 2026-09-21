"""YouTube — the explainer channels, via each channel's public Atom feed.

    https://www.youtube.com/feeds/videos.xml?channel_id=UC...

Policy is always HEADLINE_ONLY, and not by accident. A video's title and
link are a reference; its description and transcript are the creator's work,
and summarising a twenty-minute explainer into a card would be building a
substitute for it rather than a pointer to it. So a video appears as a title,
a channel, a date and a link — the thing that sends viewers *to* the creator.

Thumbnails are the creator's images too, and hotlinking them makes this page
a display surface for someone else's art, so we don't take those either.

Channel IDs live in config.yaml. If you only have a handle, tools/resolve_youtube.py
turns @handle into the UC... id.
"""

from __future__ import annotations

import time
import urllib.request
from datetime import datetime, timedelta, timezone

import feedparser

from ..models import Item, Policy

FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
UA = "AInstein/0.3 (https://github.com/AyaRudek/ainstein; personal science feed)"
RATE_LIMIT_S = 1.0


def fetch_channel(channel: dict, days: int) -> list[Item]:
    """channel: {name, channel_id, track}"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    req = urllib.request.Request(
        FEED.format(channel_id=channel["channel_id"]),
        headers={"User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        parsed = feedparser.parse(resp.read())

    items: list[Item] = []
    for e in parsed.entries:
        stamp = getattr(e, "published_parsed", None)
        published = datetime(*stamp[:6], tzinfo=timezone.utc) if stamp else None
        if not published or published < cutoff:
            continue
        items.append(Item(
            id=f"yt:{getattr(e, 'yt_videoid', e.link)}",
            title=" ".join(e.title.split()),
            url=e.link,
            published=published.isoformat(),
            source=channel["name"],
            policy=Policy.HEADLINE_ONLY,   # never anything but this
            track=channel.get("track", "auto"),
            license="YouTube video — title and link only, no description or transcript",
            media="video",
        ))
    return items


def fetch(channels: list[dict], days: int) -> list[Item]:
    out: list[Item] = []
    for channel in channels:
        if not channel.get("channel_id"):
            print(f"  ! {channel['name']}: no channel_id — run tools/resolve_youtube.py")
            continue
        try:
            got = fetch_channel(channel, days)
            print(f"  · {channel['name']}: {len(got)} videos")
            out.extend(got)
        except Exception as exc:
            print(f"  ! {channel['name']} skipped: {exc}")
        time.sleep(RATE_LIMIT_S)
    return out
