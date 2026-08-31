"""Attacks of opportunity: things that happen on somebody else's turn.

Everything the engine did before this was somebody's own action, in their own turn,
proposed by the GM. A reaction is none of those. It belongs to one creature, fires during
another creature's action, and nobody proposes it — it is *owed*, by the rules, the moment
its trigger happens. The GM does not get a say in whether an attack of opportunity occurs.

`docs/intent-protocol.md` listed these under "deliberately not in v1" because `run()` had
no way to suspend one intent to resolve another. It turns out it did: `_drive` works a
queue, and a reaction is intents spliced in *front* of the one that provoked them. They
resolve through the ordinary machinery, which is why a player-taken attack of opportunity
suspends for a dice roll without a line of special handling.

The measurement that matters most here is order. An attack of opportunity provoked by
movement lands as the creature leaves the square, not after it arrives — so if the blow
drops them, they never get there. A first pass that resolved reactions after the triggering
intent looked identical in every test except that one, and that one is the point.
"""
from __future__ import annotations

import pytest

from rules import reactions
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.grid import Grid
from rules.sheet import load_pc


def board(pc_at=(5, 5), thug_at=(6, 5), fighting=True, **terrain):
    s = Scene(location_id="5bbd0c40345f", grid=Grid(20, 20, **terrain))
    s.add(load_pc("fixtures/pc-kesst.json"), at=pc_at)
    s.add(instantiate("thug", scene=s, name="the thug"), at=thug_at)
    s.sides = {"us": ["pc"], "them": ["c1"]}
    if fighting:
        s.initiative = [("pc", 20), ("c1", 10)]
        s.turn = 0
    return s, Engine(s, Dice(seed=7))


def run_move(engine, ref, square, zone="far"):
    return engine.run(engine.validate([
        {"op": "move", "actor": ref, "because": "moving",
         "params": {"zone": zone, "square": list(square)}}]))


def finish(engine, res, faces=(18, 5, 6, 4, 3, 2)):
    """Drive a suspended resolution to the end. A PC attack can suspend three times —
    to-hit, crit confirmation, damage — and the reaction is a PC attack like any other."""
    for face in faces:
        if res.status == "complete":
            break
        res = engine.resume(face=face)
    return res


# --- what provokes -----------------------------------------------------------------------

def test_leaving_a_threatened_square_provokes():
    s, e = board()
    res = run_move(e, "pc", (5, 9))
    assert [o.op for o in res.outcomes] == ["attack", "move"]
    assert s.reacted == {"c1:attack_of_opportunity": 1}


def test_the_swing_lands_before_the_move_not_after():
    """The ordering the whole design turns on. Resolving reactions after the triggering
    intent passes every other test in this file and fails only this one."""
    s, e = board()
    res = run_move(e, "pc", (5, 9))
    assert res.outcomes[0].op == "attack"
    assert res.outcomes[1].op == "move"


def test_a_five_foot_step_provokes_nothing():
    """"You can move 5 feet in any round when you don't perform any other kind of
    movement" is the entire point of the step. Treating it as a move makes the safest
    option in the game the most dangerous one."""
    s, e = board()
    res = run_move(e, "pc", (5, 6), zone="engaged")
    assert [o.op for o in res.outcomes] == ["move"]
    assert s.reacted == {}


def test_walking_into_reach_does_not_provoke():
    """Entering a threatened square is free; leaving one is not. Getting this backwards
    makes closing to melee cost a hit every single time."""
    s, e = board(pc_at=(1, 5), thug_at=(6, 5))
    res = run_move(e, "pc", (5, 5), zone="engaged")
    assert [o.op for o in res.outcomes] == ["move"]


def test_moving_from_one_threatened_square_to_another_still_provokes():
    """You left a threatened square. Circling an opponent is not free."""
    s, e = board(pc_at=(5, 5), thug_at=(6, 5))
    res = run_move(e, "pc", (7, 7), zone="engaged")
    assert res.outcomes[0].op == "attack"


def test_a_creature_that_cannot_act_takes_no_swing():
    s, e = board()
    s.actors["c1"].add_condition("unconscious")
    res = run_move(e, "pc", (5, 9))
    assert [o.op for o in res.outcomes] == ["move"]


