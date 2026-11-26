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

WHAT IS IMMUNE, AND THE THING THAT IS EASY TO GET WRONG. Pathfinder 1e dropped 3.5's
blanket immunity for undead and constructs: neither type's trait list mentions critical
hits or precision damage any more (re-read on the legacy PRD's creatureTypes page
2026-09-27, when `rules/coup_de_grace.py` needed the answer — this paragraph used to say
they were "not subject to critical hits", which was the 3.5 wording). So both can be
sneak attacked; only traits that say so in as many words stop precision damage:

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

import logging
import re


# How far a ranged sneak attack reaches. The rogue's own text, and it is a hard edge
# rather than a penalty: past it the dice simply do not apply.
RANGED_FEET = 30

# Traits whose wording explicitly refuses precision damage. Quoted in the header.
IMMUNE_TRAITS = frozenset({"ooze traits", "elemental traits"})

# Held apart on purpose: believed immune, not confirmed on the source pages. See header.
IMMUNE_SUBTYPES_UNSOURCED = frozenset({"incorporeal", "swarm"})

# Feat loop b3 (2026-11-26), each a feat document's tag asked of the vocabulary:
# Shadow Strike (APG) "You can deal precision damage, such as sneak attack damage, against
# targets with concealment (but not total concealment)"; Bludgeoner (UC, Special) "A rogue
# with this feat can use a lethal bludgeoning weapon to deal nonlethal damage with a sneak
# attack"; Flanking Foil (UC) "that opponent ... cannot deal sneak attack damage to you",
# the mark its hit leaves on the foe, whose payload names whom it is foiled against.
# Bludgeoner's sneak attack is the engine's `pulled` itself, which a blow whose -4 is
# waived (`Actor.lethality_swap`) never is.
THROUGH_CONCEALMENT = "precision.through-concealment"
FOILED = "flank.foiled"


def foiled(actor, defender) -> bool:
    """Whether a Flanking Foil mark on `actor` names `defender`: no flanking bonus and no
    precision dice against them until the mark's round runs out."""
    from . import states

    return any(isinstance(e.payload, dict) and e.payload.get("by") == getattr(defender, "ref", None)
               and any(states.matches(str(t), FOILED) for t in e.tags)
               for e in getattr(actor, "effects", ()) or ())


def dice_for(actor) -> str:
    """The sneak attack dice this character's class table grants by their level, or "".

    Read off the table rather than computed from the level, because the table is the
    document and a class that grants it on a different ladder — an archetype, a homebrew
    class on the bench — is then right for free. Group 13 wrote the rogue's ladder down;
    this reads it — by the `class.sneak-attack` ladder and its rung's dice
    (`classfeatures.rungs`, `rung_dice`), the one grammar the other class features use.
    Until 2026-11-22 it was its own regex over the grant's English (`sneak attack NdN`),
    outside the three-law ratchet (audit §3.5).
    """
    from . import classfeatures

    cid = str(getattr(actor, "char_class", "") or "")
    if not cid:
        return ""
    level = int(getattr(actor, "level", 1) or 1)
    for grant in reversed(classfeatures.rungs(cid, level, classfeatures.SNEAK_ATTACK)):
        dice = classfeatures.rung_dice(grant)
        if dice:
            return dice
    return ""


def _doc_of(defender) -> dict:
    doc = None
    getter = getattr(defender, "_creature_doc", None)
    if callable(getter):
        try:
            doc = getter()
        except Exception:
            logging.getLogger(__name__).exception("a creature document did not read")
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
            distance_ft: float | None = None, concealed: bool = False,
            pulled: bool = False) -> tuple[str, str]:
    """(dice, why) when this swing is a sneak attack; ("", why-not) when it is not.

    Every branch answers in words, because the "why not" is worth as much as the "why":
    a rogue who never sees their dice needs to be told it was the concealment.

    `pulled` is a lethal weapon swung to deal nonlethal damage. Core Rulebook, Rogue:
    with a sap or an unarmed strike a rogue may sneak attack for nonlethal damage, but
    "she cannot use a weapon that deals lethal damage to deal nonlethal damage in a
    sneak attack, not even with the usual -4 penalty."
    """
    dice = dice_for(actor)
    if not dice:
        return "", ""
    reason = immune(defender)
    if reason:
        return "", f"{defender.name} {reason}"
    if pulled:
        return "", "a blow pulled to spare them cannot also be aimed at the vitals"
    if foiled(actor, defender):
        return "", f"{defender.name} has turned the angle against them (Flanking Foil)"
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
