"""The class tables are documents, and now something reads them.

Item 39 of the 2026-09-19 play-test, written down rather than fixed inside group 15:

> "`rules/precision.py` is the only thing in the app that reads a class table's `grants`.
> Sneak attack applies; bravery, armour training, weapon training, trap sense, uncanny
> dodge, trapfinding, rogue talents, master strike, arcane bond and arcane school are
> printed on the Class tab and read by nothing."

> "**One of them is now urgent because of group 15.** Sneak attack keys off the defender
> being flat-footed, and **uncanny dodge** is the rule that stops a 4th-level rogue being
> flat-footed. The trigger was made real without its counter, so a rogue currently takes
> sneak dice they should be immune to."

Measured before the fix, on a 4th-level rogue standing in a fight they had not yet acted
in: `_flat_footed` answered True, `precision.applies` returned "1d6, their guard is down",
and the rogue's own class table said `uncanny dodge` on the row they had bought.
"""
from __future__ import annotations

import pytest

from rules import classfeatures, position as position_mod
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene


def _scene():
    s = Scene()
    e = Engine(s, Dice(seed=5))
    return s, e


def _rogue(s, level=4, name="Rogue"):
    a = instantiate("guildhand", scene=s, name=name)
    a.char_class = "rogue"
    a.level = level
    a.hp = a.hp_base = 40
    s.add(a)
    return a


class TestTheTableBecomesTags:
    def test_every_row_the_table_grants_is_a_tag(self):
        got = classfeatures.tags_for("rogue", 8)
        assert classfeatures.UNCANNY_DODGE in got
        assert classfeatures.IMPROVED_UNCANNY_DODGE in got
        assert classfeatures.EVASION in got

    def test_nothing_is_granted_before_its_level(self):
        assert classfeatures.UNCANNY_DODGE not in classfeatures.tags_for("rogue", 3)
        assert classfeatures.UNCANNY_DODGE in classfeatures.tags_for("rogue", 4)
        assert classfeatures.IMPROVED_UNCANNY_DODGE not in classfeatures.tags_for("rogue", 7)

    def test_the_number_stays_in_the_table(self):
        """"trap sense +1" and "trap sense +2" are one thing the character has, at a
        tier the table knows — the same split `precision.dice_for` already uses for the
        sneak dice, and the reason a homebrew ladder is right for free."""
        assert classfeatures.slug("trap sense +2") == "trap-sense"
        assert classfeatures.slug("sneak attack 3d6") == "sneak-attack"
        assert classfeatures.slug("armor training 2") == "armor-training"
        tags = classfeatures.tags_for("rogue", 9)
        assert len([t for t in tags if t.endswith("trap-sense")]) == 1

    def test_the_sheet_carries_them_live(self):
        """Read off the class document, never stored: correcting a class table corrects
        every character of it, the way a feat's tags and a race's already work."""
        s, _e = _scene()
        rogue = _rogue(s, level=4)
        assert rogue.has_state(classfeatures.UNCANNY_DODGE)
        assert rogue.has_state("class")            # the family answers by prefix
        rogue.level = 3
        assert not rogue.has_state(classfeatures.UNCANNY_DODGE)

    def test_a_class_with_no_such_row_has_no_such_tag(self):
        s, _e = _scene()
        fighter = _rogue(s, level=4)
        fighter.char_class = "fighter"
        assert not fighter.has_state(classfeatures.UNCANNY_DODGE)
        assert fighter.has_state("class.bravery")

    def test_the_level_it_arrives_at_is_read_and_not_assumed(self):
        assert classfeatures.granted_at("rogue", classfeatures.UNCANNY_DODGE) == 4
        assert classfeatures.granted_at("rogue", classfeatures.IMPROVED_UNCANNY_DODGE) == 8
        assert classfeatures.granted_at("fighter", classfeatures.UNCANNY_DODGE) == 0


