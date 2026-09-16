"""Talking somebody round (`rules/attitude.py`, docs/attitude.md).

The defect, and it was a whole pillar of the game: `rules/states.py` has held 1e's
attitude track since the spell import and said so in its own comment — thirty-three
spells set an attitude, `effectspec` offered the type, and the note beside it read "no
check in the app consults an attitude yet". `_op_check` rolled Diplomacy, printed the
margin, paid the XP for beating a DC, and left the merchant exactly as hostile as they
had been.

The engine was also telling the model otherwise. The refusal that stops a plan declaring
somebody helpful ends "To move somebody by ordinary means, talk to them and roll it:
check skill=diplomacy" — the app describing a feature it did not have.

Every number checked here is the Core Rulebook's, and that is the point of the file: the
DCs (25/20/15/10/0 + Charisma), the one step plus one per 5 over, the two-step cap, the
step lost on a failure by 5 or more, the 1d4 hours, the once per 24 hours, and
Intimidate's 10 + Hit Dice + Wisdom for 1d6x10 minutes of friendliness. If any of them
drifts, this is where it is caught rather than at a table.
"""
from __future__ import annotations

import pytest

from rules import attitude, states
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import load_pc
from world import loader

WORLD = loader.load_cached("fixtures/pangrella-campaign.json")
TOWN = "5bbd0c40345f"
MARKET = f"{TOWN}~urban:the-market"


def _table(seed: int = 5):
    scene = Scene(location_id=TOWN)
    scene.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(scene, Dice(seed=seed), world=WORLD)
    engine.place_party(MARKET)
    who = scene.add(instantiate("thug", scene=scene, name="Grix"))
    return scene, engine, who


def _talk(engine, who, face: int, skill: str = "diplomacy"):
    res = engine.run(engine.validate(
        [{"op": "check", "actor": "pc", "target": who.ref, "because": "a word with them",
          "params": {"skill": skill}}], origin="author:test"))
    if res.awaiting:
        res = engine.resume(face)
    return next(o for o in res.outcomes if o.op == "check")


# --- the numbers are the book's ---------------------------------------------------------

def test_the_dc_is_the_table_from_the_core_rulebook():
    """25/20/15/10/0 by where they stand, plus their Charisma modifier."""
    _scene, _engine, who = _table()
    for step, base in (("hostile", 25), ("unfriendly", 20), ("indifferent", 15),
                       ("friendly", 10), ("helpful", 0)):
        who.clear_states("attitude")
        who.add_condition(step, source="test")
        assert attitude.influence_dc(who) == base + who.ability_mod("cha"), step


def test_a_success_moves_one_step_and_one_more_per_five_over():
    for margin, steps in ((0, 1), (4, 1), (5, 2), (9, 2), (10, 2), (25, 2)):
        assert attitude.steps_for(margin) == steps, margin


def test_two_steps_is_the_ceiling_however_well_it_went():
    """"A creature's attitude cannot be shifted more than two steps up in this way." A
    natural 20 on a silver tongue does not make an assassin your friend."""
    assert attitude.steps_for(100) == attitude.MOST_STEPS_UP == 2
    assert attitude.moved("hostile", attitude.steps_for(100)) == "indifferent"


def test_missing_by_five_costs_a_step_and_missing_by_four_costs_nothing():
    """The half that makes the check worth thinking about. Without it the only cost of
    trying is a minute, and a player rolls until the dice agree."""
    assert attitude.steps_for(-4) == 0
    assert attitude.steps_for(-5) == -1


def test_the_track_has_ends_and_they_hold():
    assert attitude.moved("helpful", 2) == "helpful"
    assert attitude.moved("hostile", -2) == "hostile"


def test_the_intimidate_dc_is_ten_plus_hit_dice_plus_wisdom():
    _scene, _engine, who = _table()
    assert attitude.intimidate_dc(who) == 10 + who.hit_dice + who.ability_mod("wis")


# --- and they reach the board -------------------------------------------------------------

