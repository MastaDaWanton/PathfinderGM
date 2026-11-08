"""The hit-point ladder, read against the Core Rulebook line by line.

The ponytail audit of 0.2.26 (2026-11-07, findings #2, #3, #4, #14, #15, #16 and two of
the smaller engine findings) found the ladder right where the blow lands and wrong almost
everywhere else: fire and poison could take a body far below 0 with no state at all, the
stabilise roll cost the hit point it was meant to save, a cure to exactly 0 left the
patient dying, and off screen the dying used a 10% rule the book never had.

The rules, quoted from the CRB on aonprd.com (Combat, Injury and Death; Appendix 2,
Conditions):

- Dying: "If your hit point total is negative, but not equal to or greater than your
  Constitution score, you're dying ... A dying character loses 1 hit point every round."
- Stabilising: "the character must make a DC 10 Constitution check to become stable. The
  character takes a penalty on this roll equal to his negative hit point total ... A
  natural 20 on this check is an automatic success. If the character fails this check, he
  loses 1 hit point."
- Healing: "If any sort of healing cures the dying character of even 1 point of damage,
  he becomes stable and stops losing hit points." "Healing that raises his hit points to
  0 makes him fully conscious and disabled." Disabled (Appendix 2): "A character with 0
  hit points ... is disabled."
- Bleed (Appendix 2): "Bleed effects do not stack with each other unless they deal
  different kinds of damage. When two or more bleed effects deal the same kind of damage,
  take the worse effect." Wounding (CRB, magic weapons) says otherwise for itself:
  "Multiple hits from a wounding weapon increase the bleed damage."
"""
from __future__ import annotations

from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc

ABILITIES = {k: 10 for k in ("str", "dex", "con", "int", "wis", "cha")}


class Face(Dice):
    """Every d20 shows the one face: the stabilise roll is the only d20 these bodies
    roll, so the face is the test's to choose."""

    def __init__(self, face: int, seed: int = 1):
        super().__init__(seed=seed)
        self.face = face

    def d20(self, modifiers=None, label="", **kw):
        return self.given(self.face, modifiers or [], label=label)


def _kesst():
    """Con 12: dead at -12, so -11 is the last rung above it."""
    return load_pc("fixtures/pc-kesst.json")


def _person(ref="c1", name="the guard", hp=10, **abilities):
    return from_dict({"name": name, "kind": "npc", "hp": hp, "hp_max": hp,
                      "abilities": dict(ABILITIES, **abilities)}, ref=ref)


def _dying(actor, hp):
    actor.hp = hp
    actor.apply_hp_state()
    assert actor.has_state("state.down.dying"), actor.conditions
    return actor


# --- #2: periodic, affliction and ability damage cross the thresholds ----------------

def _burning(actor, amount):
    actor.apply_effect(ActiveEffect(
        name="the fire", kind="effect", key="state.burning", source="a flask",
        origin="item:test", tags=("state.burning",),
        periodic=[{"per": "round", "damage": amount, "damage_type": "fire"}]))


def test_a_burn_that_drops_a_body_below_zero_leaves_it_dying():
    """Audit #2, measured: a thug at 1 HP burnt for 6d6 went to -21 HP with no condition,
    and a player at -5 could still act. `run_periodic` called `take_damage` and nothing
    after it, so no threshold was ever asked."""
    thug = _person(hp=12, con=12)
    thug.hp = 1
    _burning(thug, 4)
    out = thug.run_periodic("round", 1, Dice(seed=1))
    assert thug.hp == -3
    assert thug.has_state("state.down.dying") and thug.has_state("state.down.unconscious")
    assert {"kind": "condition", "ref": "c1", "condition": "dying",
            "from": "hit points"} in out, "the state went on with no record to tell it by"


def test_a_burn_past_the_floor_kills():
    thug = _person(hp=12, con=12)
    thug.hp = 1
    _burning(thug, 20)
    thug.run_periodic("round", 1, Dice(seed=1))
    assert thug.is_dead and not thug.has_state("state.down.dying")


def test_a_poisons_hit_point_damage_crosses_the_threshold():
    """The affliction's own damage branch (`affliction_strikes`) took hit points through
    `take_damage` and stopped there, like the burn."""
    victim = _person(hp=12, con=12)
    victim.hp = 2
    eff, _ = victim.take_affliction(
        {"kind": "poison", "dc": 30, "save": "fort",
         "effects": [{"damage": 6, "type": "untyped"}]},
        name="black ichor", source="a dart", origin="item:test",
        onset_rounds=0, every_rounds=1, limit=6)
    out = victim.affliction_strikes(eff, Dice(seed=1))
    assert victim.hp == -4 and victim.has_state("state.down.dying")
    assert any(r.get("condition") == "dying" for r in out)


