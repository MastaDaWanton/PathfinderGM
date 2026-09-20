"""Sneak attack, applied — the half of item 27 that group 13 did not claim.

`docs/hollow-classes.md`, written when the four core class tables were filled in: "Making
sneak attack apply itself is a damage rule the engine has to run rather than a document it
reads — it is the one item in this group that is not finished by writing a table down. The
table now says the rogue has it, at the right levels, which is the half that was missing
from the screen the player photographed."

This is the other half. Before it, the phrase "sneak attack" appeared in the app twice:
once in `rules/glossary.py` as a definition nothing read, and once in the rogue's table as
a row nothing applied.

THE RULE (d20pfsrd, rogue, read 2026-09-20): extra damage "any time her target would be
denied a Dexterity bonus to AC ... or when the rogue flanks her target"; 1d6 at 1st and
another every two levels; ranged only within 30 feet; never while the target has
concealment; and "not multiplied" on a critical hit.

THE THING THAT IS EASY TO GET WRONG, and the reason the immunity list is short: immunity
to critical hits is NOT immunity to sneak attack in Pathfinder 1e — that was 3.5. Undead
and constructs are "not subject to critical hits" and can still be sneak attacked. Only
traits that refuse precision damage in as many words stop it, and of those only ooze and
the elemental subtype could be quoted from the source; incorporeal and swarm are held
apart in `precision.IMMUNE_SUBTYPES_UNSOURCED` as believed-but-unconfirmed.
"""
from __future__ import annotations

import pytest

from rules import precision
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.grid import Grid


class _Rogue:
    """Only the two fields `dice_for` reads. A whole sheet would say nothing more."""

    def __init__(self, level, char_class="rogue"):
        self.level = level
        self.char_class = char_class


# --- the ladder, read off the table group 13 wrote ---------------------------------------

@pytest.mark.parametrize("level,dice", [
    (1, "1d6"), (2, "1d6"), (3, "2d6"), (7, "4d6"), (10, "5d6"), (19, "10d6"), (20, "10d6"),
])
def test_the_dice_come_off_the_class_table(level, dice):
    """Read rather than computed, so an archetype or a homebrew class that grants it on a
    different ladder is right for free."""
    assert precision.dice_for(_Rogue(level)) == dice


def test_a_fighter_has_none_of_it():
    assert precision.dice_for(_Rogue(20, "fighter")) == ""


def test_nobody_without_a_class_has_it():
    assert precision.dice_for(_Rogue(20, "")) == ""


# --- when it applies -----------------------------------------------------------------------

def _board(rogue_level=3):
    """A rogue and an ally either side of a foe, on a bare map."""
    s = Scene(location_id="t")
    rogue = instantiate("guildhand", scene=s, name="Vess")
    rogue.kind = "pc"
    rogue.char_class = "rogue"
    rogue.level = rogue_level
    s.add(rogue, at=(4, 5))
    ally = instantiate("guildhand", scene=s, name="Ally")
    s.add(ally, at=(6, 5))
    foe = instantiate("guildhand", scene=s, name="Foe")
    foe.hp = foe.hp_base = 60
    s.add(foe, at=(5, 5))
    s.grid = Grid()
    s.sides = {"us": [rogue.ref, ally.ref], "them": [foe.ref]}
    return s, Engine(s, Dice(seed=1), world=None), rogue, ally, foe


MELEE = {"name": "short sword", "category": "melee"}
BOW = {"name": "shortbow", "category": "ranged"}


def test_a_target_whose_guard_is_down_takes_the_dice():
    """"any time her target would be denied a Dexterity bonus to AC"."""
    s, _e, rogue, _a, foe = _board()
    dice, why = precision.applies(s, rogue, foe, MELEE, flat_footed=True)
    assert dice == "2d6" and "guard is down" in why


def test_flanking_takes_the_dice_and_names_who_with():
    s, _e, rogue, _a, foe = _board()
    dice, why = precision.applies(s, rogue, foe, MELEE, flat_footed=False)
    assert dice == "2d6" and why == "flanking with Ally"


