"""The AI layer: turn an abstract into a card.

Two rules are enforced in code, not just in the prompt:
  1. Only ABSTRACT_OK items are ever sent to the model (`item.may_rewrite`).
  2. One failed card never kills a run.
"""

from __future__ import annotations

import json
import os
import re

from .models import Item

MODEL = os.environ.get("AINSTEIN_MODEL", "claude-sonnet-5")

SYSTEM = """You turn scientific abstracts and official agency releases into short, \
scrollable cards for curious, technically literate readers who are NOT specialists \
in that subfield.

Rules:
- No hype. No "scientists were stunned". No exclamation marks.
- Never state a finding the source text does not state. Keep its uncertainty words \
("suggests", "candidate", "upper limit") when it uses them.
- Numbers are good. Keep the key number if there is one.
- Plain words for jargon; if a term must stay, define it in <=6 words.
- Write your own sentences. Do not quote more than six consecutive words.

Return STRICT JSON, nothing around it:
{
  "hook": "<=70 chars, the finding itself, no clickbait",
  "body": "2-3 sentences, <=420 chars, what was done and what was found",
  "why": "1 sentence, <=140 chars, why a non-specialist should care",
  "tags": ["2-3 lowercase topic tags"],
  "jargon": {"term": "<=6 word definition"},
  "confidence": "solid" | "preliminary" | "modeling-only" | "announcement"
}"""


def rewrite(item: Item, client) -> bool:
    """Fill the card fields on `item`. Returns True on success."""
    if not item.may_rewrite:
        return False

    msg = client.messages.create(
        model=MODEL,
        max_tokens=700,
        system=SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                f"SOURCE: {item.source}"
                + (f" (published in {item.venue})" if item.venue else "")
                + f"\nTITLE: {item.title}"
                + (f"\nCATEGORIES: {', '.join(item.categories)}" if item.categories else "")
                + f"\nTEXT: {item.abstract}"
            ),
        }],
    )

    raw = re.sub(r"^```(?:json)?|```$", "", msg.content[0].text.strip(), flags=re.M).strip()
    card = json.loads(raw)

    item.hook = card.get("hook", "")[:90]
    item.body = card.get("body", "")
    item.why = card.get("why", "")
    item.tags = [t.lower() for t in card.get("tags", [])][:3]
    item.jargon = card.get("jargon", {}) or {}
    item.confidence = card.get("confidence", "")
    return bool(item.hook and item.body)


def rewrite_all(items: list[Item], client) -> None:
    for it in items:
        if not it.may_rewrite:
            continue
        try:
            if rewrite(it, client):
                print(f"  + {it.hook}")
        except Exception as exc:
            print(f"  ! {it.id}: {exc}")