def test_constitution_damage_that_takes_hit_points_below_zero_leaves_them_dying():
    """Audit #2: `_op_ability_damage` asked `ability_zero_effects` (a score of 0) and
    never the hit points the lost Constitution modifier carried away with it. Kesst at 1
    of her hit points, Con 12 to 6, lost 3 a level and lay at a negative total awake."""
    s = Scene()
    pc = s.add(_kesst())
    engine = Engine(s, Dice(seed=1))
    pc.hp = 1
    res = engine.run(engine.validate([{
        "op": "ability_damage", "actor": "pc", "because": "a shadow's touch",
        "params": {"to": "pc", "ability": "con", "amount": 6}}], origin="author:test"))
    assert pc.hp < 0
    assert pc.has_state("state.down.dying"), pc.conditions
    out = res.outcomes[-1]
    assert any(e.get("condition") == "dying" for e in out.effects)
    assert "dying" in out.tell


def test_a_carried_price_that_runs_constitution_out_kills():
    """The periodic executor's `ability_damage` document took the score and asked no
    threshold at all: Constitution 0 and still breathing."""
    victim = _person(hp=12, con=3)
    victim.apply_effect(ActiveEffect(
        name="a cursed idol", kind="carried", key="carried:idol", source="item:idol",
        origin="item:idol",
        periodic=[{"per": "day", "effect": {"type": "ability_damage", "target": "con",
                                            "amount": 3}}]))
    out = victim.run_periodic("day", 1, Dice(seed=1))
    assert victim.is_dead
    assert any(r.get("condition") == "dead" for r in out)


# --- smaller finding: Con 0 is death through the one door ------------------------------

def test_constitution_zero_clears_the_rungs_above_dead():
    """Audit, smaller finding: `ability_zero_effects` wrote `dead` with `add_condition`,
    leaving a dying body dead AND dying AND unconscious — the second copy of `die()` the
    three laws' literal-key ratchet exists to stop."""
    victim = _dying(_person(hp=12, con=12), -2)
    victim.damage_ability("con", 12)
    assert victim.ability_zero_effects() == ["dead"]
    assert victim.is_dead
    assert not victim.has_state("state.down.dying")
    assert not victim.has_state("state.down.unconscious")


# --- #3: the stabilise roll comes first ------------------------------------------------

def test_a_made_stabilise_check_costs_no_hit_point():
    """Audit #3, measured: a 21 against DC 11 at -1 left the character stable at -2.
    "If the character fails this check, he loses 1 hit point" — only then."""
    pc = _dying(_kesst(), -1)
    out = pc.bleed_out(Face(20))
    assert out["outcome"] == "stable"
    assert pc.hp == -1 and pc.has_state("state.down.stable")
    assert out["dc"] == 11


def test_a_failed_stabilise_check_costs_the_hit_point():
    pc = _dying(_kesst(), -1)
    out = pc.bleed_out(Face(1))
    assert out["outcome"] == "dying" and pc.hp == -2


def test_one_rung_above_the_floor_still_gets_its_roll():
    """Audit #3, measured: at -11 with Con 12 the point came off first, so she died with
    no roll at all, even with a forced 20."""
    pc = _dying(_kesst(), -11)
    out = pc.bleed_out(Face(20))
    assert out["outcome"] == "stable" and pc.hp == -11 and not pc.is_dead


def test_a_natural_twenty_stabilises_whatever_the_total():
    """"A natural 20 on this check is an automatic success." A Con 30 brute at -29 needs
    a 39; 20 + 10 is 30, and the natural face carries it anyway."""
    brute = _dying(_person(hp=40, con=30), -29)
    out = brute.bleed_out(Face(20))
    assert out["outcome"] == "stable" and brute.hp == -29


def test_failing_on_the_last_rung_kills():
    pc = _dying(_kesst(), -11)
    out = pc.bleed_out(Face(1))
    assert out["outcome"] == "dead" and pc.is_dead and pc.hp == -12


def test_continuous_damage_fails_every_stabilise_check():
    """CRB (aonprd, Combat, Injury and Death, Stable Characters and Recovery):
    "Characters taking continuous damage, such as from an acid arrow or a bleed effect,
    automatically fail all Constitution checks made to stabilize." Measured before the
    fix: Kesst at -1 with a claw's bleed on her rolled a 20 and lay stable while the
    wound kept bleeding her every round."""
    pc = _dying(_kesst(), -1)
    _bleed(pc, 1, "creature:wolf")
    out = pc.bleed_out(Face(20))
    assert out["outcome"] == "dying" and out.get("continuous")
    assert pc.hp == -2 and not pc.has_state("state.down.stable")
    # Stopped, the wound no longer fails the check for her.
    pc.remove_effects(kind="condition", match=lambda e: e.key == "bleed")
    assert pc.bleed_out(Face(20))["outcome"] == "stable"


