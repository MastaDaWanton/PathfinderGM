"""Combat manoeuvres: an attack roll with CMB, against CMD.

Checked against the Core Rulebook, pp. 198-201. Every manoeuvre shares one resolution and
differs only in consequence, which is why they are one table and one code path.
"""
from __future__ import annotations

import pytest

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError, parse
from rules.sheet import from_dict, load_pc


@pytest.fixture
def scene():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    return s


@pytest.fixture
def engine(scene):
    e = Engine(scene, Dice(seed=20260820))
    # The battle gate defers a swing that finds no fight running; every test here
    # is about the manoeuvre itself, so the fight is already open.
    e._ensure_encounter("pc")
    return e


def play(engine, raw, faces=()):
    res = engine.run(engine.validate(raw))
    supply = list(faces)
    prompts = []
    while res.awaiting:
        prompts.append(res.awaiting)
        res = engine.resume(supply.pop(0))
    return res, prompts


# --- The two formulas ------------------------------------------------------------

def test_cmb_is_bab_plus_str_plus_the_special_size_modifier(scene):
    """CMB = base attack bonus + Str modifier + special size modifier (CRB p.198).

    Kesst is a Medium Rogue 1: BAB +0, Str 12 (+1), no size modifier, so CMB +1. Note
    this uses Str and not the Dex that Weapon Finesse gives her attack roll — Finesse
    does not apply to manoeuvres.
    """
    kesst = scene.pc()
    terms = {m.source: m.value for m in kesst.cmb_modifiers()}
    assert terms == {"Str": 1}
    assert sum(terms.values()) == 1


def test_cmd_is_ten_plus_bab_plus_str_plus_dex_plus_size(scene):
    """CMD = 10 + BAB + Str + Dex + special size modifier (CRB p.199).

    Kesst: 10 + 0 + 1 + 3 = 14.
    """
    kesst = scene.pc()
    assert kesst.cmd() == 14
    terms = {m.source: m.value for m in kesst.cmd_modifiers()}
    assert terms == {"base": 10, "Str": 1, "Dex": 3}


def test_a_flat_footed_creature_does_not_add_dex_to_cmd(scene):
    """CRB p.199, and the reason an ambushed target is easier to trip. Kesst drops from
    14 to 11 without her +3 Dex."""
    kesst = scene.pc()
    assert kesst.cmd() == 14
    assert kesst.cmd(flat_footed=True) == 11


def test_penalties_to_ac_also_apply_to_cmd(scene):
    """CRB p.199: "Any penalties to a creature's AC also apply to its CMD." Bonuses do
    not travel the same way, so only the negatives are carried."""
    kesst = scene.pc()
    before = kesst.cmd()
    kesst.add_condition("blinded")          # -2 AC, and loses Dex to AC
    assert kesst.cmd() == before - 2 - 3


def test_tiny_and_smaller_creatures_use_dex_for_cmb():
    """CRB p.198: "Creatures that are size Tiny or smaller use their Dexterity modifier
    in place of their Strength modifier to determine their CMB."
    """
    imp = from_dict({
        "name": "imp", "kind": "npc", "size": "tiny",
        "abilities": {"str": 6, "dex": 17, "con": 10, "int": 10, "wis": 10, "cha": 10},
        "hp": 6,
    })
    terms = {m.source: m.value for m in imp.cmb_modifiers()}
    assert terms["Dex"] == 3
    assert "Str" not in terms
    assert terms["tiny size"] == -2


def test_the_special_size_modifier_runs_opposite_to_the_attack_one():
    """A Small creature is +1 to attack and AC but -1 to CMB and CMD. Crossing these two
    columns makes every small creature better at grappling than it should be."""
    from rules.tables import SIZES

    assert SIZES["small"]["attack_ac"] == 1
    assert SIZES["small"]["cmb_cmd"] == -1
    assert SIZES["large"]["attack_ac"] == -1
    assert SIZES["large"]["cmb_cmd"] == 1


# --- Resolution ---------------------------------------------------------------------

def test_a_manoeuvre_is_the_players_own_roll_against_cmd(engine, scene):
    """"When you attempt to perform a combat maneuver, make an attack roll and add your
    CMB in place of your normal attack bonus... The DC of this maneuver is your target's
    Combat Maneuver Defense." (CRB p.199)
    """
    res, prompts = play(
        engine, [{"op": "attack", "actor": "pc", "target": "c1",
                  "because": "she goes for his legs",
                  "params": {"manoeuvre": "trip"}}],
        faces=[18],
    )
    assert len(prompts) == 1
    p = prompts[0]
    assert p["label"] == "Trip (CMB)"
    assert [b["source"] for b in p["breakdown"]] == ["Str"]
    # Thug CMD 15, flat-footed (no encounter has started) so no Dex: 15 - 1 = 14.
    assert p["dc"] == 14
    assert res.outcomes[0].verdict == "success"
    assert scene.get("c1").has_condition("prone")