class TestUncannyDodge:
    """"She cannot be caught flat-footed ... She still loses her Dexterity bonus to AC if
    immobilized." (Core Rulebook, Rogue.)"""

    def test_a_rogue_of_four_is_never_caught_flat_footed(self):
        s, e = _scene()
        rogue = _rogue(s, level=4)
        assert not s.initiative, "nobody has acted: the ambush case"
        assert e._flat_footed(rogue) is False

    def test_a_rogue_of_three_still_is(self):
        """The measured defect: the trigger shipped without its counter."""
        s, e = _scene()
        assert e._flat_footed(_rogue(s, level=3)) is True

    def test_immobilised_loses_it_anyway(self):
        s, e = _scene()
        rogue = _rogue(s, level=4)
        rogue.add_condition("paralyzed", None, source="test")
        assert rogue.is_helpless
        assert e._flat_footed(rogue) is True

    def test_a_flat_footed_condition_somebody_laid_on_them_still_counts(self):
        """Uncanny dodge stops you being CAUGHT off guard; it does not dispel a
        condition another rule applied."""
        s, e = _scene()
        rogue = _rogue(s, level=4)
        rogue.add_condition("flat-footed", None, source="test")
        assert e._flat_footed(rogue) is True

    def test_the_sneak_dice_do_not_come_out(self):
        """End to end, which is the whole point of item 39's urgency: the rogue's own
        counter has to reach `precision.applies` through the same answer."""
        from rules import precision

        s, e = _scene()
        defender = _rogue(s, level=4, name="Target")
        attacker = _rogue(s, level=3, name="Thief")
        dice, why = precision.applies(
            s, attacker, defender, {"category": "melee"},
            flat_footed=e._flat_footed(defender))
        assert dice == "", why

    def test_and_they_do_against_somebody_without_it(self):
        from rules import precision

        s, e = _scene()
        defender = _rogue(s, level=3, name="Target")
        attacker = _rogue(s, level=3, name="Thief")
        dice, why = precision.applies(
            s, attacker, defender, {"category": "melee"},
            flat_footed=e._flat_footed(defender))
        assert dice == "2d6" and "guard is down" in why


class TestImprovedUncannyDodge:
    """"The character can no longer be flanked ... unless the attacker has at least four
    more rogue levels than the target has levels in the class that granted this ability.\""""

    def _flanked(self, s, defender, attacker, ally):
        s.grid = __import__("rules.grid", fromlist=["Grid"]).Grid(width=8, height=8)
        s.positions[defender.ref] = (4, 4)
        s.positions[attacker.ref] = (3, 4)
        s.positions[ally.ref] = (5, 4)
        s.sides = {"pc": [attacker.ref, ally.ref], "them": [defender.ref]}
        return position_mod.flanking_with(s, attacker, defender, {"category": "melee"})

    def test_a_rogue_of_eight_cannot_be_flanked(self):
        s, _e = _scene()
        defender = _rogue(s, level=8, name="Target")
        attacker = _rogue(s, level=4, name="Thief")
        ally = _rogue(s, level=1, name="Friend")
        assert self._flanked(s, defender, attacker, ally) == ""

    def test_four_levels_above_them_gets_through_it(self):
        """The book's own exception, with the levels both sides actually have."""
        s, _e = _scene()
        defender = _rogue(s, level=8, name="Target")
        attacker = _rogue(s, level=12, name="Thief")
        ally = _rogue(s, level=1, name="Friend")
        assert self._flanked(s, defender, attacker, ally) == "Friend"

    def test_somebody_without_it_is_flanked_normally(self):
        s, _e = _scene()
        defender = _rogue(s, level=7, name="Target")
        attacker = _rogue(s, level=4, name="Thief")
        ally = _rogue(s, level=1, name="Friend")
        assert self._flanked(s, defender, attacker, ally) == "Friend"

    def test_it_takes_the_plus_two_with_it_and_not_only_the_dice(self):
        """"The character can no longer be flanked" — the book denies the flank itself,
        so the bonus to hit goes with the sneak dice. Asked in `flanking_with` for
        exactly that reason: `position.attack_mods` and `precision` read one answer."""
        s, _e = _scene()
        defender = _rogue(s, level=8, name="Target")
        attacker = _rogue(s, level=4, name="Thief")
        ally = _rogue(s, level=1, name="Friend")
        self._flanked(s, defender, attacker, ally)
        mods = position_mod.attack_mods(s, attacker, defender, {"category": "melee"})
        assert not any("flank" in str(m.source).lower() for m in mods)