def test_a_clinging_fire_is_continuous_damage_too():
    """The book's other example is acid arrow: any damage that comes again every round,
    not only the bleed condition."""
    pc = _dying(_kesst(), -1)
    _burning(pc, 2)
    assert pc.bleed_out(Face(20))["outcome"] == "dying"
    assert pc.hp == -2


def test_off_screen_a_bleeding_body_cannot_stabilise():
    s = Scene()
    s.add(_kesst())
    victim = s.add(_dying(_person("c1", "the bleeding one", hp=10), -1))
    _bleed(victim, 1, "creature:wolf")
    said = Engine(s, Face(20))._resolve_dying(victim)
    assert victim.is_dead and "bled out" in said[0]


# --- #4: healed to exactly 0 is conscious and disabled; any healing stabilises ----------

def test_a_cure_to_exactly_zero_wakes_them_disabled():
    """Audit #4, measured: at -5, healed by 5, the character was unconscious, dying and
    disabled all at once, and bled again next round. Three copies of the lift checked
    `hp > 0`; the book's 0 is "fully conscious and disabled"."""
    s = Scene()
    pc = s.add(_dying(_kesst(), -5))
    engine = Engine(s, Dice(seed=1))
    res = engine.run(engine.validate([{
        "op": "heal", "actor": "pc", "because": "a potion",
        "params": {"to": "pc", "amount": 5}}], origin="author:test"))
    assert pc.hp == 0
    assert pc.has_state("state.impaired.disabled")
    assert not pc.has_state("state.down"), pc.conditions
    assert "no longer" in res.outcomes[-1].tell and "disabled" in res.outcomes[-1].tell


def test_a_cure_that_leaves_them_negative_still_stops_the_bleeding():
    """"If any sort of healing cures the dying character of even 1 point of damage, he
    becomes stable." No path did this: a cure of 2 at -5 left her dying at -3."""
    s = Scene()
    pc = s.add(_dying(_kesst(), -5))
    engine = Engine(s, Dice(seed=1))
    engine.run(engine.validate([{
        "op": "heal", "actor": "pc", "because": "a potion",
        "params": {"to": "pc", "amount": 2}}], origin="author:test"))
    assert pc.hp == -3
    assert pc.has_state("state.down.stable") and not pc.has_state("state.down.dying")
    assert pc.bleed_out(Face(1)) is None and pc.hp == -3


def test_fast_healing_to_zero_wakes_them_too():
    """The third copy of the lift, in the periodic executor's heal branch."""
    pc = _dying(_kesst(), -1)
    pc.apply_effect(ActiveEffect(
        name="troll marrow", kind="effect", key="buff.fast-healing", source="a draught",
        origin="item:test", tags=("buff.fast-healing",),
        periodic=[{"per": "round", "heal": 1}]))
    pc.run_periodic("round", 1, Dice(seed=1))
    assert pc.hp == 0
    assert pc.has_state("state.impaired.disabled") and not pc.has_state("state.down")


# --- #14: off screen, the same roll -----------------------------------------------------

def test_off_screen_dying_uses_the_constitution_check():
    """Audit #14: `_resolve_dying` rolled a flat 10% on d100, so a Con 10 NPC at -1 who
    stabilises on a 10+ on screen (half the time) stabilised off screen one time in ten.
    A forced 20 must save him, and a forced 1 every round must kill him."""
    s = Scene()
    s.add(_kesst())
    lucky = s.add(_dying(_person("c1", "the lucky one", hp=10), -1))
    engine = Engine(s, Face(20))
    said = engine._resolve_dying(lucky)
    assert lucky.has_state("state.down.stable") and lucky.hp == -1
    assert "stabilises" in said[0]

    s2 = Scene()
    s2.add(_kesst())
    doomed = s2.add(_dying(_person("c1", "the doomed one", hp=10), -1))
    said = Engine(s2, Face(1))._resolve_dying(doomed)
    assert doomed.is_dead and "bled out" in said[0]


# --- #15: fresh damage reopens the wound ------------------------------------------------

def test_a_stable_body_hit_again_starts_dying_again():
    """Audit #15, measured: stable at -3, hit for 2, still stable at -5 — stabilising
    made a body immune to bleeding. The Disabled rule is the book's own model: a fragile
    body that takes a point "is now at -1 hit points and dying"; and Appendix 2 defines
    stable as "stopped losing hit points", which a new wound has not."""
    pc = _kesst()
    pc.hp = -3
    pc.apply_hp_state()
    pc.bleed_out(Face(20))
    assert pc.has_state("state.down.stable")
    pc.take_damage(2)
    pc.apply_hp_state()
    assert pc.hp == -5
    assert pc.has_state("state.down.dying") and not pc.has_state("state.down.stable")


