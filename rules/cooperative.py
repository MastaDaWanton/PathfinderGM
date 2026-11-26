"""Cooperative Crafting (Advanced Player's Guide), reworked for the benches (feat loop
b4-crafting).

The book (aonprd.com FeatDisplay "Cooperative Crafting", read 2026-11-26): "You can assist
another character in crafting mundane and magical items. You must both possess the relevant
Craft skill or item creation feat, but either one of you can fulfill any other prerequisites
for crafting the item. You provide a +2 circumstance bonus on any Craft or Spellcraft checks
related to making an item, and your assistance doubles the gp value of items that can be
crafted each day."

Its prerequisite "any item creation feat" left with the retired feats (owner 2026-11-22 and
2026-11-26: stripped and reworked). In a one-player game the other crafter is a companion
travelling with the player, so the feat works in either direction — the player holds it and
a companion helps, or a companion holds it and helps the player — and both need ranks in the
one Craft this game keeps (`tables.base_skill`). Read for the five world-class benches:

  +2 circumstance   on every bench check (`tradecraft.bench_check_terms`, the one formula
                    the five benches share), named for the helper;
  doubled per day   work that goes In progress takes half the time (`inprogress.begin`, the
                    one door every bench's long work goes through);
  prerequisites     a spell the helper can cast stands in for one the enchanter does not
                    know (`enchanter._spells_known`): no +5 DC for it.

The help is an `ActiveEffect` on the crafter (`assist.crafting`), laid or lifted by
`settle` each time a bench is opened or worked, since the benches read the actor and not the
scene (law two: removing it removes every term).
"""
from __future__ import annotations

import math

FEAT = "cooperative-crafting"
TAG = "assist.crafting"
ORIGIN = f"feat:{FEAT}"
BONUS = 2


def _crafts(actor) -> bool:
    return int((getattr(actor, "ranks", None) or {}).get("craft", 0) or 0) >= 1


def _holds(actor) -> bool:
    from . import feats

    return FEAT in feats._held(actor)


def helper(scene, crafter):
    """The companion here who helps this crafter at a bench, or None."""
    from . import states

    if crafter is None or scene is None or not _crafts(crafter):
        return None
    for ref, other in list(getattr(scene, "actors", {}).items()):
        if other is crafter or getattr(other, "is_pc", False) or other.is_down:
            continue
        if not other.has_state(states.TRAVELS_WITH_YOU) or not _crafts(other):
            continue
        if _holds(crafter) or _holds(other):
            return other
    return None


def _castable(actor) -> list[str]:
    from . import casting

    if not casting.is_caster(actor):
        return []
    top = casting.highest_spell_level(actor)
    return sorted({s.id for lvl, row in casting.known_spells(actor, up_to=top).items()
                   for s in row if casting.castable_now(actor, s)})


def settle(scene, crafter) -> None:
    """Lay the help on the crafter, or lift it when nobody here gives it."""
    from .activeeffect import ActiveEffect

    if crafter is None:
        return
    crafter.remove_effects(match=lambda e: e.origin == ORIGIN)
    h = helper(scene, crafter)
    if h is None:
        return
    crafter.apply_effect(ActiveEffect(
        name=f"Cooperative crafting with {h.name}", kind="effect", key=FEAT,
        source="Cooperative Crafting", origin=ORIGIN, tags=(TAG,),
        payload={"helper": h.name, "spells": _castable(h)}))


def _help(actor) -> dict | None:
    for e in getattr(actor, "effects", None) or ():
        if e.origin == ORIGIN and TAG in (e.tags or ()):
            return dict(e.payload or {})
    return None


def terms(actor) -> list[dict]:
    """The bench check's term: +2 circumstance, named for the helper, or []."""
    got = _help(actor)
    if got is None:
        return []
    return [{"label": f"Cooperative Crafting ({got.get('helper') or 'a helper'})",
             "value": BONUS}]


# The world-class crafts: a commissioned smith's work or an animal's training is not the
# crafter's own, and the helper does not shorten it.
CRAFTS = frozenset({"alchemist", "blacksmith", "enchanter", "leatherworker", "herbalist"})


def minutes(actor, minutes: int, craft: str = "") -> int:
    """"Doubles the gp value of items that can be crafted each day": half the time."""
    if _help(actor) is None or craft not in CRAFTS:
        return int(minutes)
    return max(1, math.ceil(int(minutes) / 2))


def helper_spells(actor) -> set[str]:
    """Spells the helper can cast, standing in for the crafter's own."""
    got = _help(actor)
    return set(got.get("spells") or ()) if got else set()