class TestEvasion:
    """"If she makes a successful Reflex saving throw against an attack that normally
    deals half damage on a successful save, she instead takes no damage." """

    def _save(self, e, actor, face, on_success="half", failure="4d6", dc=10):
        raw = {"op": "save", "actor": actor.ref, "because": "t",
               "params": {"save": "ref", "dc": dc,
                          "on_success": {"damage": on_success},
                          "on_failure": {"damage": failure}}}
        res = e.run(e.validate([raw], origin="author:test"))
        if e.scene.awaiting:
            res = e.resume(face)
        return res

    def test_a_successful_reflex_save_takes_nothing(self):
        s, e = _scene()
        rogue = _rogue(s, level=2)
        rogue.armour = "leather"
        was = rogue.hp
        tell = " ".join(o.tell for o in self._save(e, rogue, 20).outcomes)
        assert rogue.hp == was, tell
        assert "got clear of it entirely" in tell

    def test_without_evasion_a_successful_save_still_takes_half(self):
        s, e = _scene()
        rogue = _rogue(s, level=1)          # evasion is 2nd level for a rogue
        rogue.armour = "leather"
        was = rogue.hp
        self._save(e, rogue, 20)
        assert rogue.hp < was

    def test_heavy_armour_switches_it_off(self):
        """"Evasion can be used only if the rogue is wearing light armor or no armor.\""""
        s, e = _scene()
        rogue = _rogue(s, level=2)
        rogue.armour = "full plate"
        was = rogue.hp
        self._save(e, rogue, 20)
        assert rogue.hp < was

    def test_a_helpless_rogue_does_not_get_it(self):
        s, _e = _scene()
        rogue = _rogue(s, level=2)
        rogue.armour = "leather"
        rogue.add_condition("paralyzed", None, source="test")
        assert classfeatures.evades(rogue) == ""

    def test_a_save_that_does_not_halve_is_untouched(self):
        """Evasion is about "an attack that normally deals half damage on a successful
        save", and nothing else in the app can tell a fireball from a Reflex save
        against a closing door — the branch is what knows."""
        s, e = _scene()
        rogue = _rogue(s, level=2)
        rogue.armour = "leather"
        was = rogue.hp
        tell = " ".join(o.tell for o in
                        self._save(e, rogue, 20, on_success="2d6").outcomes)
        assert rogue.hp < was, tell

    def test_improved_evasion_halves_a_failed_save(self):
        """"...henceforth she takes only half damage on a failed save.\""""
        s, e = _scene()
        monk = _rogue(s, level=9, name="Monk")
        monk.char_class = "monk"
        monk.armour = "none"
        assert monk.has_state(classfeatures.IMPROVED_EVASION)
        # A DC a 9th-level monk's Reflex save cannot make on a 1.
        tell = " ".join(o.tell for o in self._save(e, monk, 1, dc=40).outcomes)
        assert "halved" in tell and "part of the way clear" in tell

    def test_a_fortitude_save_is_not_evaded(self):
        s, e = _scene()
        rogue = _rogue(s, level=2)
        rogue.armour = "leather"
        was = rogue.hp
        raw = {"op": "save", "actor": rogue.ref, "because": "t",
               "params": {"save": "fort", "dc": 10,
                          "on_success": {"damage": "half"},
                          "on_failure": {"damage": "4d6"}}}
        e.run(e.validate([raw], origin="author:test"))
        if s.awaiting:
            e.resume(20)
        assert rogue.hp < was


class TestWhatIsStillInert:
    """The honest half of closing item 39: which rows still read nothing, and why.

    A test rather than a comment, so the day a trigger arrives this fails and somebody
    wires the feature up instead of the note going stale.
    """

    @pytest.mark.parametrize("feature", ["bravery", "trap-sense"])
    def test_a_save_carries_no_descriptor_to_key_these_off(self, feature):
        from rules.intents import OPS

        need, may, _vis = OPS["save"]
        assert "against" not in set(need) | set(may), (
            f"`save` now carries a descriptor — {feature} can be wired up")

    def test_weapon_training_has_no_groups_to_train(self):
        from rules.tables import WEAPONS

        assert not any("group" in row for row in WEAPONS.values()), (
            "the weapon table now carries groups — weapon training can be wired up")
