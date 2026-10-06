"""Walking out of a fight is a withdraw, and a withdraw is not free.

The defect (docs/fix-interfaces.md, "Walking out of a fight provokes nothing", found by the
polish batch 2026-09-29): leaving a fight by `travel` or `journey` ended the encounter with
ZERO attacks of opportunity, whoever stood over the player, while the exits row promised
them. `Engine._reactions_before` answered only `move` and `give`, and both ops settled the
experience and called `end_encounter` without asking anybody. A player could walk out of
any melee for free.

The rule sourced for the fix (CRB p.188, Withdraw; aonprd.com/Rules.aspx?Name=Withdraw&
Category=Full-Round%20Actions): the square you start in "is not considered threatened by
any opponent you can see"; "invisible enemies still get attacks of opportunity against you,
and you can't withdraw from combat if you're blinded"; and leaving any threatened square
after the first provokes "as normal" — which is where a foe with reach still swings. So one
adjacent man with a club gets nothing as you back away, an ogre beside you still does, and
a blow that drops you stops you going (CRB p.180: the attack of opportunity interrupts, and
is resolved before the provoking action goes on).
"""
from __future__ import annotations

import pytest

from rules import journey, reactions
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.grid import Grid
from rules.intents import IntentError
from rules.sheet import load_pc
from tests._places import stand_on
from world.loader import load_cached

AURVANTIS = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = "bde94b038cba"


def board(pc_at=(5, 5), thug_at=(6, 5), fighting=True, seed=7):
    s = Scene(location_id="5bbd0c40345f", grid=Grid(20, 20))
    s.add(load_pc("fixtures/pc-kesst.json"), at=pc_at)
    s.add(instantiate("thug", scene=s, name="the thug"), at=thug_at)
    stand_on(s, "urban")
    # By day: a street at the default midnight is dim since the light model (alchemy
    # lane C), and the swings here are about who swings, not about seeing.
    s.clock_minutes = 12 * 60
    s.sides = {"us": ["pc"], "them": ["c1"]}
    if fighting:
        s.initiative = [("pc", 20), ("c1", 10)]
        s.turn = 0
    return s, Engine(s, Dice(seed=seed))


def sturdy(s):
    """A PC no single blow can drop, so a test about WHO swings is not also about dying."""
    s.actors["pc"].hp = 500
    return s


def leave(engine, **params):
    return engine.run(engine.validate([
        {"op": "travel", "actor": "pc", "because": "she makes for the treeline",
         "params": {"biome": "forest", **params}}]))


def ops(res):
    return [o.op for o in res.outcomes]


# --- who swings --------------------------------------------------------------------------

def test_one_adjacent_foe_you_can_see_gets_no_swing():
    """The withdraw's whole point: "the square you start out in is not considered
    threatened by any opponent you can see". A thug with a club beside you threatens only
    the squares next to him, and the first step away is out of them."""
    s, e = board()
    sturdy(s)
    res = leave(e)
    assert ops(res) == ["travel"]
    assert s.reacted == {}
    assert not s.in_encounter


def test_a_foe_whose_reach_covers_the_way_out_still_swings():
    """The defect, measured: this walk-out ended the encounter with zero attacks of
    opportunity. An ogre-sized foe beside you threatens ten feet, so every square you can
    step into is still in its reach, and leaving THAT square provokes "as normal"."""
    s, e = board()
    sturdy(s)
    s.actors["c1"].size = "large"
    res = leave(e)
    assert ops(res) == ["attack", "travel"]
    assert res.outcomes[0].status != "prevented"
    assert s.reacted == {"c1:attack_of_opportunity": 1}
    assert not s.in_encounter, "the PC survived the swing and the walk went on"


def test_a_glaive_ten_feet_off_does_not_reach_the_first_step_back():
    """Reach is not a blanket "reach foes always swing": a glaive-wielder standing at the
    far edge of his reach cannot strike what is beside him or anything further off, so a
    step directly away takes the withdrawer out of it, and the start square is exempt."""
    s, e = board(thug_at=(7, 5))
    sturdy(s)
    thug = s.actors["c1"]
    thug.weapons = list(thug.weapons) + ["glaive"]
    thug.equipped = "glaive"
    assert reactions.threatens(s, "c1", (5, 5)), "the start square IS threatened"
    res = leave(e)
    assert ops(res) == ["travel"]