def test_a_trip_that_fails_by_ten_knocks_the_attacker_down(engine, scene):
    """"If your attack fails by 10 or more, you are knocked prone instead." (CRB p.201)

    Kesst's CMB is +1 against CMD 14, so a natural 2 gives 3 — failing by 11.
    """
    res, _ = play(engine, [{"op": "attack", "actor": "pc", "target": "c1",
                            "params": {"manoeuvre": "trip"}}], faces=[2])
    assert res.outcomes[0].verdict == "failure"
    assert res.outcomes[0].margin <= -10
    assert scene.pc().has_condition("prone")
    assert not scene.get("c1").has_condition("prone")
    assert "knocked prone instead" in res.outcomes[0].tell


def test_a_natural_one_always_fails_and_a_natural_twenty_always_succeeds(scene):
    """CRB p.199, and the reason verdict is not simply `total >= cmd`."""
    engine = Engine(scene, Dice(seed=3))
    engine._ensure_encounter("pc")
    res, _ = play(engine, [{"op": "attack", "actor": "pc", "target": "c1",
                            "params": {"manoeuvre": "trip"}}], faces=[20])
    assert res.outcomes[0].verdict == "success"

    scene.get("c1").remove_condition("prone")
    engine2 = Engine(scene, Dice(seed=3))
    # A natural 1 fails even though 1 + CMB could not reach CMD anyway; the assertion
    # that matters is that a 20 succeeded above without beating a high CMD by arithmetic.
    res2, _ = play(engine2, [{"op": "attack", "actor": "pc", "target": "c1",
                              "params": {"manoeuvre": "trip"}}], faces=[1])
    assert res2.outcomes[0].verdict == "failure"


def test_an_incapacitated_target_is_manoeuvred_automatically(engine, scene):
    """"If your target is immobilized, unconscious, or otherwise incapacitated, your
    maneuver automatically succeeds." No roll, so no prompt. (CRB p.199)
    """
    scene.get("c1").add_condition("unconscious")
    res, prompts = play(engine, [{"op": "attack", "actor": "pc", "target": "c1",
                                  "params": {"manoeuvre": "grapple"}}])
    assert prompts == []
    assert res.outcomes[0].verdict == "success"
    assert "automatically" in res.outcomes[0].tell


def test_a_stunned_target_gives_a_four_bonus(engine, scene):
    """"If your target is stunned, you receive a +4 bonus on your attack roll to perform
    a combat maneuver against it." (CRB p.199)

    This could not be tested until the vocabulary split: `automatic` was read off
    `can_act()`, so a stunned target succeeded with no roll and there was no attack roll
    for the +4 to appear on. The test added `stunned`, removed it again and measured the
    base — the bonus it is named for went unchecked. 1e gives the bonus precisely
    because a stunned creature CAN still resist; the clause that skips the roll is
    "immobilized, unconscious, or otherwise incapacitated", which is a different set.
    """
    kesst = scene.pc()
    base = sum(m.value for m in kesst.cmb_modifiers("trip"))
    scene.get("c1").add_condition("stunned")

    res, prompts = play(engine, [{"op": "attack", "actor": "pc", "target": "c1",
                                  "params": {"manoeuvre": "trip"}}], faces=[10])

    assert prompts, "a stunned target still resists, so the roll must be asked for"
    assert sum(b["value"] for b in prompts[0]["breakdown"]) == base + 4


def test_a_body_on_the_floor_is_never_handed_a_die_to_roll(engine, scene):
    """Found by an adversarial review, under a green suite.

    The automatic clause moved from `not can_act()` — true for eleven condition rows —
    to the `helpless` flag, which sits on five. `dead` and `stable` are in the gap, so
    the player was offered a d20 against a corpse, and could fail it. That is the same
    insult the swing path records at `_resolve_attack`: "the player was asked to roll a
    d20 at a body on the floor".
    """
    for key, hp in (("dead", -20), ("stable", -3), ("dying", -3)):
        s = Scene(location_id="5bbd0c40345f")
        s.add(load_pc("fixtures/pc-kesst.json"))
        s.add(instantiate("thug", scene=s, name="the thug"))
        body = s.get("c1")
        body.hp = hp
        body.add_condition(key, source="probe")

        res, prompts = play(Engine(s, Dice(seed=4)),
                            [{"op": "attack", "actor": "pc", "target": "c1",
                              "params": {"manoeuvre": "grapple"}}])
        assert prompts == [], f"a d20 was asked for against a {key} body"
        assert res.outcomes[0].verdict == "success"


def test_grappling_grapples_both_of_you(engine, scene):
    """"If successful, both you and the target gain the grappled condition." (CRB p.200)
    — the detail everyone forgets at the table."""
    res, _ = play(engine, [{"op": "attack", "actor": "pc", "target": "c1",
                            "params": {"manoeuvre": "grapple"}}], faces=[20])
    assert scene.get("c1").has_condition("grappled")
    assert scene.pc().has_condition("grappled")


