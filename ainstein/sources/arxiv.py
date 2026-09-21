"""arXiv — preprints, via the public Atom API.

Terms: arXiv provides this API for exactly this kind of use. Metadata is
CC0; abstracts are served by the API for reuse with attribution. We link to
the abstract page, never mirror the PDF.
https://info.arxiv.org/help/api/tou.html
"""

from __future__ import annotations

import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import feedparser

from ..models import Item, Policy

API = "http://export.arxiv.org/api/query"
UA = "AInstein/0.2 (https://github.com/AyaRudek/ainstein; personal science feed)"
RATE_LIMIT_S = 3.0  # arXiv asks for one request per three seconds


def fetch(categories: list[str], days: int, per_cat: int = 60) -> list[Item]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    out: dict[str, Item] = {}

    for cat in categories:
        params = urllib.parse.urlencode({
            "search_query": f"cat:{cat}",
            "start": 0,
            "max_results": per_cat,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        })
        req = urllib.request.Request(f"{API}?{params}", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            feed = feedparser.parse(resp.read())

        for e in feed.entries:
            published = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
            if published < cutoff:
                continue
            arxiv_id = e.id.rsplit("/", 1)[-1]
            if arxiv_id in out:
                continue
            authors = [a.name for a in getattr(e, "authors", [])]
            out[arxiv_id] = Item(
                id=f"arxiv:{arxiv_id}",
                title=" ".join(e.title.split()),
                url=e.link,
                published=published.isoformat(),
                source="arXiv",
                policy=Policy.ABSTRACT_OK,
                track="papers",
                license="arXiv API terms; metadata CC0",
                authors=authors[:3],
                n_authors=len(authors),
                abstract=" ".join(e.summary.split()),
                categories=[t["term"] for t in getattr(e, "tags", [])],
            )
        time.sleep(RATE_LIMIT_S)

    return list(out.values())
