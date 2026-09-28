"""The coup de grâce: 1e's blow for a creature that cannot defend itself.

WHY IT EXISTS. Probed 2026-09-27: a thug beaten unconscious (non-lethal past his hit
points) and then attacked by the PC with a rapier through `Engine.run` came back with 0
rolls, no effects, an empty tell and his hit points unchanged — and a dying one the same.
`_op_attack`'s loop broke on `defender.is_down` before the FIRST swing, so "I finish him"
never resolved at all, while `judgement.is_finishing_blow` and
`redirect_attacks_off_corpses` stood guard over a blow that could not land.

THE RULE (Core Rulebook p.197, "Helpless Defenders", read on Archives of Nethys
2026-09-27; paraphrased, the sentences are Paizo's):

  * A full-round action. A melee weapon, or a bow or crossbow if you are adjacent.
  * You automatically hit and score a critical hit.
  * If the defender survives the damage, a Fortitude save at DC 10 + the damage dealt,
    or die.
  * A rogue adds sneak attack damage to it.
  * It provokes attacks of opportunity from threatening opponents.
  * You cannot deliver one against a creature immune to critical hits.
  * Against total concealment it takes two consecutive full-round actions.

An ordinary attack on a helpless defender is still allowed, and is a different rule: Dex
treated as 0 (a -5 modifier) and -4 AC against melee. That half lives in
`Actor.ac_modifiers`, because every reader of an AC must see it.

WHAT IS IMMUNE, CHECKED TWICE. The Bestiary's type lists (the legacy PRD's
creatureTypes page, read 2026-09-27): oozes, elementals and swarms are "not subject to
critical hits"; incorporeal creatures are immune to them "unless the attacks are made
using a weapon with the ghost touch special weapon quality". A first reading of that page
claimed constructs were not subject to critical hits too; a second read of the Construct
and Undead lists found no mention of critical hits in either — which is the 3.5 → PF1
change, and why `precision.py` rightly still sneak attacks both.

What undead and constructs DO have is "immunity to any effect that requires a Fortitude
save (unless the effect also works on objects, or is harmless)". So the blow lands and
crits them, and there is no save to fail: a skeleton finished off is finished by the
damage or not at all.

NOT BUILT, and said so rather than faked: the attack of opportunity (only movement
provokes today — `rules/reactions.py`), the two-round version against total concealment,
and the full-round cost as an enforced budget (the engine enforces no action economy for
any op; the panel files the blow in the standard slot, as it does a full attack). Ghost
touch is not read either: an incorporeal creature is refused whatever the weapon.
"""
from __future__ import annotations

import re

# "DC 10 + damage dealt". The damage the defender actually lost, after DR and
# resistance — the number the tell states — not what the die said.
SAVE_BASE = 10

# The two traits whose own text refuses every Fortitude save. Quoted in the header.
_NO_FORT_TRAITS = frozenset({"undead traits", "construct traits"})
_NO_FORT_TYPES = frozenset({"undead", "construct"})

# Not subject to critical hits: the type/subtype words, then the stat-block phrasing.
_NO_CRIT_TYPES = frozenset({"ooze"})
_NO_CRIT_SUBTYPES = frozenset({"elemental", "swarm", "incorporeal"})
_NO_CRIT_TRAITS = frozenset({"ooze traits", "elemental traits", "critical hits"})

# Bows and crossbows are the ranged weapons the rule names, adjacent only. No leading
# word boundary: the weapon table writes "Longbow" and "Shortbow" as one word, and the
# first cut of this refused a longbow for not being a bow.
_BOW = re.compile(r"bows?\b", re.I)


def _doc_of(defender) -> dict:
    getter = getattr(defender, "_creature_doc", None)
    if callable(getter):
        try:
            return getter() or {}
        except Exception:
            return {}
    return {}


def _words(value) -> set[str]:
    return {w.strip().lower() for w in re.split(r"[,;]", str(value or "")) if w.strip()}


def _immunities(defender) -> set[str]:
    listed = list(getattr(defender, "immunities", None) or [])
    listed += list(_doc_of(defender).get("immune") or [])
    return {" ".join(str(x).split()).lower() for x in listed if str(x).strip()}


def crit_immunity(defender) -> str:
    """Why critical hits do not land on this creature, or "" when they do.

    A reason rather than a bool, because it is printed: the player is told the ooze has
    no vital spot to finish, never that a rule fired. Read off the creature's own
    document, as `precision.immune` does, so a homebrew creature carrying the trait
    behaves without this file learning its name.
    """
    doc = _doc_of(defender)
    traits = _immunities(defender) & _NO_CRIT_TRAITS
    if traits:
        return f"is immune to critical hits ({sorted(traits)[0]})"
    kind = _words(doc.get("creature_type"))
    if kind & _NO_CRIT_TYPES:
        return f"is an {sorted(kind & _NO_CRIT_TYPES)[0]} — no anatomy to finish"
    sub = _words(doc.get("subtype"))
    if sub & _NO_CRIT_SUBTYPES:
        return f"is {sorted(sub & _NO_CRIT_SUBTYPES)[0]} — no anatomy to finish"
    return ""


def fortitude_exempt(defender) -> str:
    """The trait that spares this creature the save, or "" when it must make one."""
    traits = _immunities(defender) & _NO_FORT_TRAITS
    if traits:
        return sorted(traits)[0]
    kind = _words(_doc_of(defender).get("creature_type")) & _NO_FORT_TYPES
    return f"{sorted(kind)[0]} traits" if kind else ""


def save_dc(damage_dealt: int) -> int:
    return SAVE_BASE + max(0, int(damage_dealt))


def refusal(actor, defender, weapon: dict, distance_ft: float | None) -> str:
    """Why this coup de grâce cannot be delivered, as a printable sentence — or "".

    Asked in the order a table would ask it: is there anybody to finish, can they be
    finished, and is what is in the hand the right tool. `distance_ft` is None when
    nobody is on the grid, and then adjacency is taken as the player's to say.
    """
    if defender.has_state("state.down.dead"):
        return f"{defender.name} is already dead."
    if not defender.is_helpless:
        return (f"{defender.name} is not helpless, so there is no coup de grâce to "
                f"deliver — that is for somebody bound, asleep, paralysed or "
                f"unconscious. An ordinary blow is still {actor.name}'s to strike.")
    why = crit_immunity(defender)
    if why:
        return (f"{defender.name} {why}, and a coup de grâce is a critical hit — there "
                f"is nothing to finish that way. An ordinary blow still lands.")
    if str(weapon.get("category") or "melee") != "melee":
        name = str(weapon.get("name") or "")
        if not _BOW.search(name):
            return (f"A coup de grâce takes a melee weapon, or a bow or crossbow at "
                    f"point-blank — not a {name or 'thrown weapon'}.")
        if distance_ft is not None and distance_ft > 5:
            return (f"A coup de grâce with a {name} means standing over "
                    f"{defender.name}, and {actor.name} is {int(distance_ft)} ft away.")
    return ""