def test_a_fair_fight_face_to_face_takes_none():
    """Neither flat-footed nor flanked is the ordinary case, and it must stay silent —
    a rogue who gets the dice every round is not playing Pathfinder."""
    s, _e, rogue, ally, foe = _board()
    s.positions[ally.ref] = (4, 6)        # beside the rogue, not opposite
    assert precision.applies(s, rogue, foe, MELEE, flat_footed=False) == ("", "")


def test_the_flanking_answer_is_the_one_position_py_charges_the_plus_two_off():
    """One rule, one home. The +2 and the sneak dice read the same function, so they can
    never disagree about whether somebody is flanked."""
    from rules import position

    s, _e, rogue, _a, foe = _board()
    assert position.flanking_with(s, rogue, foe, MELEE) == "Ally"
    assert [m.source for m in position.attack_mods(s, rogue, foe, MELEE)] \
        == ["flanking with Ally"]


def test_a_bow_does_not_flank():
    """Flanking requires threatening the target, which a bow does not do — the rule
    `position._melee` already states for the +2."""
    s, _e, rogue, _a, foe = _board()
    assert precision.applies(s, rogue, foe, BOW, flat_footed=False) == ("", "")


def test_a_shot_beyond_thirty_feet_is_not_a_sneak_attack():
    """The rogue's own text: ranged attacks count as sneak attacks only within 30 feet."""
    s, _e, rogue, _a, foe = _board()
    dice, why = precision.applies(s, rogue, foe, BOW, flat_footed=True, distance_ft=45)
    assert dice == "" and "30" in why
    near, _ = precision.applies(s, rogue, foe, BOW, flat_footed=True, distance_ft=25)
    assert near == "2d6"


def test_concealment_stops_it():
    """The rogue's own text: no sneak attack while striking a creature with concealment."""
    s, _e, rogue, _a, foe = _board()
    dice, why = precision.applies(s, rogue, foe, MELEE, flat_footed=True, concealed=True)
    assert dice == "" and "concealed" in why


# --- who is immune, and who only looks immune ---------------------------------------------

def test_a_crowd_has_no_single_guard_to_slip_past():
    """`rules/troops.py` already holds that a unit is immune to anything aimed at a
    specific number of creatures; a blow aimed at one vital spot is the same argument.
    This one is the project's reading, not a quoted rule, and says so."""
    s, _e, rogue, _a, foe = _board()
    from rules import troops

    # A Troop, not `form` — `form` returns the ACTOR that carries one, and assigning an
    # Actor here would have passed this test while meaning nothing.
    foe.troop = troops.Troop(member="goblin", member_name="goblin", member_hp=4,
                             member_xp=10, members=12, members_max=12)
    dice, why = precision.applies(s, rogue, foe, MELEE, flat_footed=True)
    assert dice == "" and "crowd" in why


def test_immunity_to_critical_hits_is_not_immunity_to_sneak_attack():
    """The 3.5 rule that Pathfinder changed, and the reason the immune list is short.
    Undead and constructs are "not subject to critical hits" and can still be sneak
    attacked, so nothing here may key off crit immunity."""
    assert "undead traits" not in precision.IMMUNE_TRAITS
    assert "construct traits" not in precision.IMMUNE_TRAITS


def test_what_is_sourced_is_kept_apart_from_what_is_not():
    """CLAUDE.md: say plainly when a claim could not be sourced. Ooze and elemental are
    quoted from d20pfsrd; incorporeal and swarm could not be confirmed on the universal
    monster rules page, which has no swarm entry and no mention of precision damage under
    Incorporeal."""
    assert precision.IMMUNE_TRAITS == {"ooze traits", "elemental traits"}
    assert precision.IMMUNE_SUBTYPES_UNSOURCED == {"incorporeal", "swarm"}


# --- through the engine, which is the point -----------------------------------------------

