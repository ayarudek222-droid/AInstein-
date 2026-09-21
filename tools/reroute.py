"""Re-run routing and linking over an existing data/feed.json, without refetching.

The network step is the slow part, so this is the loop you want while tuning
config.yaml's `match` rules, ainstein/route.py or ainstein/link.py.

    python tools/reroute.py
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml                                      # noqa: E402

from ainstein.link import annotate, link         # noqa: E402
from ainstein.models import Item, Policy         # noqa: E402
from ainstein.route import route                 # noqa: E402

cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
path = ROOT / "data" / "feed.json"
feed = json.loads(path.read_text(encoding="utf-8"))

items = [Item(
    id=d["id"], title=d.get("title", ""), url=d.get("url", ""),
    published=d["published"].replace("Z", "+00:00"), source=d.get("source", ""),
    policy=Policy(d["policy"]), track=d.get("track", "auto"),
    abstract=d.get("abstract", ""), hook=d.get("hook", ""), body=d.get("body", ""), why=d.get("why", ""),
    categories=d.get("categories", []), venue=d.get("venue", ""),
    fallback_track=d.get("fallback_track", ""),
) for d in feed["items"]]

routed, unrouted = route(items, cfg["tracks"])
for i in unrouted:
    print(f"  dropped (no domain): {i.title[:70]}")

by_entity = link(routed, cfg["entities"])
feed["tracks"] = [{k: v for k, v in t.items() if k != "match"} for t in cfg["tracks"]]
feed["entities"] = annotate(cfg["entities"], by_entity, routed)
feed["canon"] = sorted(cfg.get("canon", []), key=lambda c: -c.get("sort", 0))
feed["watch"] = cfg.get("watch", [])
feed["books"] = cfg.get("books", [])

kept = {i.id: i for i in routed}
out = []
for d in feed["items"]:
    if d["id"] not in kept:
        continue
    d["track"] = kept[d["id"]].track
    d["entities"] = kept[d["id"]].entities
    out.append(d)
feed["items"] = out

path.write_text(json.dumps(feed, ensure_ascii=False, indent=2), encoding="utf-8")

per_track: dict[str, int] = {}
for d in feed["items"]:
    per_track[d["track"]] = per_track.get(d["track"], 0) + 1
print("\nitems per track:", per_track)
for e in feed["entities"]:
    if e["item_ids"]:
        print(f'  {e["track"]:<12} {e["name"]:<22} {len(e["item_ids"])}')
print(f'linked {sum(1 for e in feed["entities"] if e["item_ids"])}/{len(feed["entities"])} entries')