def test_a_creature_that_cannot_swing_takes_no_swing_even_though_it_can_move():
    """Found by an adversarial review, under a green suite.

    A spliced reaction goes straight to resolution and never passes `validate`, so this
    is the only gate it meets — and it asked the general question, `can_act()`. The
    moment the vocabulary correctly gave a nauseated creature its move action back, that
    same answer handed it the attack of opportunity as well, and it swung.

    1e is explicit: a nauseated creature may take "a single move action" and nothing
    else. The question a reaction asks is about attacking, not about acting.
    """
    s, e = board()
    s.actors["c1"].add_condition("nauseated", source="bad meat")
    assert s.actors["c1"].can_act(), "it may still move — that is the whole point"

    res = run_move(e, "pc", (5, 9))
    assert [o.op for o in res.outcomes] == ["move"], "a nauseated creature swung"


def test_allies_do_not_provoke_each_other():
    s, e = board()
    s.sides = {"us": ["pc", "c1"]}
    res = run_move(e, "pc", (5, 9))
    assert [o.op for o in res.outcomes] == ["move"]


def test_nothing_provokes_on_a_scene_with_no_map():
    """A reaction on an unmeasurable battlefield would be the engine inventing geometry.
    Zones do not carry enough to say whether a threatened square was left."""
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    s.initiative, s.turn = [("pc", 20), ("c1", 10)], 0
    e = Engine(s, Dice(seed=7))
    res = e.run(e.validate([{"op": "move", "actor": "pc", "because": "away",
                             "params": {"zone": "far"}}]))
    assert [o.op for o in res.outcomes] == ["move"]


def test_nothing_provokes_outside_an_encounter():
    """Walking across a village past a stranger is not a combat manoeuvre."""
    s, e = board(fighting=False)
    res = run_move(e, "pc", (5, 9))
    assert [o.op for o in res.outcomes] == ["move"]


def test_reach_lets_a_bigger_creature_swing_from_further_out():
    """An ogre threatens ten feet. Somebody leaving a square two away is still leaving a
    square it threatened."""
    s, e = board(pc_at=(5, 5), thug_at=(7, 5))
    assert [o.op for o in run_move(e, "pc", (5, 9)).outcomes] == ["move"]

    s, e = board(pc_at=(5, 5), thug_at=(7, 5))
    s.actors["c1"].size = "large"
    assert run_move(e, "pc", (5, 9)).outcomes[0].op == "attack"


# --- the allowance -----------------------------------------------------------------------

def test_one_attack_of_opportunity_a_round():
    s, e = board()
    run_move(e, "pc", (5, 9))
    # Straight back into reach, then out again — the second swing is not owed.
    s.positions["pc"] = (5, 5)
    res = run_move(e, "pc", (1, 5))
    assert [o.op for o in res.outcomes] == ["move"]
    assert s.reacted == {"c1:attack_of_opportunity": 1}


def test_combat_reflexes_buys_one_per_point_of_dexterity():
    """"plus one additional attack of opportunity for every point of Dexterity bonus"."""
    s, _ = board()
    thug = s.actors["c1"]
    assert reactions.budget_for(thug) == 1
    thug.feats = ["combat reflexes"]
    thug.abilities["dex"] = 18
    assert reactions.budget_for(thug) == 5


def test_a_negative_dexterity_still_leaves_you_one():
    """A subtraction rather than a maximum would give a clumsy creature with the feat
    *fewer* attacks of opportunity than one without it."""
    s, _ = board()
    thug = s.actors["c1"]
    thug.feats = ["combat reflexes"]
    thug.abilities["dex"] = 6
    assert reactions.budget_for(thug) == 1


def test_the_allowance_refills_at_the_top_of_the_round():
    """At the top of the round, not on your own turn: it is what you may do while other
    people are acting."""
    s, e = board()
    run_move(e, "pc", (5, 9))
    assert s.reacted
    s.advance_turn()                                     # pc -> c1
    s.advance_turn()                                     # c1 -> pc, new round
    assert s.round == 1
    assert s.reacted == {}


