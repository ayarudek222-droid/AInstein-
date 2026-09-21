"""Inline data/feed.json into index.html.

index.html fetches ./data/feed.json when served, but also carries an inline
snapshot so the page works when opened as a bare file (or shared as a single
file). This script regenerates index.html from web/template.html.

    python tools/embed.py
"""

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

template = (ROOT / "web" / "template.html").read_text(encoding="utf-8")
feed = (ROOT / "data" / "feed.json").read_text(encoding="utf-8")
json.loads(feed)  # fail loudly on malformed data

(ROOT / "index.html").write_text(
    template.replace("__FEED_JSON__", feed.strip()), encoding="utf-8"
)
print(f"index.html rebuilt ({len(feed)} bytes of feed data inlined)")
