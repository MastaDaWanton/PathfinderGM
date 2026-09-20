"""Sneak attack: the one thing the rogue's table promised and the engine never did.

Group 15 of the fix pass after the 2026-09-19 play-test, and the half of item 27 that
group 13 explicitly did not claim. `docs/hollow-classes.md` put it plainly: "Making sneak
attack apply itself is a damage rule the engine has to run rather than a document it
reads — it is the one item in this group that is not finished by writing a table down."

The table says the rogue has it, at the right levels. This makes it land.

WHY IT IS ITS OWN MODULE, like `rules/position.py` before it and for the same stated
reason: none of these questions can be answered by the sheet. Whether this swing is a
sneak attack depends on the DEFENDER's guard, on where both of them are standing, on how
far apart they are, and on what the defender is made of. `Actor.damage_modifiers` knows
none of that. Scene in, dice out; nothing here mutates anything.

THE RULE (d20pfsrd, rogue, read 2026-09-20):

  "The rogue's attack deals extra damage any time her target would be denied a Dexterity
  bonus to AC ... or when the rogue flanks her target." 1d6 at 1st, another d6 every two
  levels. "Ranged attacks can count as sneak attacks only if the target is within 30
  feet." "A rogue cannot sneak attack while striking a creature with concealment." The
  extra damage "is not multiplied" on a critical hit.

WHAT IS IMMUNE, AND THE THING THAT IS EASY TO GET WRONG. Immunity to critical hits is NOT
immunity to sneak attack in Pathfinder 1e — that was 3.5. Undead and constructs are "not
subject to critical hits" and can still be sneak attacked; only traits that say so in as
many words stop precision damage:

  ooze traits      "Not subject to critical hits or flanking. Does not take additional
                   damage from precision-based attacks, such as sneak attack."
  elemental        the same sentence, for the elemental subtype.

Those two are quoted from the source. **Incorporeal and swarm are widely held to be immune
as well, and this could not be confirmed on d20pfsrd's own pages** — the universal monster
rules entry for Incorporeal does not mention critical hits or precision damage at all, and
the page has no swarm entry. They are honoured here because the corpus's own stat blocks
carry the subtype, and they are listed apart below so that the sourced rules and the
unsourced ones are never confused for each other.

Immunity is read from the creature's OWN document — its `immune` list and its `subtype` —
rather than from a list of type names kept here, which is the same argument
`rules/leveling.table_die` makes for reading a column by name: a creature that ships with
traits nobody here has heard of still behaves correctly.
"""
from __future__ import annotations

import re

from . import classes as classes_mod

# How far a ranged sneak attack reaches. The rogue's own text, and it is a hard edge
# rather than a penalty: past it the dice simply do not apply.
RANGED_FEET = 30

# Traits whose wording explicitly refuses precision damage. Quoted in the header.
IMMUNE_TRAITS = frozenset({"ooze traits", "elemental traits"})

# Held apart on purpose: believed immune, not confirmed on the source pages. See header.
IMMUNE_SUBTYPES_UNSOURCED = frozenset({"incorporeal", "swarm"})

# "sneak attack 3d6" on a class table row.
_SNEAK = re.compile(r"sneak attack\s+(\d+d\d+)", re.I)


def dice_for(actor) -> str:
    """The sneak attack dice this character's class table grants by their level, or "".

    Read off the table rather than computed from the level, because the table is the
    document and a class that grants it on a different ladder — an archetype, a homebrew
    class on the bench — is then right for free. Group 13 wrote the rogue's ladder down;
    this reads it.
    """
    cid = str(getattr(actor, "char_class", "") or "")
    if not cid:
        return ""
    best = ""
    for level in range(1, int(getattr(actor, "level", 1) or 1) + 1):
        for grant in classes_mod.table_at(cid, level).get("grants") or []:
            m = _SNEAK.search(str(grant))
            if m:
                best = m.group(1)
    return best


def _doc_of(defender) -> dict:
    doc = None
    getter = getattr(defender, "_creature_doc", None)
    if callable(getter):
        try:
            doc = getter()
        except Exception:
            doc = None
    return doc or {}


def immune(defender) -> str:
    """Why this creature takes no precision damage, or "" when it does.

    A reason rather than a bool, because it becomes a tell: the narrator is told that the
    blow found nothing to find, never that a rule fired.
    """
    doc = _doc_of(defender)
    words = {str(x).strip().lower() for x in (doc.get("immune") or [])}
    if words & IMMUNE_TRAITS:
        trait = sorted(words & IMMUNE_TRAITS)[0]
        return f"has {trait} — no anatomy for a precise blow to find"
    subtypes = {s.strip().lower()
                for s in re.split(r"[,;]", str(doc.get("subtype") or "")) if s.strip()}
    if subtypes & IMMUNE_SUBTYPES_UNSOURCED:
        which = sorted(subtypes & IMMUNE_SUBTYPES_UNSOURCED)[0]
        return f"is {which} — no anatomy for a precise blow to find"
    # A crowd is not one body. `rules/troops.py` already holds that a unit is immune to
    # anything aimed at a specific number of creatures; a blow aimed at one vital spot is
    # the same argument, and this one is this project's reading rather than a quoted rule.
    if getattr(defender, "troop", None) is not None:
        return "is a crowd — there is no single guard to slip past"
    return ""


def applies(scene, actor, defender, weapon, *, flat_footed: bool,
            distance_ft: float | None = None, concealed: bool = False) -> tuple[str, str]:
    """(dice, why) when this swing is a sneak attack; ("", why-not) when it is not.

    Every branch answers in words, because the "why not" is worth as much as the "why":
    a rogue who never sees their dice needs to be told it was the concealment.
    """
    dice = dice_for(actor)
    if not dice:
        return "", ""
    reason = immune(defender)
    if reason:
        return "", f"{defender.name} {reason}"
    if concealed:
        # "A rogue cannot sneak attack while striking a creature with concealment."
        return "", f"{defender.name} is concealed — nothing to aim at precisely"
    ranged = bool(weapon.get("ranged") or str(weapon.get("category", "")).startswith("ranged"))
    if ranged and distance_ft is not None and distance_ft > RANGED_FEET:
        return "", (f"too far for a precise shot — {int(distance_ft)} ft, and a sneak "
                    f"attack reaches {RANGED_FEET}")
    if flat_footed:
        return dice, "their guard is down"
    # The grid's own answer, through the one function that computes it. `position.py`
    # charges the +2 off exactly this fact, so the bonus and the dice can never disagree
    # about whether somebody is flanked.
    from . import position as position_mod

    with_whom = position_mod.flanking_with(scene, actor, defender, weapon)
    if with_whom:
        return dice, f"flanking with {with_whom}"
    return "", ""