def test_an_exhausted_allowance_is_silence_not_an_error():
    """A spent allowance is not something the GM can repair. Raising here would abort the
    mover's whole intent list over somebody else's used-up resource."""
    s, e = board()
    s.reacted["c1:attack_of_opportunity"] = 9
    res = run_move(e, "pc", (5, 9))
    assert [o.op for o in res.outcomes] == ["move"]
    assert s.positions["pc"] == (5, 9)


# --- the swing itself --------------------------------------------------------------------

def test_an_attack_of_opportunity_is_a_single_swing():
    """Inheriting the attacker's iteratives would turn a high-level fighter's threatened
    square into four free attacks a round."""
    s, e = board()
    fired = e._reactions_before({"op": "move", "actor": "pc",
                                 "params": {"zone": "far", "square": (5, 9)}})
    assert fired[0]["params"]["full_attack"] is False
    assert fired[0]["params"]["reaction"] == "attack_of_opportunity"


def test_an_npcs_swing_stays_hidden_and_the_players_does_not():
    s, e = board()
    fired = e._reactions_before({"op": "move", "actor": "pc",
                                 "params": {"zone": "far", "square": (5, 9)}})
    assert fired[0]["visibility"] == "hidden"            # the thug swings at the PC

    s, e = board()
    fired = e._reactions_before({"op": "move", "actor": "c1",
                                 "params": {"zone": "far", "square": (10, 5)}})
    assert fired[0]["visibility"] == "player"            # the PC swings at the thug


def test_the_player_rolls_their_own_attack_of_opportunity():
    """It goes through `_drive` like any other intent, so the suspend machinery that
    already existed for the PC's own attacks carries it with no special handling."""
    s, e = board()
    res = run_move(e, "c1", (10, 5))
    assert res.status == "awaiting_player_roll"
    assert "rapier" in res.awaiting["label"]

    res = finish(e, res)
    assert res.status == "complete"
    assert [o.op for o in res.outcomes] == ["attack", "move"]
    assert s.positions["c1"] == (10, 5)


def test_a_blow_that_drops_the_mover_stops_the_move():
    """The reason reactions resolve before the intent that provoked them. A creature cut
    down as it turns to run does not also complete the run."""
    s, e = board()
    s.actors["pc"].hp = 1
    res = run_move(e, "pc", (5, 9))

    assert res.outcomes[0].op == "attack"
    assert res.outcomes[1].status == "prevented"
    assert "does not get there" in res.outcomes[1].tell
    assert s.positions["pc"] == (5, 5)                   # never left


# --- the geometry underneath -------------------------------------------------------------

def test_threatens_asks_the_grid_and_not_the_zone():
    s, _ = board()
    assert reactions.threatens(s, "c1", (5, 5))
    assert not reactions.threatens(s, "c1", (5, 9))


def test_an_unplaced_creature_threatens_nothing():
    """Positions are optional even on a scene that has a map — an NPC the GM has not put
    anywhere is in the scene without being anywhere on it."""
    s, _ = board()
    del s.positions["c1"]
    assert not reactions.threatens(s, "c1", (5, 5))


def test_every_trigger_the_code_uses_is_a_declared_one():
    """The same reason `ACTOR_RULES` is a list: a reaction whose trigger is misspelled is
    a feature that silently never fires, and the only symptom is a player wondering why
    their ability never went off."""
    for reaction in reactions.reactions_for(load_pc("fixtures/pc-kesst.json")):
        assert reaction.trigger in reactions.TRIGGERS


def test_the_allowance_survives_a_save(tmp_path, settings):
    """A fight can be put down mid-round. Losing this hands everybody a fresh attack of
    opportunity for the price of reloading."""
    settings.CAMPAIGN_DIR = str(tmp_path)
    from play import campaign as campaign_mod

    c = campaign_mod.begin_with(load_pc("fixtures/pc-kesst.json"))
    c.scene.grid = Grid(20, 20)
    c.scene.reacted["c1:attack_of_opportunity"] = 1
    c.save()

    assert campaign_mod.Campaign.load(c.path()).scene.reacted == {
        "c1:attack_of_opportunity": 1}
