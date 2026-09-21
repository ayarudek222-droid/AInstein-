"""Check a suggested source before it goes anywhere near config.yaml.

The in-page checker judges a suggestion from what is known about the
publisher, but it cannot visit the address. This does the part that needs
a real network: does it answer, is it a feed or an API, does robots.txt
allow us, and what do its terms say about reuse.

    python tools/vet_source.py https://www.eso.org/public/news/feed/

It prints a report and, when the source looks usable, a config.yaml entry
to paste — always with policy: headline_only. Upgrading a source to
abstract_ok is a human decision made after reading its licence page, and
this script will never make it for you.
"""

import json
import re
import sys
import urllib.parse
import urllib.request
import urllib.robotparser

UA = "AInstein/0.4 (https://github.com/AyaRudek/ainstein; source check)"
LICENCE_WORDS = [
    ("creative commons", "mentions Creative Commons"),
    ("cc by-nd", "CC BY-ND: no derivatives — headline and link only"),
    ("cc by-nc", "CC BY-NC: non-commercial only"),
    ("cc by-sa", "CC BY-SA: share-alike applies"),
    ("cc by 4.0", "CC BY 4.0: reuse with credit"),
    ("public domain", "mentions public domain"),
    ("all rights reserved", "all rights reserved"),
]


def fetch(url, limit=2_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read(limit)


def main(url):
    report, ok = [], True
    parts = urllib.parse.urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        print("Not a web address."); return 1

    # 1. robots.txt
    rp = urllib.robotparser.RobotFileParser(f"{parts.scheme}://{parts.netloc}/robots.txt")
    try:
        rp.read()
        allowed = rp.can_fetch(UA, url)
        report.append(("robots.txt", "allows us" if allowed else "DISALLOWS this path"))
        ok &= allowed
    except Exception:
        report.append(("robots.txt", "could not be read (treat as allowed, be polite)"))

    # 2. does it answer, and as what
    try:
        status, ctype, body = fetch(url)
        report.append(("responds", f"HTTP {status}, {ctype or 'no content type'}"))
    except Exception as exc:
        report.append(("responds", f"NO — {exc}")); ok = False
        return show(url, report, ok, None)

    head = body[:600].lstrip().lower()
    kind = None
    if head.startswith(b"<?xml") or b"<rss" in head or b"<feed" in head:
        try:
            import feedparser
            f = feedparser.parse(body)
            dates = [e.get("published") or e.get("updated") for e in f.entries[:1]]
            report.append(("feed", f"{len(f.entries)} items, titled \"{f.feed.get('title', '?')}\", newest: {dates[0] if dates else '?'}"))
            kind = "feed"
        except ImportError:
            report.append(("feed", "looks like XML (pip install feedparser to inspect)")); kind = "feed"
    elif "json" in ctype or head[:1] in (b"{", b"["):
        try:
            payload = json.loads(body)
            keys = list(payload)[:8] if isinstance(payload, dict) else f"array of {len(payload)}"
            report.append(("api", f"JSON, top level: {keys}")); kind = "api"
        except ValueError:
            report.append(("api", "claims JSON but does not parse")); ok = False
    else:
        report.append(("page", "an HTML page, not a feed — look for its RSS link or an API"))
        m = re.search(rb'<link[^>]+type="application/(?:rss|atom)\+xml"[^>]+href="([^"]+)"', body, re.I)
        if m:
            report.append(("feed link", urllib.parse.urljoin(url, m.group(1).decode())))

    # 3. what the site says about reuse
    text = body.decode("utf-8", "replace").lower()
    found = [msg for word, msg in LICENCE_WORDS if word in text]
    links = re.findall(r'href="([^"]*(?:licen[cs]e|copyright|terms|reuse)[^"]*)"', text)
    report.append(("licence", "; ".join(found) if found else "nothing stated on this page"))
    if links:
        report.append(("read before upgrading", urllib.parse.urljoin(url, links[0])))

    return show(url, report, ok, kind)


def show(url, report, ok, kind):
    width = max(len(k) for k, _ in report)
    print(f"\n{url}\n" + "-" * min(80, len(url)))
    for k, v in report:
        print(f"  {k:<{width}}  {v}")
    print("\n  verdict:", "usable, pending a human read of the licence" if ok and kind else "not usable as it stands")
    if ok and kind == "feed":
        name = urllib.parse.urlparse(url).netloc.replace("www.", "")
        print("\n  config.yaml entry to start from:\n")
        print(f"  - name: {name}\n    url: {url}\n    policy: headline_only\n    track: auto\n"
              f"    license: \"read the licence page before changing policy\"\n    verified: true\n")
    return 0 if ok else 2


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__); sys.exit(1)
    sys.exit(main(sys.argv[1]))
