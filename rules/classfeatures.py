"""What a class table grants, as something code can ask about.

Item 39 of the 2026-09-19 play-test, found while finishing the sneak attack work and
written down rather than fixed inside it:

> "`rules/precision.py` is the only thing in the app that reads a class table's `grants`.
> Sneak attack applies; bravery, armour training, weapon training, trap sense, uncanny
> dodge, trapfinding, rogue talents, master strike, arcane bond and arcane school are
> printed on the Class tab and read by nothing."

**And one of them was urgent, because shipping sneak attack made it wrong.** Sneak attack
keys off the defender being flat-footed. Uncanny dodge is the rule that stops a 4th-level
rogue being flat-footed, and improved uncanny dodge is the rule that stops them being
flanked. Both were printed and inert, so a rogue took dice they are immune to — a
coherence problem group 15 introduced, not an old gap.

**A reader, not a special case.** The contract's own worked judgment is that a class
ability "does not need a special case in the engine; it needs a field in the `grants`
grammar, applied generically", and `tests/test_three_laws.py` pins that the engine names
no class ability. So this turns every row of every class table into a TAG, by the first
law's rules — hierarchical, asked by prefix, never matched as a string:

    grants: ["uncanny dodge"]            ->  class.uncanny-dodge
    grants: ["sneak attack 3d6"]         ->  class.sneak-attack
    grants: ["trap sense +2"]            ->  class.trap-sense
    grants: ["improved uncanny dodge"]   ->  class.improved-uncanny-dodge

The NUMBER stays in the table and is read by whoever needs it, exactly as
`precision.dice_for` already reads the sneak dice — because the ladder is the document,
and a homebrew class on the bench that grants uncanny dodge at 6th is then right for
free without anybody editing this file.

Joined to `Actor.standing_tags`, so they are live-read like a feat's tags and a race's:
nothing is stored on the sheet, and correcting a class table corrects every character of
it. `has_state("class.uncanny-dodge")` is the whole interface.

WHAT NOW HAS A READER, and what does not. Stated plainly, because the item this closes
was itself a note about inert documents and the honest half of closing it is saying which
rows are still inert and why:

  uncanny dodge             READ by `Engine._flat_footed`
  improved uncanny dodge    READ by `position.flanking_with`
  evasion / improved        READ by `_op_save`'s damage branch
  sneak attack              READ by `rules/precision.py` (group 15)

  bravery, trap sense       no trigger exists. Both are bonuses on a save against a
                            DESCRIPTOR — fear, traps — and `save` carries no descriptor:
                            its params are `save` and `dc` and nothing else. Adding one
                            would put the trigger in the model's hands, which is the one
                            thing the third law forbids, so it waits for the descriptor
                            to come from a document (a spell's `descriptors`, a hazard's
                            row) rather than from a sentence.
  trapfinding               no trap-finding check exists to bonus.
  armour training           `max_dex` and `acp` are read from the armour row at the point
                            of use; there is no per-character adjustment channel yet.
  weapon training           needs weapon GROUPS, which the weapon table does not carry.
  rogue talent, arcane
  bond, arcane school       choices, not grants: they need a picker at level-up, and no
                            level-up feat/talent writer exists (`docs/hollow-classes.md`).
"""
from __future__ import annotations

import re

from . import classes as classes_mod

# The tag family. One level, like `role.` and `proficient.`, because a class feature is
# a flat thing a character either has or does not.
FAMILY = "class"

# What is stripped off a grant to leave its name: a dice ladder, a bonus, a parenthetical.
_NUMBER = re.compile(r"\s*(?:[+-]\s*\d+|\d+d\d+|\d+|\(.*?\))\s*$")

# The features this module's own readers ask for by name. Named here so no reader spells
# a tag inline, and so this file is the list of what is actually wired up.
UNCANNY_DODGE = f"{FAMILY}.uncanny-dodge"
IMPROVED_UNCANNY_DODGE = f"{FAMILY}.improved-uncanny-dodge"
EVASION = f"{FAMILY}.evasion"
IMPROVED_EVASION = f"{FAMILY}.improved-evasion"

# Evasion is for people who can move: "can be used only if the rogue is wearing light
# armor or no armor", and "a helpless rogue does not gain the benefit of evasion"
# (Core Rulebook, Rogue). The weight word is the armour table's own.
EVASION_ARMOUR = frozenset({"light"})


