"""A person an NPC places at a real place in this settlement becomes a population record:
heard of, not seen.

Measured on the 2026-09-28 playtest (item 5.2): the watchman said "The girl in the market
might know where the bigger coins are hidden", and a turn later "She's in the market, near
the well". Nothing wrote her down. When the player went to the market to find her, the
finder searched and missed (`population-miss`), and the beat gave itself to somebody else.

Eric Eve's Epistemology (Inform Recipe Book §5.5) gives a thing two flags, *seen* and
*familiar* — familiar being known about "for other reasons", heard of but not found — and
Inform's `[any thing]` token reaches out of scope for exactly the asking-about case
(Recipe Book §6.2). The girl the watchman spoke of is familiar. The owner's ruling (Q5,
2026-09-28): yes, a person an NPC places at a real place in THIS settlement becomes a
record, heard of and not seen — never beyond the settlement, and never at a place the
engine does not have (the engine, not the model, owns geography).

Detected in code over the kept `said` records of NPC speakers: a person phrase joined by
in/at/by/near to the name of one of this settlement's places; a pronoun line ("She's in the
market") binds to the same speaker's last person phrase in the beat. Recorded only when the
finder holds nobody who fits.
"""
from __future__ import annotations

import re

STAGE = "beat"
ORDER = 20

_PREP = r"(?:in|at|by|near|on|round|around|outside|inside|behind)"
_DET = r"(?:the|a|an|that|this|some|one|old|young)"
_PRONOUN_AT = re.compile(
    rf"\b(?P<p>she|he|they)(?:'s|'re| is| are| was| works| keeps| sits| stands| lives| "
    rf"sells| minds| runs| can be found)\b(?:\s+\w+){{0,4}}?\s+{_PREP}\s+(?P<rest>.+)$",
    re.I)


def _person_words() -> frozenset:
    """Words that head a description of a person: the population's person words, the
    gendered nouns, and every single-word trade the occupations are read from."""
    from rules import lives, population
    from gm.checks._people import _PERSON

    words = set(population._PERSON_WORDS) | set(_PERSON)
    for occ in lives.tables()["occupations"]:
        for w in [occ["id"], *str(occ["name"]).split(), *(occ.get("match") or [])]:
            if " " not in w:
                words.add(w.lower())
    for w in ("folk", "people", "crowd", "family", "you", "me", "us", "everyone"):
        words.discard(w)
    return frozenset(words)


def _place_at(rest: str, places) -> object | None:
    """The settlement place `rest` begins with ("the market, near the well" -> the
    market), longest name first, or None."""
    low = " ".join(str(rest or "").lower().split())
    best = None
    for p in places:
        name = " ".join(str(p.name).lower().split())
        bare = re.sub(r"^the\s+", "", name)
        for n in {name, bare, "the " + bare}:
            if n and re.match(rf"{re.escape(n)}(?![\w-])", low):
                if best is None or len(p.name) > len(best.name):
                    best = p
    return best


def phrases_at(line: str, places, person_words) -> list[tuple[str, object]]:
    """(person phrase, place) for every "<person> <prep> <place>" in one line."""
    out = []
    heads = "|".join(sorted((re.escape(w) for w in person_words), key=len, reverse=True))
    pattern = re.compile(
        rf"\b(?P<phrase>{_DET}\s+(?:[a-z'-]+\s+){{0,3}}?(?:{heads}))\s+"
        rf"(?:who\s+\w+\s+)?(?P<prep>{_PREP})\s+(?P<rest>[^.!?;]+)", re.I)
    for m in pattern.finditer(str(line or "")):
        place = _place_at(m.group("rest"), places)
        # A name is the world's to place, not a line's (scope.look_for answers it).
        if place is not None and not any(w[:1].isupper()
                                         for w in m.group("phrase").split()[1:]):
            # The speaker's words, with the place they gave: "the girl in the market" is
            # what the player will say back, and the finder matches every word of it.
            said = " ".join(m.group("phrase").split())
            said = said[:1].lower() + said[1:]
            name = str(place.name)
            where = name if name.lower().startswith("the ") else f"the {name}"
            out.append((f"{said} {m.group('prep').lower()} {where}", place))
    return out


def step(ctx) -> list[dict]:
    from rules import population

    scene = ctx.scene
    if scene is None or not ctx.said:
        return []
    engine = ctx.campaign.engine()
    try:
        places = list(engine.places())
    except Exception:  # noqa: BLE001 — no places, nothing to place anybody at
        return []
    if not places:
        return []
    people = getattr(scene, "people", None) or getattr(scene, "actors", {}) or {}
    words = _person_words()
    rows: list[dict] = []
    last: dict[str, str] = {}
    for rec in ctx.said:
        who = str(rec.get("who") or "")
        line = str(rec.get("line") or "")
        speaker = people.get(who)
        if not who or who == "you" or speaker is None or getattr(speaker, "is_pc", False):
            continue
        found = phrases_at(line, places, words)
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            m = _PRONOUN_AT.search(sentence)
            if m and who in last:
                place = _place_at(m.group("rest"), places)
                if place is not None:
                    found.append((last[who], place))
        for phrase, place in found:
            last[who] = phrase
            if place.id == getattr(scene, "at", None):
                continue                       # here: the page's own people, not this
            if population.find(scene, phrase, world=ctx.world, log_miss=False).scope \
                    != population.NONE:
                continue
            rec_ = population.note(scene, phrase, turn=int(ctx.turn or 0), spot=place.id,
                                   heard_from=who, hint=line)
            if rec_.get("seen") is False and not any(r.get("record") == rec_["id"] for r in rows):
                rows.append({"kind": "heard-of", "record": rec_["id"], "spot": place.id,
                             "from": who})
    return rows