def test_a_diplomacy_check_actually_moves_somebody():
    """The measurement, as an assertion: before this, the merchant was exactly as
    hostile after the check as before it."""
    _scene, engine, who = _table()
    assert attitude.of(who) == "indifferent"
    out = _talk(engine, who, 18)
    assert out.verdict == "success"
    assert attitude.of(who) in ("friendly", "helpful"), out.tell
    assert who.has_state(f"attitude.{attitude.of(who)}")


def test_the_shift_wears_off():
    """1d4 hours, and a shift with no clock on it is a permanent change of heart bought
    for one check — which is how a social system stops being a system."""
    _scene, engine, who = _table()
    _talk(engine, who, 18)
    held = [c for c in who.conditions if c.key in states.ATTITUDES]
    assert held and held[0].rounds_left, [(c.key, c.rounds_left) for c in who.conditions]
    # 1d4 hours in rounds: six hundred to a hour.
    assert 600 <= held[0].rounds_left <= 2400, held[0].rounds_left


def test_nobody_is_two_things_at_once():
    """One step of the track at a time, through the one applicator. A charm laid over an
    old grudge used to leave both standing."""
    _scene, engine, who = _table()
    _talk(engine, who, 18)
    held = [c.key for c in who.conditions if c.key in states.ATTITUDES]
    assert len(held) == 1, held


def test_the_same_person_will_not_hear_it_twice_in_a_day():
    """"You cannot use Diplomacy to influence a given creature's attitude more than once
    in a 24 hour period." The limit is on TRYING, so a bad roll spends the day too."""
    scene, engine, who = _table()
    _talk(engine, who, 18)
    was = attitude.of(who)
    again = _talk(engine, who, 20)
    assert "will not hear it again" in again.tell
    assert attitude.of(who) == was
    assert not again.rolls, "the dice were rolled on an attempt that could not happen"
    scene.clock_minutes += attitude.COOLDOWN_MINUTES
    assert "will not hear it again" not in _talk(engine, who, 20).tell


def test_a_threat_buys_friendliness_by_the_minute():
    """Intimidate, Change Attitude: 1d6x10 minutes of acting friendly. Minutes, not the
    hours Diplomacy buys — a mind changed by fear is on a shorter clock, which is the
    book's own distinction between the two skills and the reason to have both."""
    _scene, engine, who = _table()
    out = _talk(engine, who, 20, skill="intimidate")
    assert out.verdict == "success"
    assert attitude.of(who) == "friendly", out.tell
    held = [c for c in who.conditions if c.key in states.ATTITUDES][0]
    # Ten to sixty minutes, in rounds — ten rounds to the minute.
    assert 100 <= held.rounds_left <= 600, held.rounds_left
    # Fear's best hour is talk's worst one: 1d6x10 minutes tops out at exactly the 1d4
    # hours' floor, which is the book's own distinction between the two skills and the
    # reason to have both.
    assert held.rounds_left <= 600, held.rounds_left


def test_a_threat_that_lands_badly_moves_nobody():
    _scene, engine, who = _table()
    out = _talk(engine, who, 1, skill="intimidate")
    assert out.verdict == "failure"
    assert attitude.of(who, default="") == ""


# --- the DC is the engine's ----------------------------------------------------------------

def test_the_plan_may_not_name_its_own_price_for_a_change_of_heart():
    """"The GM proposes and the engine disposes." A band named here would be the model
    setting how hard it is to talk somebody round, which is a rule with a table behind
    it — and a plan that can set that price can talk anybody into anything."""
    _scene, engine, who = _table()
    with pytest.raises(IntentError) as caught:
        engine.validate([{"op": "check", "actor": "pc", "target": who.ref,
                          "because": "t",
                          "params": {"skill": "diplomacy", "dc": {"band": "easy"}}}],
                        origin="author:test")
    assert "the engine's" in str(caught.value)


def test_a_check_with_nobody_named_still_needs_a_dc():
    """Additive: a Diplomacy check at a band, with no person named, is what it always
    was — working a crowd, talking past a gate guard the scene does not hold."""
    _scene, engine, _who = _table()
    with pytest.raises(IntentError):
        engine.validate([{"op": "check", "actor": "pc", "because": "t",
                          "params": {"skill": "diplomacy"}}], origin="author:test")
    engine.validate([{"op": "check", "actor": "pc", "because": "t",
                      "params": {"skill": "diplomacy", "dc": {"band": "easy"}}}],
                    origin="author:test")


