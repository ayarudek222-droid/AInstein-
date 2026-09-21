"""Re-run the linker over an existing data/feed.json, without refetching.

Useful while tuning ainstein/link.py — the network step is the slow part.
    python tools/relink.py
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ainstein.link import annotate, link       # noqa: E402
from ainstein.models import Item, Policy       # noqa: E402

path = ROOT / "data" / "feed.json"
feed = json.loads(path.read_text(encoding="utf-8"))

items = [Item(
    id=d["id"], title=d.get("title", ""), url=d.get("url", ""),
    published=d["published"].replace("Z", "+00:00"), source=d.get("source", ""),
    policy=Policy(d["policy"]), track=d["track"], abstract=d.get("abstract", ""),
    hook=d.get("hook", ""), body=d.get("body", ""), categories=d.get("categories", []),
) for d in feed["items"]]

pulse_fields = ("item_ids", "last_activity", "quiet_days")
base = [{k: v for k, v in e.items() if k not in pulse_fields} for e in feed["experiments"]]

by_exp = link(items, base)
feed["experiments"] = annotate(base, by_exp, items)

linked = {i.id: i.experiments for i in items if i.experiments}
for d in feed["items"]:
    d["experiments"] = linked.get(d["id"], [])

path.write_text(json.dumps(feed, ensure_ascii=False, indent=2), encoding="utf-8")

for e in feed["experiments"]:
    if e["item_ids"]:
        print(f'  {e["name"]:<22} {len(e["item_ids"])}  {e["item_ids"]}')
print(f'linked {sum(1 for e in feed["experiments"] if e["item_ids"])}/{len(feed["experiments"])} experiments')
