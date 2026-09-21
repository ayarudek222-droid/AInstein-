"""Crossref — the peer-review quality filter.

We do NOT scrape Nature, Science or PRL. We ask Crossref which papers those
journals published, which is open metadata (CC0), and then take the abstract
only when Crossref itself carries one (publishers deposit these deliberately,
as JATS, for reuse). When there is no deposited abstract the item stays
HEADLINE_ONLY: title, journal, date, DOI link — no AI summary.

Crossref asks for a contact address in the User-Agent, which buys you the
faster "polite pool". Set CROSSREF_MAILTO in your environment.
https://api.crossref.org  ·  https://www.crossref.org/documentation/retrieve-metadata/rest-api/
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from ..models import Item, Policy

API = "https://api.crossref.org/journals/{issn}/works"
RATE_LIMIT_S = 1.0


def _ua() -> str:
    mailto = os.environ.get("CROSSREF_MAILTO", "")
    base = "AInstein/0.2 (https://github.com/AyaRudek/ainstein"
    return f"{base}; mailto:{mailto})" if mailto else f"{base})"


def _strip_jats(raw: str) -> str:
    """Crossref abstracts arrive as JATS XML. Flatten to plain text."""
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return " ".join(text.split()).removeprefix("Abstract ").strip()


def _iso(parts: list[int]) -> str:
    y = parts[0]
    m = parts[1] if len(parts) > 1 else 1
    d = parts[2] if len(parts) > 2 else 1
    return datetime(y, m, d, tzinfo=timezone.utc).isoformat()


def fetch(journals: dict[str, str], days: int, rows: int = 40) -> list[Item]:
    """journals: {"Nature": "0028-0836", "Physical Review Letters": "1079-7114", ...}"""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    out: list[Item] = []

    for name, issn in journals.items():
        params = urllib.parse.urlencode({
            "filter": f"from-pub-date:{since},type:journal-article",
            "rows": rows,
            "sort": "published",
            "order": "desc",
            "select": "DOI,title,abstract,author,published,container-title,URL",
        })
        req = urllib.request.Request(
            API.format(issn=issn) + "?" + params,
            headers={"User-Agent": _ua()},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.load(resp)
        except Exception as exc:
            print(f"  ! crossref {name}: {exc}")
            continue

        for w in payload.get("message", {}).get("items", []):
            title = " ".join((w.get("title") or [""])[0].split())
            if not title:
                continue
            abstract = _strip_jats(w.get("abstract", ""))
            authors = [
                " ".join(filter(None, [a.get("given"), a.get("family")]))
                for a in (w.get("author") or [])
            ]
            date_parts = (w.get("published") or {}).get("date-parts", [[1970]])[0]

            out.append(Item(
                id="doi:" + w["DOI"],
                title=title,
                url=w.get("URL") or f"https://doi.org/{w['DOI']}",
                published=_iso(date_parts),
                source="Crossref",
                # The key rule: only a publisher-deposited abstract may be rewritten.
                policy=Policy.ABSTRACT_OK if abstract else Policy.HEADLINE_ONLY,
                track="papers",
                license="Crossref metadata CC0; abstract as deposited by publisher",
                authors=authors[:3],
                n_authors=len(authors),
                abstract=abstract,
                venue=name,
                categories=[name],
            ))
        time.sleep(RATE_LIMIT_S)

    return out
