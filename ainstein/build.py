"""Entry point: read config, gather, rank, rewrite, write data/feed.json.

    python -m ainstein.build --days 3
    python -m ainstein.build --days 3 --no-ai     # plumbing only, no API cost
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .images import localize
from . import pictures
from .link import annotate, link
from .route import route
from .models import Item, Policy
from .score import rank
from .sources import arxiv, buzz, crossref, feeds, youtube
from .rewrite import rewrite_all

ROOT = Path(__file__).resolve().parent.parent


def load_config(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def gather(cfg: dict, days: int) -> list[Item]:
    items: list[Item] = []

    print("arXiv…")
    items += arxiv.fetch(cfg["arxiv"]["categories"], days=days)

    print("Crossref…")
    items += crossref.fetch(cfg["crossref"]["journals"], days=days)

    print("Feeds…")
    items += feeds.fetch(cfg["feeds"], days=days)

    print("YouTube…")
    items += youtube.fetch(cfg.get("youtube", []), days=days)

    print("Buzz…")
    b = cfg.get("buzz", {})
    trending = buzz.hacker_news(days=b.get("days", 7), min_points=b.get("hn_min_points", 150))
    items += buzz.merge_buzz(items, trending)   # boosts what we have, adds what we don't

    print(f"gathered {len(items)} items")
    return items


def build(days: int, use_ai: bool, cfg_path: Path) -> dict:
    cfg = load_config(cfg_path)
    items = gather(cfg, days)

    # Domain first: ranking is per-track, so an item has to know its tab
    # before it can compete for a place on it.
    items, unrouted = route(items, cfg["tracks"])
    if unrouted:
        print(f"unrouted (dropped): {len(unrouted)} — "
              f"e.g. {unrouted[0].title[:60]!r}")

    top = rank(items, cfg["interests"], per_track=cfg["limits"]["per_track"])
    print(f"kept {len(top)}")

    if use_ai:
        from anthropic import Anthropic
        client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        print("rewriting…")
        rewrite_all(top, client)

    # Anything that should have become a card but didn't gets dropped, so the
    # feed never shows a half-built item.
    cards = [
        i for i in top
        if i.policy is Policy.HEADLINE_ONLY or i.hook or not use_ai
    ]

    # Only what made the cut gets its image fetched — a few dozen, not hundreds.
    pic_opts = cfg.get("pictures", {})
    if pic_opts.get("enabled", True):
        pictures.find(cards, cfg["feeds"], pic_opts)
    try:
        localize(cards, ROOT / "data" / "img")
    except ImportError:
        print("  ! images skipped: pip install Pillow")

    # Attach the pulse to the inventory: which entity is each card about?
    by_entity = link(cards, cfg["entities"])
    directory = annotate(cfg["entities"], by_entity, cards)
    # A directory entry people are suddenly looking up is news in itself.
    attention = buzz.wikipedia_attention(cfg["entities"]) if cfg.get("buzz", {}).get("wikipedia", True) else {}
    for e in directory:
        if e["id"] in attention:
            e["trending_views"] = attention[e["id"]]
    linked = sum(1 for e in directory if e["item_ids"])
    print(f"linked items to {linked}/{len(directory)} directory entries")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tracks": [{k: v for k, v in t.items() if k != "match"} for t in cfg["tracks"]],
        "entities": directory,
        # Hand-maintained layers: the canon doesn't change with the news,
        # and the watch list is where to start when a paper is the wrong
        # first step.
        "canon": sorted(cfg.get("canon", []), key=lambda c: -c.get("sort", 0)),
        "watch": cfg.get("watch", []),
        "books": cfg.get("books", []),
        "items": [i.to_json() for i in cards],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--no-ai", action="store_true", help="skip the rewrite step")
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--out", default=str(ROOT / "data" / "feed.json"))
    args = ap.parse_args()

    feed = build(args.days, not args.no_ai, Path(args.config))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(feed, fh, ensure_ascii=False, indent=2)
    print(f"wrote {out} — {len(feed['items'])} items")


if __name__ == "__main__":
    main()