def test_a_blow_fully_soaked_leaves_a_stable_body_stable():
    pc = _kesst()
    pc.hp = -3
    pc.apply_hp_state()
    pc.bleed_out(Face(20))
    pc.take_damage(0)
    pc.apply_hp_state()
    assert pc.has_state("state.down.stable") and pc.hp == -3


# --- #16: a re-applied condition with no end ------------------------------------------

def test_an_open_ended_copy_outlasts_a_timed_one():
    """Audit #16, measured: a 2-round sickened plus a disease's open-ended sickened stayed
    at 2 rounds with the payload dropped; the sickness ended while the disease held."""
    victim = _person(hp=12)
    victim.add_condition("sickened", 2, source="a stench")
    eff, _ = victim.take_affliction(
        {"kind": "disease", "dc": 30, "save": "fort",
         "effects": [{"condition": "sickened"}]},
        name="filth fever", source="a bite", origin="item:test",
        onset_rounds=0, every_rounds=14400, limit=None)
    victim.affliction_strikes(eff, Dice(seed=1))
    sick = [e for e in victim.effects if e.key == "sickened"]
    assert len(sick) == 1
    assert sick[0].rounds_left is None, "the disease's hold kept the stench's timer"
    victim.tick_effects(3)
    assert victim.has_state("state.impaired.sickened"), "it ended while the disease held"
    victim.end_affliction(eff, "cured")
    assert not victim.has_state("state.impaired.sickened"), (
        "the payload that ties it to the disease was dropped, so the cure left it")


def test_an_open_ended_copy_does_not_tie_a_standing_one_to_the_disease():
    """The other half: a condition already held with no end, by something that is not
    the affliction, is not handed to the affliction to take away when it is cured."""
    victim = _person(hp=12)
    victim.add_condition("sickened", source="a curse")
    eff, _ = victim.take_affliction(
        {"kind": "disease", "dc": 30, "save": "fort",
         "effects": [{"condition": "sickened"}]},
        name="filth fever", source="a bite", origin="item:test",
        onset_rounds=0, every_rounds=14400, limit=None)
    victim.affliction_strikes(eff, Dice(seed=1))
    victim.end_affliction(eff, "cured")
    assert victim.has_state("state.impaired.sickened")


# --- smaller finding: bleed takes the worse, whatever order it arrived in ---------------

def _bleed(actor, amount, source, *, stacking="refresh", origin=""):
    actor.apply_effect(ActiveEffect(
        name="Bleed", kind="condition", key="bleed", source=source,
        origin=origin or source, stacking=stacking,
        tags=("state.wound.bleeding",),
        periodic=[{"per": "round", "damage": amount, "damage_type": "untyped"}]))


def test_two_bleeds_from_different_sources_take_the_worse():
    """Audit, smaller finding: three writers had three rules, and which one won depended
    on the order they ran. A flask's 1 and a claw's 3 bled 4 a round; the book takes the
    worse, 3."""
    victim = _person(hp=40)
    _bleed(victim, 1, "item:demon-ichor")
    _bleed(victim, 3, "creature:wolf")
    victim.run_periodic("round", 1, Dice(seed=1))
    assert victim.hp == 37


def test_wounding_hits_add_up_and_then_compete_as_one_bleed():
    """Wounding says otherwise for itself: three hits from the one blade bleed 3. Against
    a claw's 2 from another source, the blade's 3 is the worse and the only one that
    runs — in either order."""
    for order in ("blade first", "claw first"):
        victim = _person(hp=40)
        if order == "claw first":
            _bleed(victim, 2, "creature:wolf")
        for n in range(3):
            _bleed(victim, 1, f"property:wounding#{n + 1}", stacking="stack",
                   origin="property:wounding")
        if order == "blade first":
            _bleed(victim, 2, "creature:wolf")
        victim.run_periodic("round", 1, Dice(seed=1))
        assert victim.hp == 37, order


def test_a_rider_bleed_is_judged_against_the_bleed_that_runs():
    """`_rider_bleed` compared its dice with each bleed one at a time, so three 1-point
    wounding bleeds (3 a round together) were each "less" than a 1d4 claw (2.5) and all
    three were stripped off for it."""
    s = Scene()
    s.add(_kesst())
    wolf = s.add(instantiate("thug", scene=s, name="the wolf"))
    victim = s.add(_person("c9", "the victim", hp=40))
    for n in range(3):
        _bleed(victim, 1, f"property:wounding#{n + 1}", stacking="stack",
               origin="property:wounding")
    engine = Engine(s, Dice(seed=1))
    out = engine._rider_bleed(None, wolf, victim, {"amount": "1d4"}, "creature:wolf", {})
    assert "no worse" in out[0]["tell"]
    assert sum(1 for e in victim.effects if e.key == "bleed") == 3