def test_a_blinded_pc_cannot_withdraw_and_provokes():
    """"You can't withdraw from combat if you're blinded": no square is exempt, so the
    thug beside you swings as you go."""
    s, e = board()
    sturdy(s)
    s.actors["pc"].add_condition("blinded", source="a pinch of sand")
    res = leave(e)
    assert ops(res) == ["attack", "travel"]
    assert s.reacted == {"c1:attack_of_opportunity": 1}


def test_an_invisible_foe_still_gets_its_swing():
    """"Invisible enemies still get attacks of opportunity against you" — the exemption is
    for foes you can see, asked of the vocabulary (`state.hidden`), never a string."""
    s, e = board()
    sturdy(s)
    s.actors["c1"].add_condition("invisible", source="a potion")
    res = leave(e)
    assert ops(res) == ["attack", "travel"]


def test_a_spent_allowance_takes_no_second_swing():
    """The same budget `_spend_reaction` keeps for a move: one attack of opportunity a
    round, and a thug who has already taken it this round watches the PC go."""
    s, e = board()
    sturdy(s)
    s.actors["c1"].size = "large"
    s.reacted["c1:attack_of_opportunity"] = 1
    res = leave(e)
    assert ops(res) == ["travel"]


def test_no_map_no_swing():
    """The rule `threatens` keeps for every reaction: on a scene with no map the engine
    cannot say a square was left, and inventing geometry would hand out swings nobody at a
    table would allow."""
    s, e = board()
    s.actors["c1"].size = "large"
    s.grid = None
    res = leave(e)
    assert ops(res) == ["travel"]


# --- a blow that drops you ---------------------------------------------------------------

def test_a_swing_that_drops_the_pc_stops_the_travel_and_the_fight_goes_on():
    """The ordering the reactions were built on (`_op_move`'s "does not get there"): a
    PC cut down as they turn to go does not also arrive in the forest, the encounter is
    not ended, and the outcome names who struck."""
    s, e = board()
    s.actors["c1"].size = "large"
    s.actors["pc"].hp = 1
    was = s.at
    res = leave(e)
    assert ops(res) == ["attack", "travel"]
    travel = res.outcomes[1]
    assert travel.status == "prevented"
    assert "the thug" in travel.tell and "never gets away" in travel.tell
    assert travel.effects[0]["struck_by"] == ["c1"]
    assert s.in_encounter, "the fight ended around a PC who never left"
    assert s.at == was and "c1" in s.actors


def test_the_model_cannot_claim_the_withdraw_was_already_taken():
    """`withdrew` is written by `_drive` only. A model that wrote it would skip every
    attack of opportunity, so it is an unknown param at validation."""
    s, e = board()
    with pytest.raises(IntentError, match="withdrew"):
        e.validate([{"op": "travel", "actor": "pc", "because": "x",
                     "params": {"biome": "forest", "withdrew": []}}])


# --- the road, the same -----------------------------------------------------------------

def _road_fight(hp=500):
    s = Scene(location_id=VORMOOR)
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    e = Engine(s, Dice(seed=7), world=AURVANTIS)
    e.place_party("")
    # By day: a road at the scene's default midnight is dim since the light model
    # (alchemy lane C), and a 20% miss chance on the swing is not what these test.
    s.clock_minutes = 12 * 60
    s.grid = Grid(20, 20)
    s.positions["pc"] = (5, 5)
    ogre = instantiate("thug", scene=s, name="the thug")
    s.add(ogre, at=(6, 5))
    ogre.at = pc.at
    ogre.size = "large"
    pc.hp = hp
    s.sides = {"us": ["pc"], "them": [ogre.ref]}
    s.initiative = [("pc", 20), (ogre.ref, 10)]
    s.turn = 0
    leg = journey.legs_from(AURVANTIS, VORMOOR)[0]
    return s, e, ogre, leg


