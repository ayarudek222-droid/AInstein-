"""Build index.html from web/template.html.

index.html fetches ./data/feed.json when served, but also carries an inline
snapshot so the page works when opened as a bare file. If cloud.json exists
(the Supabase project URL and *publishable* key — safe to publish, the
database is protected by row-level security), it is inlined too, and the
public site saves each visitor's diary there.

    python tools/embed.py
"""

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

template = (ROOT / "web" / "template.html").read_text(encoding="utf-8")
feed = (ROOT / "data" / "feed.json").read_text(encoding="utf-8")
json.loads(feed)  # fail loudly on malformed data

cloud_path = ROOT / "cloud.json"
cloud = "null"
if cloud_path.exists():
    c = json.loads(cloud_path.read_text(encoding="utf-8"))
    key = c.get("supabase_key", "")
    if key.startswith("sb_secret_") or "service_role" in key:
        raise SystemExit("cloud.json holds a SECRET key. Use the publishable (anon) key — never the secret one.")
    cloud = json.dumps({"supabase_url": c["supabase_url"], "supabase_key": key})

out = template.replace("__FEED_JSON__", feed.strip().replace("</", "<\\/")).replace("__CLOUD_JSON__", cloud)
(ROOT / "index.html").write_text(out, encoding="utf-8")
print(f"index.html rebuilt ({len(feed)} bytes of feed data inlined, cloud: {'on' if cloud != 'null' else 'off'})")
