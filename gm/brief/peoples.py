"""OF WHICH PEOPLE: each present person's people, and what this place has been promised.

Measured on the 2026-09-30 playtest (item 10): 8 of 8 NPCs in Sam's save were stored as
`race: "human"` with a Ratfolk face and no people. The brief carried the people only as the
first word of the face ("Ratfolk: …"), which a later beat shortens or drops, and Quin Nutmeg
was written with human hair and skin and then "rodent-featured eyes". The people is now
recorded on every person (`person_words.settle_people`) and stated here as the fact it is.

And the grant (owner ruling F2, `rules/granted.py`): "any human women here?" — "There is
one." Until somebody is minted to keep it, the narrator is told what was promised, so the
woman it describes behind the curtain is the one the engine will make.
"""
from __future__ import annotations

ORDER = 65
SLOT = "people"
SCAFFOLD = ("OF WHICH PEOPLE (fact; every description of them keeps to it):",
            "PROMISED HERE (fact; whoever it turns out to be is this):")


def section(ctx) -> tuple[str, dict]:
    from rules import granted

    scene = ctx.scene
    facts: dict = {}
    rows = []
    for ref, actor in (getattr(scene, "actors", {}) or {}).items():
        if actor.is_pc or actor.has_state("state.hidden"):
            continue
        people = str(getattr(actor, "heritage", "") or "").strip()
        if not people:
            continue
        rows.append(f"{actor.name} ({ref}) is {people}")
        facts[ref] = people
    text = ""
    if rows:
        text += ("\n  OF WHICH PEOPLE (fact; every description of them keeps to it): "
                 + "; ".join(rows) + ".")
    at = str(getattr(scene, "at", "") or "")
    promised = []
    people = getattr(scene, "people", {}) or {}
    for rec in granted.open_grants(scene):
        g = rec["granted"]
        if not granted._within(at, g.get("place", "")):
            continue
        by = people.get(g.get("by") or "")
        who = f"{by.name} ({by.ref})" if by is not None else "somebody here"
        promised.append(f"{who} said there is {granted.phrase_of(g)} here")
        facts.setdefault("promised", []).append(rec.get("id"))
    if promised:
        text += ("\n  PROMISED HERE (fact; whoever it turns out to be is this): "
                 + "; ".join(promised) + ".")
    return text, facts
