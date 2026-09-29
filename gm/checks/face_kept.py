"""A described person re-described differently (item 16.7).

Measured on the Bobby playtest, 2026-09-28: the watchman had been described two beats
earlier — an Orc, hair the colour of wet rope, blue ink dots across the knuckles — and a
later beat gave the gate "an older man with a face like cracked leather … the hilt of a
broadsword". Whether that man was the watchman or the patrol's undescribed guard could not
be settled: the attribution labelled one of its two mentions "unknown". The brief now
carries the page's first description (`gm/brief/faces.py`); this check is the net under it.

Closed slots, never free comparison. Re3 (Yang et al. 2022) keeps an attribute dictionary
per character and checks each passage only against it, because comparing statements
freely gave "a sea of false positive contradictions" and plain NLI scored 0.528 ROC-AUC,
near chance. The slots, read off the held face (`Actor.appearance`, `described_as`) and
off each sentence about the person (`_people.about`):

  * people — the world's own peoples (`names.peoples`), never a list of ours; a
    Pangrella Korvu has talons and wings, so no body slot is assumed;
  * age band — young against old, never "older" against a middle age;
  * hair — bald against a hair colour, and one basic colour against another;
  * what they carry — a named weapon they do not carry (`Actor.weapons`).

An unfilled slot is never a contradiction, and a new detail is drift, not a finding (the
owner's ruling on Q9: faces are handled in the brief; no flag for a new detail that
contradicts nothing). Repair: one sentence rewrite naming the held face. No backstop, as
`_repair_misnamed` has none: the flag rests on the labeller, and a wrong swap would write
a wrong face.
"""
from __future__ import annotations

import re

from gm.narration import Finding

from ._people import about

ORDER = 50
KINDS = frozenset({"face-changed"})
DOORS = frozenset({"plan", "turn", "npc", "outcome"})

_YOUNG = re.compile(r"\b(?:young|younger|youthful|youth|boyish|girlish|barely\s+grown|"
                    r"teen\w*)\b", re.I)
_OLD = re.compile(r"\b(?:old|older|elderly|aged|grizzled|wizened|ancient|white-haired|"
                  r"grey-haired|gray-haired|stopped\s+counting|wrinkled|"
                  r"weathered\s+by\s+(?:age|years))\b", re.I)
# In a sentence, an age word counts only on a person or a face: "the old road" is a road.
_BODY_AFTER = (r"(?:\s+(?:\w+\s+){0,2}?(?:man|men|woman|women|fellow|figure|person|face|"
               r"features|skin|hands|guard|watchman|\w+man|\w+woman|one))\b")
_AGE_ON_A_PERSON = re.compile(
    rf"\b(?:young|younger|youthful|old|older|elderly|aged|grizzled|wizened|ancient)"
    rf"{_BODY_AFTER}|\b(?:is|was|looks|seems|too)\s+(?:\w+\s+)?(?:young|old|elderly)\b",
    re.I)
# What a hand of theirs holds, never a weapon merely in the sentence ("he eyes your
# dagger" is yours).
_THEIRS = r"(?:his|her|their|its)\s+(?:\w+\s+){0,2}?"
_HOLDS = (r"(?:carries|carrying|holds|holding|wields|wielding|grips|gripping|draws|"
          r"drawing|hilt\s+of)\s+(?:a|an|the|his|her|their)?\s*(?:\w+\s+){0,2}?")
_COLOURS = ("black", "brown", "red", "blond", "blonde", "golden", "white", "grey", "gray",
            "auburn", "copper", "silver", "sandy")
_HAIR_COLOUR = re.compile(
    rf"\b({'|'.join(_COLOURS)})(?:-haired|\s+hair)\b|\bhair\s+(?:\w+\s+){{0,2}}?"
    rf"({'|'.join(_COLOURS)})\b", re.I)
_BALD = re.compile(r"\b(?:bald\w*|shaven[- ]headed|hairless)\b", re.I)
_SWORDISH = re.compile(r"\b(\w*sword|rapier|dagger|knife|axe|mace|club|spear|hammer|"
                       r"cudgel|scimitar|sabre|saber|falchion|flail|maul|whip|crossbow|"
                       r"bow|halberd|glaive|staff|sap)s?\b", re.I)


