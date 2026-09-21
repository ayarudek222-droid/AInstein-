"""RSS/Atom sources: agency press rooms and opportunity boards.

Each feed carries its own policy, set in config.yaml:

  abstract_ok    NASA (largely public domain), ESA (CC BY-SA 3.0 IGO),
                 CERN (CC-BY 4.0) — official releases, written to be spread.
  headline_only  magazines and anything commercially published. Title, date
                 and link only; the summary text is discarded on arrival so
                 it cannot reach the LLM or the published feed.

A feed that stops being valid XML (a redirect to an HTML page, a CDN error
page) is skipped loudly rather than parsed into nonsense.
"""

from __future__ import annotations

import re
import urllib.request
from datetime import datetime, timedelta, timezone

import feedparser

from ..images import allowed, find_image_url
from ..models import Item, Policy

UA = "AInstein/0.2 (https://github.com/AyaRudek/ainstein; personal science feed)"

# deadline phrasing seen on ESA / NASA / EU opportunity postings
DEADLINE_RE = re.compile(
    r"(?:deadline|closing date|applications? close|apply by|submissions? due)"
    r"[^\n\r]{0,40}?(\d{1,2}\s+\w+\s+\d{4}|\d{4}-\d{2}-\d{2})",
    re.I,
)


def _clean(html: str, limit: int = 1400) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return " ".join(text.split())[:limit]


def fetch_one(spec: dict, days: int) -> list[Item]:
    """spec: {name, url, policy, track, license}"""
    policy = Policy(spec["policy"])
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    req = urllib.request.Request(spec["url"], headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()

    head = raw[:400].lstrip()
    if not head.startswith(b"<?xml") and b"<rss" not in head and b"<feed" not in head:
        raise ValueError(f"{spec['name']}: not an XML feed (got {head[:60]!r})")

    parsed = feedparser.parse(raw)
    items: list[Item] = []

    for e in parsed.entries:
        stamp = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
        published = datetime(*stamp[:6], tzinfo=timezone.utc) if stamp else datetime.now(timezone.utc)
        if published < cutoff:
            continue

        summary = _clean(getattr(e, "summary", ""))

        # Images are a separate licence question from text. Look for one only
        # where the source's terms cover images, and before any text is dropped.
        image_url = ""
        if spec.get("images"):
            candidate = find_image_url(e)
            if candidate and allowed(candidate, e.title, spec.get("image_skip", [])):
                image_url = candidate
        deadline = None
        if spec["track"] == "opportunities":
            m = DEADLINE_RE.search(summary)
            deadline = m.group(1) if m else None

        items.append(Item(
            id=f"{spec['name'].lower().replace(' ', '-')}:{getattr(e, 'id', e.link)}",
            title=" ".join(e.title.split()),
            url=e.link,
            published=published.isoformat(),
            source=spec["name"],
            policy=policy,
            track=spec["track"],
            fallback_track=spec.get("fallback_track", ""),
            license=spec.get("license", ""),
            # HEADLINE_ONLY: drop the text here, at the boundary. Nothing
            # downstream ever sees it.
            abstract=summary if policy is Policy.ABSTRACT_OK else "",
            deadline=deadline,
            categories=[t.get("term", "") for t in getattr(e, "tags", [])][:3],
            image_url=image_url,
            image_credit=spec.get("image_credit", "") if image_url else "",
        ))

    return items


def fetch(specs: list[dict], days: int) -> list[Item]:
    out: list[Item] = []
    for spec in specs:
        try:
            got = fetch_one(spec, days)
            print(f"  · {spec['name']}: {len(got)} items")
            out.extend(got)
        except Exception as exc:
            print(f"  ! {spec['name']} skipped: {exc}")
    return out
