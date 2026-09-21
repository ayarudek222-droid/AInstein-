"""Attach pulse items to the standing directory.

A DUNE card should show DUNE news. That needs matching free text against
experiment names, and the hard part is precision, not recall: "ALICE" is
also a name, "LZ" is also two letters, "Auger" is also a person. A false
link on a directory card is worse than a missing one, because the whole
point of the directory is that it can be trusted.

So: short or all-caps acronyms must match case-sensitively as whole words;
longer, distinctive names may match case-insensitively. Keywords ("dark
matter") never create a link on their own — they only rank an already
matched item.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from .models import Item

#: Known name collisions. If one of these matches, the link is vetoed —
#: cheaper and far more honest than trying to disambiguate.
#: "3I/ATLAS" is a comet, named after a survey telescope in Hawaii, and has
#: nothing to do with the detector at CERN.
EXCLUDE: dict[str, re.Pattern] = {
    "atlas": re.compile(r"\dI/ATLAS|ATLAS\s+(survey|telescope)|Asteroid Terrestrial", re.I),
    "alice": re.compile(r"\bAlice\b(?!\s+Collaboration)"),   # the name, not the detector
    "auger": re.compile(r"Auger\s+(electron|spectroscopy|effect)", re.I),
    "lz": re.compile(r"\bLZ\d|\bLZ[-_]"),                    # compression libraries etc.
}

#: Extra names the directory doesn't carry. Keep these specific.
ALIASES: dict[str, list[str]] = {
    "atlas": ["ATLAS Collaboration"],
    "cms": ["CMS Collaboration", "CMS experiment"],
    "lhcb": ["LHCb Collaboration"],
    "alice": ["ALICE Collaboration"],
    "icecube": ["IceCube-Gen2"],
    "belle2": ["Belle II", "SuperKEKB"],
    "ligo": ["LIGO", "Virgo", "KAGRA", "LVK"],
    "hyperk": ["Hyper-K", "Hyper-Kamiokande"],
    "t2k": ["Super-Kamiokande", "Super-K"],
    "auger": ["Pierre Auger"],
    "dune": ["DUNE", "LBNF"],
    "ams02": ["AMS-02"],
    "xenonnt": ["XENONnT", "XENON1T"],
    "lz": ["LUX-ZEPLIN"],
}


def _patterns(exp: dict) -> list[re.Pattern]:
    names = {exp["name"], exp.get("full_name", "")}
    names.update(ALIASES.get(exp["id"], []))

    pats: list[re.Pattern] = []
    for name in filter(None, names):
        escaped = re.escape(name).replace(r"\ ", r"\s+").replace(r"\-", r"[-\s]")
        # Short or shouty acronyms are ambiguous in lowercase — require the caps.
        ambiguous = len(name) <= 5 or name.isupper()
        flags = 0 if ambiguous else re.IGNORECASE
        # A leading "/" or "-" means the name is part of a compound designation
        # (3I/ATLAS, ATLAS-Probe) rather than the experiment itself.
        pats.append(re.compile(rf"(?<![\w\-/]){escaped}(?![\w-])", flags))
    return pats


def link(items: list[Item], entities: list[dict]) -> dict[str, list[str]]:
    """Fill `item.entities`, and return {entity_id: [item_id, ...]}."""
    compiled = {e["id"]: _patterns(e) for e in entities}
    track_of = {e["id"]: e["track"] for e in entities}
    by_entity: dict[str, list[str]] = {e["id"]: [] for e in entities}

    for item in items:
        haystack = " ".join(filter(None, [
            item.title, item.abstract, item.hook, item.body,
            " ".join(item.categories or []),
        ]))
        for ent_id, pats in compiled.items():
            # Only ever link inside the item's own domain. A space story and a
            # particle detector can share a word; they cannot share a tab.
            if track_of[ent_id] != item.track:
                continue
            veto = EXCLUDE.get(ent_id)
            if veto and veto.search(haystack):
                continue
            if any(p.search(haystack) for p in pats):
                item.entities.append(ent_id)
                by_entity[ent_id].append(item.id)

    return by_entity


def annotate(entities: list[dict], by_entity: dict[str, list[str]],
             items: list[Item]) -> list[dict]:
    """Return the directory with pulse attached: item ids, and how quiet it is."""
    when = {i.id: i.published for i in items}
    now = datetime.now(timezone.utc)
    out = []

    for exp in entities:
        ids = by_entity.get(exp["id"], [])
        dates = sorted((when[i] for i in ids), reverse=True)
        enriched = dict(exp)
        enriched["item_ids"] = ids
        enriched["last_activity"] = dates[0] if dates else None
        if dates:
            age = (now - datetime.fromisoformat(dates[0])).days
            enriched["quiet_days"] = age
        else:
            enriched["quiet_days"] = None
        out.append(enriched)

    # Entries with something to show float to the front of the directory.
    out.sort(key=lambda e: (len(e["item_ids"]) == 0, e["name"].lower()))
    return out
