"""The taste layer: decide what is worth a card today.

This is the part worth tuning. Everything else is plumbing.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone

from .models import Item, Policy

PENALTY_TERMS = {
    "erratum": -12, "corrigendum": -12, "comment on": -8, "reply to": -8,
    "a note on": -4, "lecture notes": -6, "book review": -8,
    "editorial": -5, "obituary": -8,
}

RESULT_RE = re.compile(r"\bwe (report|detect|measure|find|observe|present the first)\b", re.I)
FIRST_RE = re.compile(r"\bfirst (detection|measurement|observation|evidence|light)\b", re.I)


def score(item: Item, interests: dict[str, int]) -> float:
    text = f"{item.title} {item.abstract}".lower()
    s = 0.0

    for term, weight in interests.items():
        if term.lower() in text:
            s += weight
    for term, weight in PENALTY_TERMS.items():
        if term in text:
            s += weight

    if RESULT_RE.search(text):
        s += 2
    if FIRST_RE.search(text):
        s += 3

    # Peer review is a real signal — that was the whole point of the Crossref source.
    if item.venue:
        s += 4
    # A headline with no abstract can still be worth showing, but it competes weakly.
    if item.policy is Policy.HEADLINE_ONLY:
        s -= 1
    elif len(item.abstract) < 400:
        s -= 2

    # Attention matters, on a log scale: 1,000 points is worth more than 100,
    # but not ten times more, and nothing trends its way past a real result.
    if item.buzz:
        s += min(8.0, 2.5 * math.log10(1 + item.buzz))

    # Deadlines beat freshness: an opportunity closing soon goes to the top.
    if item.deadline:
        s += 5

    age_h = (datetime.now(timezone.utc)
             - datetime.fromisoformat(item.published)).total_seconds() / 3600
    s += max(0.0, 3.0 - age_h / 24)

    item.score = s
    return s


def rank(items: list[Item], interests: dict[str, int],
         per_track: int, per_source_cap: int = 4) -> list[Item]:
    """Top N per track, with a cap per source so one loud feed can't own a tab."""
    for it in items:
        score(it, interests)
    items.sort(key=lambda i: i.score, reverse=True)

    picked: list[Item] = []
    track_count: dict[str, int] = {}
    source_count: dict[tuple[str, str], int] = {}

    for it in items:
        if track_count.get(it.track, 0) >= per_track:
            continue
        key = (it.track, it.source)
        if source_count.get(key, 0) >= per_source_cap:
            continue
        track_count[it.track] = track_count.get(it.track, 0) + 1
        source_count[key] = source_count.get(key, 0) + 1
        picked.append(it)

    return picked