def test_a_journey_out_of_a_fight_is_the_same_withdraw():
    """The other door out: `_op_journey` ended the fight with no swing too."""
    s, e, ogre, leg = _road_fight()
    assert ogre.ref in s.actors and s.in_encounter
    res = e.run(e.validate([{"op": "journey", "actor": "pc", "because": "t",
                             "params": {"to": leg.to_name}}]))
    assert ops(res)[:2] == ["attack", "journey"]
    swing = res.outcomes[0]
    assert swing.status != "prevented" and swing.effects, "the swing was rolled"
    # Left behind — whatever the road then meets (this seed meets something on it).
    assert ogre.ref not in s.actors
    assert s.location_id == leg.to_id or s.road, "the PC set out"


def test_a_journey_stopped_by_the_swing_goes_nowhere():
    s, e, ogre, leg = _road_fight(hp=1)
    was = s.location_id
    res = e.run(e.validate([{"op": "journey", "actor": "pc", "because": "t",
                             "params": {"to": leg.to_name}}]))
    assert ops(res) == ["attack", "journey"]
    assert res.outcomes[1].status == "prevented"
    assert s.location_id == was and s.in_encounter


# --- whoever leaves with you withdraws too ------------------------------------------------

def _escort(s, at):
    ana = instantiate("guildhand", scene=s, name="Ana")
    s.add(ana, at=at)
    ana.hp = 500
    return ana


def test_an_escort_who_walks_out_of_reach_is_struck_as_the_player_would_be():
    """docs/fix-interfaces.md, "what the withdraw fix left", (1): only the PC withdrew, and
    an escort walked out from beside a foe for free — in 1e every creature that moves out
    of a threatened square provokes. Here the player stands well clear and Ana, leaving
    with her, starts beside a Large thug whose ten-foot reach covers her first step: the
    thug's swing is at Ana, and the walk goes on with her."""
    s, e = board(pc_at=(15, 15))
    s.actors["c1"].size = "large"
    ana = _escort(s, (8, 5))
    res = leave(e, **{"with": [ana.ref]})
    assert ops(res) == ["attack", "travel"], [o.tell for o in res.outcomes]
    assert "Ana" in res.outcomes[0].tell
    assert s.reacted == {"c1:attack_of_opportunity": 1}
    assert ana.at == s.at, "she came along"


def test_a_foe_has_one_swing_for_the_whole_party():
    """The allowance is the foe's, one a round (`_spend_reaction`): the Large thug whose
    reach covers both the player's way out and Ana's swings at the player, who goes first,
    and has nothing left for Ana."""
    s, e = board()
    sturdy(s)
    s.actors["c1"].size = "large"
    ana = _escort(s, (8, 5))
    res = leave(e, **{"with": [ana.ref]})
    assert ops(res) == ["attack", "travel"]
    assert "Kesst" in res.outcomes[0].tell
    assert s.reacted == {"c1:attack_of_opportunity": 1}


def test_the_party_never_swings_at_its_own():
    """A companion is often on no declared side. Asked of her as the mover, the player
    beside her is not a foe owed a swing at her back, nor a body blocking her way."""
    s, e = board(pc_at=(5, 5), thug_at=(15, 15))
    sturdy(s)
    ana = _escort(s, (4, 5))
    # Blinded, so no square is exempt: asked without the party, the player beside her IS
    # one of "everyone who threatens" — the bug the party argument is there for.
    ana.add_condition("blinded", source="t")
    assert [w for w, _ in reactions.provoked_by_withdraw(s, ana.ref)] == ["pc"]
    assert not reactions.provoked_by_withdraw(s, ana.ref, party=["pc", ana.ref])
    res = leave(e, **{"with": [ana.ref]})
    assert ops(res) == ["travel"]
    assert "pc:attack_of_opportunity" not in s.reacted


# --- out of a fight, nothing changes ------------------------------------------------------

def test_a_peaceful_travel_is_byte_identical(monkeypatch):
    """Out of combat the new door must be invisible: the same outcome, to the byte, and
    the same dice stream as a travel with the withdraw machinery removed entirely."""
    def walk(patch):
        s, e = board(fighting=False)
        if patch:
            monkeypatch.setattr(Engine, "_leaving_the_fight",
                                lambda self, i, pc, escorts=(): None)
        res = leave(e)
        after = e.dice.roll("1d1000", label="probe").total
        monkeypatch.undo()
        return [o.as_dict() for o in res.outcomes], s.reacted, after

    assert walk(False) == walk(True)
