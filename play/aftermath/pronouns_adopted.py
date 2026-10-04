"""Pronouns for a person the world gave no gender: the page's first gendered reference to
them, adopted once and held — as the beat reader read it.

The owner's ruling (Q26, 2026-09-28): a person the world gives no gender — every Aurvantis
and Pangrella character; World Bible ships no gender per name or per character yet — takes
the first gendered reference the page makes to them, and keeps it. Not a guess from a
name: the page is what the player read, and keeping the page consistent with itself is
the whole of the aim. Measured on the playtest (item 15): Drenn was they/them on the
sheet, "a man in a suit" and "he says" on the page, and the suggestions asked about "her".

**The reader answers, per they/them person present, "he", "she", "they" or "not said"**
(gm/beat_reader.py). This step used to read it in code: the gender word of a description
the labeller tied to them, else a "…,' he says" pattern beside one of their own lines
(`_from_mentions`, `_from_tags`, `_ATTRIBUTING`, `_LEADING`) — the shape of reading that
gave the servant every "he" of "the man" on 2026-10-03, once the lines had been booked to
him. A person whose gender is already set is never touched (`person_words.apply`).
"""
from __future__ import annotations

STAGE = "beat"
ORDER = 30


def step(ctx) -> list[dict]:
    from gm import beat_reader
    from rules import person_words

    reading = ctx.attribution
    if not isinstance(reading, beat_reader.Reading) or not reading.read:
        return []
    actors = getattr(ctx.scene, "actors", {}) or {}
    rows = []
    for ref, pronoun in reading.pronouns.items():
        actor = actors.get(ref)
        if actor is None or getattr(actor, "is_pc", False):
            continue
        if str(getattr(actor, "gender", "") or "").strip():
            continue
        if str(getattr(actor, "pronouns", "") or "they/them").lower() != "they/them":
            continue
        gender = "man" if pronoun == "he" else "woman"
        if person_words.apply(actor, {"gender": gender,
                                      "pronouns": person_words.PRONOUNS[gender]}):
            rows.append({"kind": "pronouns-adopted", "ref": ref, "pronouns": actor.pronouns,
                         "from": "beat reader"})
    return rows