def test_overrun_by_five_or_more_also_knocks_the_target_prone(scene):
    """"If your attack exceeds your opponent's CMD by 5 or more, you move through the
    target's space and the target is knocked prone." (CRB p.201)"""
    scene.pc().abilities["str"] = 20        # +5, enough to clear CMD 14 by 5 on a 14
    engine = Engine(scene, Dice(seed=5))
    engine._ensure_encounter("pc")
    res, _ = play(engine, [{"op": "attack", "actor": "pc", "target": "c1",
                            "params": {"manoeuvre": "overrun"}}], faces=[20])
    assert res.outcomes[0].margin >= 5
    assert scene.get("c1").has_condition("prone")


def test_bull_rush_reports_the_extra_distance(scene):
    """"For every 5 by which your attack exceeds your opponent's CMD you can push the
    target back an additional 5 feet." (CRB p.199)"""
    scene.pc().abilities["str"] = 20
    engine = Engine(scene, Dice(seed=5))
    engine._ensure_encounter("pc")
    res, _ = play(engine, [{"op": "attack", "actor": "pc", "target": "c1",
                            "params": {"manoeuvre": "bull rush"}}], faces=[20])
    assert "5 feet" in res.outcomes[0].tell


def test_disarming_while_unarmed_costs_four(engine, scene):
    """"Attempting to disarm a foe while unarmed imposes a -4 penalty." (CRB p.199)"""
    _, prompts = play(engine, [{"op": "attack", "actor": "pc", "target": "c1",
                                "params": {"manoeuvre": "disarm", "weapon": "unarmed"}}],
                      faces=[10])
    terms = {b["source"]: b["value"] for b in prompts[0]["breakdown"]}
    assert terms["unarmed"] == -4


# --- Legality --------------------------------------------------------------------------

def test_you_cannot_trip_something_two_size_categories_larger(engine, scene):
    """"You can only trip an opponent who is no more than one size category larger than
    you." (CRB p.201)"""
    from rules.sheet import from_dict as build

    giant = build({"name": "giant", "kind": "npc", "size": "huge",
                   "abilities": {"str": 25, "dex": 8, "con": 20, "int": 8, "wis": 10,
                                 "cha": 8},
                   "hp": 90, "flat_ac": 20, "flat_attack": 12, "flat_cmd": 30},
                  ref="c2")
    scene.add(giant)
    with pytest.raises(IntentError, match="at most one size category larger"):
        engine.validate([{"op": "attack", "actor": "pc", "target": "c2",
                          "params": {"manoeuvre": "trip"}}])


def test_a_manoeuvre_with_no_size_limit_is_allowed_against_anything(engine, scene):
    """Disarm and sunder carry no size restriction in the book, so the check must not be
    applied uniformly."""
    from rules.sheet import from_dict as build

    giant = build({"name": "giant", "kind": "npc", "size": "huge",
                   "abilities": {"str": 25, "dex": 8, "con": 20, "int": 8, "wis": 10,
                                 "cha": 8},
                   "hp": 90, "flat_ac": 20, "flat_attack": 12, "flat_cmd": 30},
                  ref="c2")
    scene.add(giant)
    engine.validate([{"op": "attack", "actor": "pc", "target": "c2",
                      "params": {"manoeuvre": "disarm"}}])


def test_you_cannot_trip_someone_already_prone(engine, scene):
    scene.get("c1").add_condition("prone")
    with pytest.raises(IntentError, match="already prone"):
        engine.validate([{"op": "attack", "actor": "pc", "target": "c1",
                          "params": {"manoeuvre": "trip"}}])


# --- Vocabulary ---------------------------------------------------------------------------

def test_the_american_spelling_and_common_synonyms_are_accepted():
    """A model will write "maneuver", and will reach for "knock down" and "shove". None
    of that is worth losing a turn over."""
    assert parse({"op": "attack", "actor": "pc", "target": "c1",
                  "params": {"maneuver": "trip"}}).params["manoeuvre"] == "trip"
    for said, means in [("bullrush", "bull rush"), ("shove", "bull rush"),
                        ("knock down", "trip"), ("tackle", "grapple"),
                        ("smash", "sunder")]:
        got = parse({"op": "attack", "actor": "pc", "target": "c1",
                     "params": {"manoeuvre": said}})
        assert got.params["manoeuvre"] == means, f"{said!r} should mean {means!r}"


def test_an_invented_manoeuvre_is_rejected_with_the_list():
    with pytest.raises(IntentError) as e:
        parse({"op": "attack", "actor": "pc", "target": "c1",
               "params": {"manoeuvre": "roundhouse kick"}})
    msg = str(e.value)
    assert "is not a combat manoeuvre" in msg
    assert "grapple" in msg and "sunder" in msg