def slug(grant: str) -> str:
    """"trap sense +2" -> "trap-sense". The name without its number."""
    text = " ".join(str(grant or "").split()).lower()
    text = _NUMBER.sub("", text).strip()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def tags_for(class_id: str, level: int) -> tuple[str, ...]:
    """Every `class.*` tag this class has granted by this level, in table order.

    Deduplicated: a ladder that names "sneak attack" at nine different levels is one
    thing the character has, not nine.
    """
    out: list[str] = []
    if not str(class_id or "").strip():
        return ()
    for lvl in range(1, max(0, int(level or 0)) + 1):
        for grant in classes_mod.table_at(class_id, lvl).get("grants") or []:
            leaf = slug(grant)
            if leaf and f"{FAMILY}.{leaf}" not in out:
                out.append(f"{FAMILY}.{leaf}")
    return tuple(out)


def granted_at(class_id: str, feature: str) -> int:
    """The class level this feature arrives at, or 0.

    Improved uncanny dodge needs it: "unless the attacker has at least four more rogue
    levels than the target has levels in the class that granted this ability". The level
    is read off the table rather than assumed to be four, for the same reason the dice
    are.
    """
    want = str(feature or "").split(".")[-1]
    for lvl in range(1, 21):
        for grant in classes_mod.table_at(class_id, lvl).get("grants") or []:
            if slug(grant) == want:
                return lvl
    return 0


def caught_flat_footed(defender) -> bool:
    """Whether this creature can be caught flat-footed at all.

    The rule, verbatim (Core Rulebook, Rogue — Uncanny Dodge): "She cannot be caught
    flat-footed, nor does she lose her Dexterity bonus to AC if the attacker is invisible.
    She still loses her Dexterity bonus to AC if immobilized."

    Both halves are kept. The exception is asked as a state question and not as a list of
    condition names: `is_helpless` is this app's owner for 1e's "immobilized, unconscious,
    or otherwise incapacitated", which is the same clause, and the contract is explicit
    that conflating it with `is_down` or `can_act` has cost a bug each.

    The feint exception in the same paragraph — "can still lose her Dexterity bonus to AC
    if an opponent successfully uses the feint action against her" — is not implemented
    because there is no feint action in the app to succeed at. Said rather than silently
    dropped.
    """
    if defender is None or not defender.has_state(UNCANNY_DODGE):
        return True
    return bool(defender.is_helpless)


def cannot_be_flanked(defender, attacker) -> str:
    """Why flanking does not work on this defender, or "".

    "The character can no longer be flanked. This defense denies a rogue the ability to
    sneak attack this character by flanking her, unless the attacker has at least four
    more rogue levels than the target has levels in the class that granted this ability."

    The four-level clause is honoured with the levels both sides actually have, and the
    reason is returned in words because it becomes a tell: the rogue is told their flank
    found a guard, not that a rule fired.
    """
    if defender is None or not defender.has_state(IMPROVED_UNCANNY_DODGE):
        return ""
    theirs = int(getattr(defender, "level", 1) or 1)
    mine = int(getattr(attacker, "level", 1) or 1) if attacker is not None else 1
    # "at least four more rogue levels than the target has levels in the class that
    # granted this ability" — the target's levels in THAT class, which for a
    # single-classed character is their level.
    if mine >= theirs + 4:
        return ""
    return f"{defender.name} cannot be flanked"


def evades(actor) -> str:
    """Which evasion this character has working right now: "improved", "evasion", or "".

    The armour clause and the helpless clause are both the book's and both are checked
    here rather than at the call site, so the one rule has one reader.
    """
    if actor is None:
        return ""
    if actor.is_helpless:
        return ""                      # "a helpless rogue does not gain the benefit"
    from .tables import ARMOUR

    worn = str(getattr(actor, "armour", "") or "none").strip().lower()
    row = ARMOUR.get(worn)
    if row is not None and str(row.get("weight", "")).lower() not in EVASION_ARMOUR:
        return ""
    if actor.has_state(IMPROVED_EVASION):
        return "improved"
    if actor.has_state(EVASION):
        return "evasion"
    return ""
