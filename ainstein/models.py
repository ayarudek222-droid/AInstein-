"""Core data types, and the licensing policy that governs them."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class Policy(str, Enum):
    """How much of a source we are allowed to process and republish.

    This is the single most important decision in the project. Every source
    declares one, and the pipeline refuses to treat an item more permissively
    than its source allows. See SOURCES.md for the reasoning per source.
    """

    #: Open licence or explicit API terms. We may send the abstract/summary to
    #: an LLM, publish our own rewritten card, and store the abstract.
    ABSTRACT_OK = "abstract_ok"

    #: Copyrighted editorial content (magazines, most journals). We store and
    #: display the headline, date and link ONLY. No full text is fetched, no
    #: LLM rewriting, nothing derivative is published.
    HEADLINE_ONLY = "headline_only"


@dataclass
class Item:
    """One thing that happened: a paper, a press release, an opportunity."""

    id: str
    title: str
    url: str
    published: str                  # ISO 8601
    source: str                     # "arXiv", "NASA", "ESA", ...
    policy: Policy
    track: str                      # a domain id from config.yaml, or "auto" to be routed
    fallback_track: str = ""        # where a trusted feed's item lands if routing finds nothing
    license: str = ""               # what the source says, verbatim-ish
    authors: list[str] = field(default_factory=list)
    n_authors: int = 0
    abstract: str = ""              # empty when policy is HEADLINE_ONLY
    categories: list[str] = field(default_factory=list)
    venue: str = ""                 # journal name, when peer-reviewed
    media: str = "article"          # article | video
    deadline: Optional[str] = None  # opportunities only
    entities: list[str] = field(default_factory=list)  # filled by link.py
    buzz: int = 0                   # attention: HN points + comments, etc.
    buzz_note: str = ""             # human-readable, e.g. "632 points on Hacker News"
    discuss_url: str = ""           # where the conversation is happening
    image_url: str = ""             # the source's own image, only where its licence covers images
    image: str = ""                 # our resized copy, served from this repository
    image_credit: str = ""          # the credit line that licence requires
    score: float = 0.0

    # filled by the rewrite step, only ever for ABSTRACT_OK items
    hook: str = ""
    body: str = ""
    why: str = ""
    tags: list[str] = field(default_factory=list)
    jargon: dict = field(default_factory=dict)
    points: list = field(default_factory=list)   # 3 short key points, the gist at a glance
    confidence: str = ""

    @property
    def may_rewrite(self) -> bool:
        return self.policy is Policy.ABSTRACT_OK and bool(self.abstract)

    def to_json(self) -> dict:
        d = asdict(self)
        d["policy"] = self.policy.value
        d.pop("score", None)
        if self.policy is Policy.HEADLINE_ONLY:
            # belt and braces: never let an abstract leak into the published feed
            d["abstract"] = ""
        return d


@dataclass
class Entity:
    """An entry in the standing directory (the 'inventory' layer).

    Every track gets one, not just particle physics: a detector, a flying
    mission, a company building the next launcher, a project assembling a
    dataset. `kind` is what changes how an entry reads.

    These change rarely and are maintained by hand in config.yaml — they are
    facts (name, location, what it does), not anyone's prose.
    """

    id: str
    name: str
    full_name: str
    track: str                      # which tab it belongs to
    kind: str                       # experiment | mission | company | project | lab
    org: str                        # who runs it
    location: str
    country: str
    does: str
    status: str                     # "taking data" | "flying" | "in development" | ...
    since: str
    keywords: list[str] = field(default_factory=list)
    url: str = ""
