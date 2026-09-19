"""Who exists, and where — asked before anybody is created.

Reported 2026-09-19: *"When I say that I turn to find the mayor, a character who was not in
the scene, the Narrator spawned them instead of saying I couldn't find them."* Seen on the
screen as *"The mayor stands before you, his heavy woolen cloak still smelling of
woodsmoke."* He was not there a moment earlier, and the town has no mayor: among the
export's 256 characters there is no mayor anywhere — the offices are law-speaker,
harbor-reeve, guildmaster — and every city's `Formal Power` fact names an office and never
a person.

Six repairs in `gm/judgement.py` can create somebody because the player named them, and
**not one of them consulted the world**, though the world could answer both halves of the
question the whole time: `World.by_name` / `World.all_named` (is there anybody of this name
or office at all?) and `World.residents` (who lives here). Their only caller was the `/gm`
lookup tool. The engine already refuses absent people correctly wherever money or bodies
are involved — "There is no {buyer} here to sell to", "There is no body here to loot" — so
a *sale* to an absent person was dropped and the turn survived, while an *attack* or a
*talk* invented them. That asymmetry was the whole bug.

**Prior art: scope.** Parser interactive fiction settled this decades ago. Inform answers a
thing out of scope with "You can't see any such thing", and the tradition distinguishes the
cases — a thing that exists but is elsewhere gets a different answer from a word the game
does not know at all
(https://intfiction.org/t/i7-npc-scope-and-the-can-see-check/47889). Three states, three
answers, and never a fourth where the parser conjures the thing to satisfy the sentence.

So: `HERE`, nothing to do; `ELSEWHERE`, say where, by name, so the player can go there;
`NOWHERE`, say so, out of the settlement's own record. Never a spawn.
"""
from __future__ import annotations

import re

HERE = "here"
ELSEWHERE = "elsewhere"
NOWHERE = "nowhere"

# Words that are never the person being looked for. "the man" and "somebody" name no
# office and no name, so the world cannot answer and the question is not this module's:
# a nameless stranger in a crowd is a fair thing for the prose to produce.
VAGUE = frozenset({
    "man", "woman", "men", "women", "person", "people", "folk", "somebody", "someone",
    "anybody", "anyone", "them", "him", "her", "it", "boy", "girl", "child", "stranger",
    "figure", "figures", "crowd", "guard", "guards", "one", "other", "others", "rest",
})

# The words that name somebody who RULES, rather than somebody who works. The difference
# decides whether the settlement's own `Formal Power` fact is worth quoting back: "there is
# no mayor here, its authority is a local reeve" is an answer, and "there is no blacksmith
# here, its authority is a local reeve" is a non sequitur.
OFFICES = frozenset({
    "mayor", "magistrate", "governor", "sheriff", "constable", "reeve", "warden",
    "burgomaster", "alderman", "councillor", "councilor", "chancellor", "steward",
    "lord", "lady", "baron", "baroness", "count", "countess", "duke", "duchess",
    "prince", "princess", "king", "queen", "judge", "justice", "headman", "chief",
    "chieftain", "prefect", "bailiff", "provost", "consul", "senator", "tribune",
    "law", "speaker", "lawspeaker", "authority", "ruler", "regent", "viceroy",
})

_WORDS = re.compile(r"[a-z']+")


def _words(text: str) -> set[str]:
    return {w for w in _WORDS.findall(str(text or "").lower()) if len(w) > 2}


def _role_of(entity) -> str:
    facts = dict(getattr(entity, "facts", {}) or {})
    return str(facts.get("Role") or "")


def matches(entity, phrase: str) -> bool:
    """Is this world character the person that phrase names — by name or by office?

    Both, because a player says either: "I look for Drenn Ironvale" and "I turn to find the
    harbour-reeve" are the same question asked two ways, and the export answers both (every
    CHARACTER carries a `Role` fact).
    """
    want = _words(phrase)
    if not want:
        return False
    return bool(want & _words(getattr(entity, "name", ""))
                or want & _words(_role_of(entity)))