def _swing(e, rogue, foe):
    """In a fight that is already running, on the rogue's own turn.

    Not a cold attack: the engine defers a swing that rides the same batch as the fight
    it opened to the player's first combat turn (`_battle_joined`), so a cold attack
    produces no damage roll at all and would prove nothing here.
    """
    s = e.scene
    ally = next(a for a in s.actors.values() if a.name == "Ally")
    e.run(e.validate([{"op": "begin_encounter",
                       "params": {"sides": {"us": [rogue.ref, ally.ref],
                                            "them": [foe.ref]}}}],
                     origin="author:test"))
    # `begin_encounter` lays the battlefield out itself, which is right and which moves
    # everyone off the board this test built. Put them back: the geometry IS the case
    # under test, and a laid-out line has nobody flanking anybody.
    s.positions[rogue.ref] = (4, 5)
    s.positions[ally.ref] = (6, 5)
    s.positions[foe.ref] = (5, 5)
    while s.current_ref() != rogue.ref:
        s.advance_turn()
    res = e.run(e.validate([{"op": "attack", "actor": rogue.ref, "target": foe.ref,
                             "params": {"weapon": "unarmed"}, "because": "t"}],
                           origin="author:test"))
    # The PC rolls their own dice, so every stage comes back as its own popup: the
    # attack, then the damage, then the sneak dice. A 19 on the d20 lands the blow;
    # every other die is answered with its top face, which keeps the damage readable.
    labels = []
    for _ in range(8):
        if res.awaiting is None:
            break
        labels.append(res.awaiting["label"])
        count, faces, _flat = e.dice.parse(str(res.awaiting.get("die") or "1d20"))
        res = e.resume(19 if (count, faces) == (1, 20) else count * faces)
    return res, labels


def test_the_dice_reach_the_damage_roll_and_are_named_on_it():
    """The whole point: the rogue's extra damage is a roll the player can see, itemised
    with a source they can argue with, not a silent number."""
    s, e, rogue, _a, foe = _board(rogue_level=5)
    res, asked = _swing(e, rogue, foe)
    assert any(l.startswith("Sneak attack (3d6)") for l in asked), asked
    sources = " ".join(str(m.get("source", ""))
                       for o in res.outcomes for r in o.as_dict()["rolls"]
                       for m in (r.get("modifiers") or []))
    assert "sneak attack (3d6)" in sources, sources


def test_the_extra_dice_are_not_multiplied_on_a_critical():
    """"The extra damage is not multiplied." The same order the rider die needed: added
    past the crit multiplier, never folded into the weapon's notation. Measured on the
    rider in a live critical — "+12 fist die (1d6) x2" — which is the defect this shape
    exists to avoid."""
    s, e, rogue, _a, foe = _board(rogue_level=5)
    res, _asked = _swing(e, rogue, foe)
    for o in res.outcomes:
        for r in o.as_dict()["rolls"]:
            for m in r.get("modifiers") or []:
                if "sneak attack" in str(m.get("source", "")):
                    assert "x" not in str(m["source"]).split("(")[0], m["source"]


def test_a_fighter_swinging_gets_no_extra_dice_and_no_mention_of_them():
    s, e, rogue, _a, foe = _board()
    rogue.char_class = "fighter"
    _res, asked = _swing(e, rogue, foe)
    assert not any("Sneak attack" in l for l in asked), asked


def test_the_reason_is_given_once_a_swing_and_keeps_the_name_it_was_given():
    """Both measured live on 2026-09-20, fighting a published goblin troop: every blow
    printed "Troop, goblin is a crowd - there is no single guard to slip past" TWICE,
    because the damage stage is re-entered on each resume and the tell was unguarded; and
    `capitalize()` had lowercased the rest of the name, turning "Troop, Goblin" into
    "Troop, goblin"."""
    from rules import troops

    s, e, rogue, _a, foe = _board()
    foe.name = "Troop, Goblin"
    foe.troop = troops.Troop(member="goblin", member_name="goblin", member_hp=4,
                             member_xp=10, members=12, members_max=12)
    res, _asked = _swing(e, rogue, foe)
    said = " ".join(o.tell for o in res.outcomes)
    assert said.count("no single guard to slip past") == 1, said
    assert "Troop, goblin" not in said, said
