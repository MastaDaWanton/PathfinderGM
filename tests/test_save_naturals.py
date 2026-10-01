"""A natural 20 on a saving throw always succeeds; a natural 1 always fails.

Core Rulebook p.180. Found 2026-09-28 while building the coup de grâce: attack rolls
and combat manoeuvres honoured naturals, each in its own copy, and no save did —
`_op_save` read `margin >= 0`, the cast save `total >= dc`, both ward saves and the
survival saves the same. So a thug whose natural 20 came to 12 against DC 15 failed
by 3, and a creature with +30 on its save passed on a natural 1. Every save site now
asks `dice.d20_succeeds`, which the attack and manoeuvre paths share.

What the rule does NOT cover, and these tests keep it that way: skill and ability
checks. 1e says a 20 on a skill check is not an automatic success, and stabilising,
holding one's breath and a caster level check are checks.
"""
from __future__ import annotations

import pytest

from rules import survival
from rules.bestiary import instantiate
from rules.dice import Dice, Roll, d20_succeeds, natural_said
from rules.engine import Engine, Scene, Ward
from rules.sheet import from_dict, load_pc, to_dict


class _Rng:
    """Every d20 comes off the list; every other die rolls its lowest face."""

    def __init__(self, d20s):
        self.d20s = list(d20s)

    def randint(self, a, b):
        return self.d20s.pop(0) if b == 20 else a


class Loaded(Dice):
    def __init__(self, *d20s):
        super().__init__(0)
        self._rng = _Rng(d20s)


def _thug_scene():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    return s


def _cursed(actor, save, bonus):
    """A save so bad (or so good) that only the face can decide it."""
    actor.flat_saves[save] = bonus


# --- the reader ------------------------------------------------------------------------

def test_the_face_decides_before_the_total():
    nat20 = Roll("1d20", [20], [])
    nat20.modifiers = [type("M", (), {"value": -8})()]      # 12 in total
    assert nat20.total == 12
    assert d20_succeeds(nat20, 15), "a natural 20 that missed DC 15 by 3 still failed"
    assert natural_said(nat20, 15) == "on a natural 20"

    nat1 = Roll("1d20", [1], [type("M", (), {"value": 30})()])
    assert nat1.total == 31
    assert not d20_succeeds(nat1, 15), "a natural 1 that beat DC 15 by 16 still passed"
    assert natural_said(nat1, 15) == "on a natural 1"

    plain = Roll("1d20", [11], [])
    assert d20_succeeds(plain, 11) and not d20_succeeds(plain, 12)
    assert natural_said(plain, 11) == ""


def test_only_a_single_d20_has_a_natural():
    """A 2d10 that shows 20 is not a natural 20."""
    assert Roll("2d10", [10, 10], []).natural is None
    assert not d20_succeeds(Roll("2d10", [10, 10], []), 21)


@pytest.mark.parametrize("face", [1, 20])
def test_a_player_rolled_d20_keeps_its_face(face):
    """The popup's two doors: `given` (a face) and `given_total` (a pool's total). A
    1d20 through either is one face, so the player's own natural 20 counts."""
    d = Dice(0)
    assert d.given(face, []).natural == face
    assert d.given_total(face, "1d20").natural == face


# --- every save site -------------------------------------------------------------------

@pytest.mark.parametrize("face, bonus, dc, verdict, said", [
    (20, -30, 15, "success", "on a natural 20"),
    (1, 30, 15, "failure", "on a natural 1"),
])
def test_the_save_op(face, bonus, dc, verdict, said):
    s = _thug_scene()
    _cursed(s.actors["c1"], "fort", bonus)
    e = Engine(s, Loaded(face))
    out = e.run(e.validate([{"op": "save", "actor": "c1", "because": "test",
                             "params": {"save": "fort", "dc": dc}}],
                           origin="author:test")).outcomes[0]
    assert out.verdict == verdict
    assert said in out.tell
    # The margin agrees with the verdict, as the manoeuvre path's does.
    assert (out.margin >= 0) == (verdict == "success")


def test_the_players_own_natural_20_on_the_popup_saves_them():
    """The PC rolls their own save; the face they report is the one that decides."""
    s = _thug_scene()
    _cursed(s.actors["pc"], "will", -30)
    e = Engine(s, Dice(5))
    res = e.run(e.validate([{"op": "save", "actor": "pc", "because": "test",
                             "params": {"save": "will", "dc": 15}}],
                           origin="author:test"))
    assert res.awaiting
    out = e.resume(20).outcomes[0]
    assert out.verdict == "success", out.tell


def _wizard_at(s):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    # Out of Kesst's leather, which since 2026-09-30 makes an arcane caster roll spell
    # failure first (tests/test_gear_usable.py); this test is about the save's natural.
    d.update({"class": "wizard", "level": 5, "ranks": {}, "armour": "none"})
    d["abilities"]["int"] = 18
    d["spellbook"] = ["burning-hands"]
    d["prepared"] = {"burning-hands": 3}
    s.people.pop("pc", None)
    s.add(from_dict(d, ref="pc"))


@pytest.mark.parametrize("face, bonus, saved", [(20, -30, True), (1, 30, False)])
def test_the_spell_save(face, bonus, saved):
    """Burning hands, Reflex half, at a thug whose Reflex only the face can decide."""
    s = _thug_scene()
    _wizard_at(s)
    _cursed(s.actors["c1"], "ref", bonus)
    # In a fight already: a first harmful cast outside one opens the fight and rolls
    # nothing (item 22.2), and this loaded die has one face to give.
    s.initiative, s.sides, s.round, s.turn = (
        [("pc", 20), ("c1", 10)], {"pc": ["pc"], "them": ["c1"]}, 1, 0)
    e = Engine(s, Loaded(face))
    out = e.run(e.validate([{"op": "cast", "actor": "pc", "because": "test",
                             "visibility": "hidden",
                             "params": {"spell": "burning-hands", "at": "c1"}}])).outcomes[0]
    word = "makes" if saved else "fails"
    assert f"{word} the Reflex save" in out.tell, out.tell
    assert f"natural {face}" in out.tell, out.tell


@pytest.mark.parametrize("spec", [
    {"type": "damage", "dice": "1d6", "damage_type": "fire"},
    {"type": "save_gate", "target": "fort", "on_failure": [], "on_success": []},
], ids=["ward-save", "save-gate"])
def test_a_ward_save(spec):
    s = _thug_scene()
    thug = s.actors["c1"]
    _cursed(thug, "fort", -30)
    s._dice = Loaded(20)
    ward = Ward(owner="", trigger="each_round", spec=spec, source="the cloud",
                save="fort", dc=15, save_effect="negates")
    got = s._resolve_on(thug, ward, spec, "fort", "negates")
    saved = [g for g in got if g.get("kind") == "ward_saved"]
    assert saved, f"a natural 20 against the cloud still failed: {got}"
    assert saved[0]["natural"] == "on a natural 20"


def test_the_survival_save_and_not_the_con_check():
    """Cold and heat are Fortitude saves and honour the face; thirst's Constitution
    check is a check and does not."""
    s = _thug_scene()
    pc = s.actors["pc"]
    _cursed(pc, "fort", -30)
    assert survival._check(pc, "cold", 15, Loaded(20), save="fort")["passed"]
    pc.abilities["con"] = 1                              # -5
    assert not survival._check(pc, "thirst", 25, Loaded(20))["passed"], (
        "a natural 20 on a Constitution CHECK was read as a save")