def in_the_room(scene, phrase: str) -> str:
    """The ref of the person here that phrase names, or "". Asked first, always: the
    answer to "where is the smith" is usually "behind you"."""
    want = _words(phrase)
    if scene is None or not want:
        return ""
    best, score = "", 0
    for ref, a in (getattr(scene, "actors", {}) or {}).items():
        if getattr(a, "is_pc", False):
            continue
        shared = len(want & _words(getattr(a, "name", "")))
        shared += len(want & _words(getattr(a, "true_name", "")))
        if shared > score:
            best, score = ref, shared
    return best


def look_for(world, phrase: str, scene=None, location_id: str | None = None) -> dict:
    """The three answers of scope for a person the player named.

    Returns `{"scope": …, "who": name, "where": place, "line": sentence}`. `line` is what
    the player reads, written here rather than left to the narrator, because the whole
    failure was a model answering a question the world had already answered.
    """
    phrase = " ".join(str(phrase or "").split())
    out = {"scope": NOWHERE, "who": "", "where": "", "line": "", "phrase": phrase}
    if not phrase:
        return out
    ref = in_the_room(scene, phrase)
    if ref:
        who = scene.actors[ref]
        return {**out, "scope": HERE, "who": str(who.name), "ref": ref, "line": ""}
    head = (_WORDS.findall(phrase.lower()) or [""])[-1]
    if head in VAGUE and not any(w[:1].isupper() for w in phrase.split()):
        # Not a question the world can answer. Left alone on purpose.
        return {**out, "scope": "", "line": ""}
    if world is None:
        return {**out, "scope": "", "line": ""}

    town = None
    try:
        town = world.get(location_id) if location_id else None
    except Exception:
        town = None
    town_name = str(getattr(town, "name", "") or "")

    found = [e for e in getattr(world, "entities", {}).values()
             if getattr(e, "kind", "") == "CHARACTER" and matches(e, phrase)]
    if found:
        # The one here in town first, because "not in this room" is a shorter walk than
        # "in another city" and the player will want the nearer answer.
        found.sort(key=lambda e: getattr(e, "parent_id", "") != (location_id or ""))
        who = found[0]
        where = ""
        try:
            parent = world.get(getattr(who, "parent_id", None))
            where = str(getattr(parent, "name", "") or "")
        except Exception:
            where = ""
        role = _role_of(who)
        named = f"{who.name}" + (f", {role}" if role else "")
        if where and where == town_name:
            line = (f"{named}, is in {where} but not in this room. Nobody of that "
                    f"description is standing here.")
        elif where:
            line = f"{named}, is in {where}, not here."
        else:
            line = f"{named}, is not here."
        return {**out, "scope": ELSEWHERE, "who": str(who.name), "where": where,
                "line": line}

    # Nobody of that name or office exists. For an OFFICE the settlement's own record says
    # what it has instead, which turns a refusal into information: "there is no mayor in
    # Vormoor; its authority is a local reeve confirmed by Kragmoor Horde's central
    # authority." For a trade it does not — "there is no blacksmith in Vormoor, its
    # authority is a local reeve" was the first version and reads as a non sequitur,
    # because a town plainly has a smith and the world simply never wrote one up. Whether
    # a place holds a trade is the place table's question (`rules/places.STAFFED`), not
    # this one's.
    where = town_name or "this place"
    line = f"There is no {phrase} in {where}."
    if _words(phrase) & OFFICES:
        facts = dict(getattr(town, "facts", {}) or {}) if town is not None else {}
        instead = str(facts.get("Formal Power") or facts.get("Governance") or "").strip()
        instead = re.split(r"(?<=[.!?])\s", instead)[0] if instead else ""
        if instead:
            line += f" Its authority is {instead[0].lower()}{instead[1:]}"
            line += "" if line.endswith(".") else "."
    else:
        line = f"No {phrase} is here, and {where} has none the world names."
    return {**out, "scope": NOWHERE, "where": town_name, "line": line}
