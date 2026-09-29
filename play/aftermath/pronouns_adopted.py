"""Pronouns for a person the world gave no gender: the page's first gendered reference to
them, adopted once and held.

The owner's ruling (Q26, 2026-09-28): a person the world gives no gender — every Aurvantis
and Pangrella character; World Bible ships no gender per name or per character yet — takes
the first gendered reference the page makes to them, and keeps it. Not a guess from a
name: the page is what the player read, and keeping the page consistent with itself is
the whole of the aim. Measured on the playtest (item 15): Drenn was they/them on the
sheet, "a man in a suit" and "he says" on the page, and the suggestions asked about "her".

Read from the engine's own records of the beat, in order of the page:
  1. the attribution's mentions of them (`gm.mentions`: "a man in a suit" labelled c4);
  2. else the speech tag beside their own line — "'You! …,' he says" — the `said` record
     that is theirs, and the pronoun that attributes it.
A person whose gender is already set is never touched (`person_words.apply`).
"""
from __future__ import annotations

import re

STAGE = "beat"
ORDER = 30

_ATTRIBUTING = re.compile(
    r"^[\s,.!?…'\"’”-]{0,4}(?P<p>he|she)\s+(?:\w+ly\s+)?(?:says?|said|asks?|asked|adds?|"
    r"added|mutters?|muttered|replies|replied|answers?|answered|growls?|growled|whispers?|"
    r"whispered|calls?|called|continues?|continued|murmurs?|murmured|laughs?|laughed|"
    r"snaps?|snapped|tells?|told|goes on|went on|shouts?|shouted|grunts?|grunted)\b",
    re.I)
_LEADING = re.compile(
    r"(?P<p>\bhe|\bshe)\s+(?:\w+ly\s+)?(?:says?|said|asks?|asked|adds?|added|mutters?|"
    r"replies|replied|answers?|answered|growls?|whispers?|calls?|murmurs?|tells?)"
    r"[\s,:]*['\"‘“]?\s*$", re.I)


def _from_mentions(ctx, ref: str) -> tuple[str, str]:
    """The first gendered description the attribution bound to `ref`, or ("", "")."""
    from rules import person_words

    attribution = ctx.attribution
    for m in getattr(attribution, "mentions", None) or ():
        if getattr(m, "ref", None) != ref or m.kind != "description":
            continue
        gender = person_words.gender_of(person_words._words(m.phrase))
        if gender:
            return gender, m.phrase
    return "", ""


def _from_tags(ctx, ref: str) -> tuple[str, str]:
    """The pronoun that attributes one of `ref`'s own lines on the page, or ("", "")."""
    text = str(ctx.text or "")
    for rec in ctx.said or ():
        if str(rec.get("who") or "") != ref:
            continue
        line = str(rec.get("line") or "").strip()
        if len(line) < 4:
            continue
        at = text.find(line)
        if at < 0:
            at = text.find(line[:40])
        if at < 0:
            continue
        after = text[at + len(line): at + len(line) + 60]
        m = _ATTRIBUTING.match(after)
        if not m:
            before = text[max(0, at - 60): at]
            m = _LEADING.search(before)
        if m:
            p = m.group("p").lower()
            return ("man" if p == "he" else "woman"), m.group(0).strip()
    return "", ""


def step(ctx) -> list[dict]:
    from rules import person_words

    scene = ctx.scene
    rows = []
    for ref, actor in (getattr(scene, "actors", {}) or {}).items():
        if getattr(actor, "is_pc", False) or str(getattr(actor, "gender", "") or "").strip():
            continue
        if str(getattr(actor, "pronouns", "") or "they/them").lower() != "they/them":
            continue
        gender, source = _from_mentions(ctx, ref)
        if not gender:
            gender, source = _from_tags(ctx, ref)
        if not gender:
            continue
        said = {"gender": gender, "pronouns": person_words.PRONOUNS[gender]}
        if person_words.apply(actor, said):
            rows.append({"kind": "pronouns-adopted", "ref": ref, "pronouns": actor.pronouns,
                         "from": source[:80]})
    return rows