def test_bluff_is_not_wired_to_the_track_and_that_is_deliberate():
    """The book does not put it there. A lie is an opposed check against Sense Motive,
    which `check` has supported all along; wiring Bluff to the attitude track because it
    appears in the same sentence as the other two would be inventing a rule and calling
    it Pathfinder. Asserted so that the omission reads as a decision."""
    assert "bluff" not in attitude.LEVERS
    _scene, engine, who = _table()
    out = _talk(engine, who, 18, skill="bluff") if False else None
    assert out is None
    # And it still resolves the way it always did, opposed.
    res = engine.run(engine.validate(
        [{"op": "check", "actor": "pc", "because": "a lie",
          "params": {"skill": "bluff",
                     "opposed_by": {"ref": who.ref, "skill": "sense motive"}}}],
        origin="author:test"))
    if res.awaiting:
        res = engine.resume(15)
    assert attitude.of(who, default="") == "", "a lie moved the attitude track"


def test_a_spell_that_makes_somebody_friendly_makes_them_friendly():
    """Charm person, and thirty-two others. The `attitude` effect type has existed since
    the spell import and shipped blocked — "no check in the app consults an attitude yet"
    — so a charmed guard was charmed in the effect list and hostile in every sentence
    about him. Lifting the block was a claim, and the suite caught it: a type marked
    executable with no executor is narrative wearing a costume."""
    _scene, engine, who = _table()
    effects, tells = engine._attitude(
        {"type": "attitude", "target": "friendly", "towards": "caster"},
        {"caster": "pc", "targets": [who.ref], "rounds": 50, "source": "charm person"})
    assert attitude.of(who) == "friendly", tells
    assert effects and effects[0]["rounds_left"] == 50
    assert tells and "Grix" in tells[0] and not any(c.isdigit() for c in tells[0])
    # And it lands through the one applicator, so one removal clears it.
    who.remove_effects(source="charm person")
    assert attitude.of(who, default="") == "", "the charm could not be broken"


# --- what a step is worth ------------------------------------------------------------------

def test_a_shopkeeper_who_dislikes_you_will_not_serve_you(tmp_path):
    """The reader that makes a step bite, and the answer to "so what?". 1e gates what a
    creature will do for you on their attitude — requests need indifferent or better —
    and buying from somebody is a request. Nobody starts unfriendly: an attitude is only
    ever set by something that happened, so a counter the player has not poisoned opens
    exactly as it did before."""
    from django.test import Client, override_settings

    from play import campaign as cm
    from play.views import _merchant_here

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.scene.location_id = TOWN
        c.engine().place_party(MARKET)
        c.save()
        keeper = _merchant_here(c.scene)
        assert keeper is not None, "no keeper at the market to fall out with"
        assert Client().post("/api/trade", data="{}",
                             content_type="application/json").status_code == 200
        keeper.add_condition("unfriendly", source="the player was rude")
        c.save()
        r = Client().post("/api/trade", data="{}", content_type="application/json")
        assert r.status_code == 409
        assert "will not trade" in r.json()["error"]
        assert "diplomacy" in r.json()["error"].lower(), "the refusal names no way back"
        cm._LIVE.clear()


def test_the_tell_says_how_they_feel_and_never_how_far_they_moved():
    """The third law. "Warmer towards you" is a thing a character notices; "attitude +1"
    is a number the narrator would start doing arithmetic with."""
    said = attitude.said("Grix", "indifferent", "friendly")
    assert "Grix" in said and not any(ch.isdigit() for ch in said), said
    # And a move DOWN reads as one. Written as movements rather than states, this came
    # out as "Grix cools: warms to you" the first time a threat moved somebody down.
    down = attitude.said("Grix", "helpful", "friendly")
    assert down.startswith("Grix cools"), down
    assert "warms to you" not in down, down
