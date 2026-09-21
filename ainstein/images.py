"""Real images, but only the ones we are allowed to show.

An image goes on a card only when three things are true:

1. Its source's licence covers images (config.yaml: `images: true` on the
   feed, with the credit line that licence requires). NASA, ESA, ESO and
   JPL qualify. Magazines, journals, arXiv figures and YouTube thumbnails
   never do.
2. It is not one of the known exceptions inside an open feed. A licence
   only covers what the publisher owns: NASA's feed carries Astronomy
   Picture of the Day, whose photographs belong to the people who took
   them; ESA's feed recently carried a Pokémon character. Each feed lists
   `image_skip` terms for these, matched against the image URL and title.
3. It downloads as an actual image, under a size limit.

Images are downloaded at build time, resized, and served from this
repository — never hotlinked. Hotlinking spends the agency's bandwidth,
breaks when they move a file, and is blocked outright inside claude.ai.
"""

from __future__ import annotations

import hashlib
import io
import re
import urllib.request
from pathlib import Path

from .models import Item

UA = "AInstein/0.4 (https://github.com/AyaRudek/ainstein; personal science feed)"
MAX_BYTES = 8 * 1024 * 1024
MAX_WIDTH = 1280
IMG_RE = re.compile(r"""<img[^>]+src=["']([^"']+)["']""", re.I)


def find_image_url(entry) -> str:
    """The first image a feed entry offers, whichever way the feed chose to send it.

    ESO uses <enclosure>, JPL <media:content>, NASA and ESA an <img> inside
    the HTML body — so check all four.
    """
    for m in getattr(entry, "media_content", None) or []:
        if (m.get("medium") == "image" or str(m.get("type", "")).startswith("image/")) and m.get("url"):
            return m["url"]
    for enc in getattr(entry, "enclosures", None) or []:
        href = enc.get("href") or enc.get("url") or ""
        if str(enc.get("type", "")).startswith("image/") or re.search(r"\.(jpe?g|png|webp)(\?|$)", href, re.I):
            return href
    for t in getattr(entry, "media_thumbnail", None) or []:
        if t.get("url"):
            return t["url"]
    html = ""
    if getattr(entry, "content", None):
        html = entry.content[0].get("value", "")
    html = html or getattr(entry, "summary", "") or ""
    m = IMG_RE.search(html)
    return m.group(1) if m else ""


def allowed(url: str, title: str, skip_terms: list[str]) -> bool:
    hay = f"{url} {title}".lower()
    return not any(term.lower() in hay for term in skip_terms or [])


def _download(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        if not resp.headers.get("Content-Type", "").startswith("image/"):
            return None
        data = resp.read(MAX_BYTES + 1)
    return data if len(data) <= MAX_BYTES else None


def localize(items: list[Item], out_dir: Path, public_prefix: str = "data/img") -> int:
    """Download, resize and store every permitted image; point items at the copy.
    Removes stored images no current item uses, so the repository doesn't grow forever."""
    from PIL import Image  # imported here so the rest of the pipeline runs without Pillow

    out_dir.mkdir(parents=True, exist_ok=True)
    keep: set[str] = set()
    done = 0

    for it in items:
        if not it.image_url:
            continue
        name = hashlib.sha1(it.image_url.encode()).hexdigest()[:16] + ".jpg"
        path = out_dir / name
        if not path.exists():
            try:
                raw = _download(it.image_url)
                if not raw:
                    continue
                img = Image.open(io.BytesIO(raw)).convert("RGB")
                img.thumbnail((MAX_WIDTH, MAX_WIDTH * 2))
                img.save(path, "JPEG", quality=82, optimize=True, progressive=True)
            except Exception as exc:
                print(f"  ! image skipped for {it.id}: {exc}")
                continue
        it.image = f"{public_prefix}/{name}"
        keep.add(name)
        done += 1

    for old in out_dir.glob("*.jpg"):
        if old.name not in keep:
            old.unlink()
    print(f"  · images: {done} stored")
    return done