def _age(text: str, *, on_a_person: bool = False) -> str:
    if on_a_person:
        text = " ".join(m.group(0) for m in _AGE_ON_A_PERSON.finditer(text))
    young, old = bool(_YOUNG.search(text)), bool(_OLD.search(text))
    if young == old:
        return ""
    return "young" if young else "old"


def _hair(text: str) -> tuple[bool, set[str]]:
    colours = {(a or b).lower().replace("gray", "grey").replace("blonde", "blond")
               for a, b in _HAIR_COLOUR.findall(text)}
    return bool(_BALD.search(text)), colours


def _peoples(world) -> list[str]:
    if world is None:
        return []
    try:
        from rules import names as names_mod

        return sorted({str(n) for n in names_mod.peoples(world).values() if n},
                      key=len, reverse=True)
    except Exception:  # noqa: BLE001 — a world with no peoples fills no slot
        return []


def _people_in(text: str, peoples: list[str], *, as_a_description: bool = False
               ) -> set[str]:
    """The world's peoples a text names. In a sentence, only as what somebody IS —
    "is an Orc", "An Orc stands…" — never "he eyes the dwarf", who is somebody else."""
    found = set()
    for name in peoples:
        word = rf"{re.escape(name)}s?(?![\w-])"
        if as_a_description:
            rx = (rf"(?:\b(?:is|was|looks\s+like|seems)\s+(?:a|an)\s+(?:\w+\s+)?{word}"
                  rf"|^\s*(?:a|an)\s+(?:\w+\s+)?{word})")
        else:
            rx = rf"(?<![\w-]){word}"
        if re.search(rx, text, re.I):
            found.add(name.lower())
    return found


def _carried(actor) -> set[str]:
    held = {str(w).lower() for w in (getattr(actor, "weapons", None) or [])}
    equipped = str(getattr(actor, "equipped", "") or "").lower()
    if equipped:
        held.add(equipped)
    return {h for h in held if h and h not in ("unarmed", "improvised")}


def contradictions(held: str, sentence: str, actor, peoples: list[str]) -> list[str]:
    """The slots on which `sentence` says otherwise than the held face, by name."""
    out = []
    was = _people_in(held, peoples)
    now = _people_in(sentence, peoples, as_a_description=True)
    if was and now and not (now & was):
        out.append(f"a {sorted(now)[0].title()}, and they are "
                   f"{'/'.join(w.title() for w in sorted(was))}")
    a, b = _age(held), _age(sentence, on_a_person=True)
    if a and b and a != b:
        out.append(f"{b}, and they are {a}")
    bald_was, hair_was = _hair(held)
    bald_now, hair_now = _hair(sentence)
    if bald_was and hair_now:
        out.append("with hair, and they are bald")
    elif bald_now and hair_was:
        out.append("bald, and they have hair")
    elif hair_was and hair_now and not (hair_was & hair_now):
        out.append(f"{'/'.join(sorted(hair_now))}-haired, and their hair is "
                   f"{'/'.join(sorted(hair_was))}")
    carried = _carried(actor)
    if carried:
        held_rx = re.compile(rf"\b(?:{_THEIRS}|{_HOLDS}){_SWORDISH.pattern[2:]}", re.I)
        for m in held_rx.finditer(sentence):
            w = m.group(1).lower()
            if w in ("sword",) or any(w in c or c in w for c in carried):
                continue
            out.append(f"carrying a {w}, and they carry {', '.join(sorted(carried))}")
            break
    return out


def find(ctx) -> list:
    peoples = _peoples(ctx.world)
    found = []
    for ref, actor in ctx.scene.actors.items():
        if getattr(actor, "is_pc", False) or not getattr(actor, "described", False):
            continue
        held = " ".join([str(getattr(actor, "appearance", "") or "")]
                        + [str(s) for s in (getattr(actor, "described_as", None) or [])])
        if not held.strip():
            continue
        for written, narration in about(ctx, ref):
            wrong = contradictions(held, narration, actor, peoples)
            if not wrong:
                continue
            found.append(Finding(
                "face-changed",
                f"{actor.name} is described as {wrong[0]}: {written[:90]!r}",
                f"{actor.name} was already described, and this sentence says otherwise "
                f"({wrong[0]}). Keep to how they look: {held.strip()} Rewrite the "
                f"sentence so it agrees, and change nothing else.",
                weight=2, sentences=(written,)))
    return found
