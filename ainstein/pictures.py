"""A real, relevant, high-quality picture for as many cards as the law allows.

In order, for each card that doesn't already have its feed's own image:

1. **The article's own picture** (its `og:image`) — but only from sources
   whose licence covers their images: the space agencies and observatories
   (NASA, ESA, ESO, ESA/Webb, ESA/Hubble, JPL) and the open-access journals
   (eLife, PLOS, Physical Review X/Research, Quantum), whose figures are
   CC BY. Marked `og_image: true` in config.yaml.

2. **Link-preview pictures from everyone else** — only if you switch on
   `pictures.previews` in config.yaml. Publishers put `og:image` on a page
   so that it shows up when the link is shared, which is how X, WhatsApp
   and Google News use it: small, credited, linking back. It is still their
   copyright, so it is off by default and the choice is yours.

3. **A library picture of the subject.** NASA's Image and Video Library
   (public domain) for space, then Wikimedia Commons for everything else —
   only files under CC BY, CC BY-SA, CC0 or public domain, at least 1000 px
   wide, credited to their author and licence. The search words come from
   the card's tags and title.

Everything found here is then downloaded and resized by images.localize —
served from this repository, never hotlinked.
"""

from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request

from .models import Item

UA = "AInstein/0.5 (https://github.com/ayarudek222-droid/AInstein; science feed; pictures)"
OG_RE = [
    re.compile(r"""<meta[^>]+property=["']og:image(?::secure_url)?["'][^>]+content=["']([^"']+)""", re.I),
    re.compile(r"""<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:image["']""", re.I),
    re.compile(r"""<meta[^>]+name=["']twitter:image["'][^>]+content=["']([^"']+)""", re.I),
]
OPEN_LICENCES = ("cc by", "cc-by", "cc0", "public domain", "pd-", "attribution")
STOP = set("""a an the of in on for to and or with from by at as is are was were be been this that these those its it
new study shows show finds find found first how why what when where who which into over under after before about
than more most less can could may might will would via using use used between across during their our your
researchers scientists team paper report reports says said""".split())
SPACE_TRACKS = {"astro", "industry"}


def _get(url: str, limit: int = 600_000, accept: str = "*/*") -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read(limit).decode("utf-8", "replace")


def og_image(page_url: str) -> str:
    try:
        head = _get(page_url, 400_000, "text/html")
    except Exception:
        return ""
    for rx in OG_RE:
        m = rx.search(head)
        if m:
            src = html.unescape(m.group(1)).strip()
            if src.startswith("//"):
                src = "https:" + src
            if src.startswith("http") and not re.search(r"logo|favicon|default|placeholder|rss\.gif", src, re.I):
                return urllib.parse.urljoin(page_url, src)
    return ""


def query_for(item: Item) -> str:
    """Two to four concrete words for a picture search: tags first, then the title."""
    words = []
    for t in (item.tags or [])[:2]:
        words += t.split()
    if len(words) < 2:
        text = re.sub(r"[^\w\s-]", " ", item.hook or item.title)
        words += [w for w in text.split() if w.lower() not in STOP and len(w) > 2 and not w.isdigit()]
    seen, out = set(), []
    for w in words:
        if w.lower() not in seen:
            seen.add(w.lower()); out.append(w)
    return " ".join(out[:4])


def nasa_library(q: str) -> tuple[str, str]:
    try:
        data = json.loads(_get("https://images-api.nasa.gov/search?media_type=image&page_size=10&q=" + urllib.parse.quote(q)))
    except Exception:
        return "", ""
    for it in data.get("collection", {}).get("items", []):
        meta = (it.get("data") or [{}])[0]
        creator = " ".join(str(meta.get(k, "")) for k in ("photographer", "secondary_creator")).lower()
        # the library also holds pictures NASA only hosts; keep NASA's own
        if creator.strip() and "nasa" not in creator and "jpl" not in creator:
            continue
        for link in it.get("links", []):
            href = link.get("href", "")
            if link.get("render") == "image" and href:
                return href.replace("~thumb", "~medium"), "NASA Image Library"
    return "", ""


def commons(q: str) -> tuple[str, str]:
    api = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search"
           "&gsrnamespace=6&gsrlimit=10&prop=imageinfo&iiprop=url|size|extmetadata&iiurlwidth=1280&gsrsearch="
           + urllib.parse.quote(q + " filetype:bitmap"))
    try:
        pages = json.loads(_get(api)).get("query", {}).get("pages", {})
    except Exception:
        return "", ""
    for p in sorted(pages.values(), key=lambda p: p.get("index", 99)):
        info = (p.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        lic = (meta.get("LicenseShortName", {}).get("value") or "").lower()
        if info.get("width", 0) < 1000 or not any(l in lic for l in OPEN_LICENCES) or "nc" in lic.split():
            continue
        if re.search(r"logo|icon|map of|diagram|chart|flag|seal|coat of arms", p.get("title", ""), re.I):
            continue
        artist = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip() or "Wikimedia Commons"
        return info.get("thumburl") or info.get("url", ""), f"{artist[:60]} / Wikimedia Commons ({meta.get('LicenseShortName', {}).get('value', '')})"
    return "", ""


def find(items: list[Item], feeds: list[dict], opts: dict | None = None) -> int:
    opts = opts or {}
    og_ok = {f["name"] for f in feeds if f.get("og_image") or f.get("images")}
    previews = bool(opts.get("previews"))
    library = opts.get("library", True)
    found = 0
    for it in items:
        if it.image_url:
            continue
        src = ""
        if it.source in og_ok or (previews and it.policy.value == "headline_only"):
            src = og_image(it.url)
            if src:
                it.image_url = src
                it.image_credit = it.image_credit or it.source
        if not it.image_url and library:
            q = query_for(it)
            if q:
                url, credit = nasa_library(q) if it.track in SPACE_TRACKS else ("", "")
                if not url:
                    url, credit = commons(q)
                if url:
                    it.image_url, it.image_credit = url, credit
        if it.image_url:
            found += 1
    print(f"  · pictures: {found}/{len(items)} cards have one")
    return found
