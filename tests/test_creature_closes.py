"""A creature's move toward somebody walks the board (the owner's play, 2026-10-01).

The measurement, from the owner's save: a Clockwork Spy (Tiny, slam, speed 30) stood
forty feet from Sam at (0, 13) against (5, 7). Its slam was refused — "Clockwork Spy
reaches 0 ft with the slam and Sam is 40 ft away ... There is no open square in reach of
Sam that Clockwork Spy can get to. Take another action." — and its retry,
`{"op": "move", "actor": "c7", "target": "pc", "params": {}}`, resolved "Clockwork Spy
moves from far to far." Its square never changed; the prose had it "closing the gap and
landing right before you". The owner: "the clockwork spy should have moved in front of
me."

Two causes, both fixed here:

- `_op_move` given a target and no square took the zone branch, which relabels a zone
  and moves nobody. A creature's move at somebody is now walked by `position.closing_move`
  (`Engine._toward_before`), and its tell says where it ended, in feet.
- A Tiny creature's reach is 0, so the only square it can strike from is its target's
  own — and every occupancy check counted that square taken. 1e: Fine, Diminutive and
  Tiny creatures "must enter an opponent's square to attack in melee. This provokes an
  attack of opportunity from the opponent" (aonprd.com/Rules.aspx?ID=179), and "can move
  into or through an occupied square" (ID=176).
"""
from __future__ import annotations

import pytest

from rules import position as position_mod
from rules import reactions
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.grid import Grid, enters_occupied
from rules.intents import IntentError
from rules.sheet import load_pc


def _owners_board(spy_at=(0, 13), pc_at=(5, 7), seed: int = 3, template="clockwork-spy",
                  name="Clockwork Spy"):
    """The owner's board of 2026-10-01: 20 by 14, its walls and rough ground as saved,
    the player at (5, 7), the creature holding the turn in a running fight."""
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    spy = instantiate(template, scene=scene, name=name)
    # As saved: the owner's spy carried its stat block's name, "Clockwork Spy", as every
    # spawn did until 2026-10-09; a printed kind spawned now goes by "clockwork spy"
    # (`bestiary.kind_word`). The measured board keeps the name it was measured with.
    spy.name = name
    scene.add(spy)
    engine = Engine(scene, Dice(seed=seed))
    engine._ensure_encounter("c1", "pc")
    scene.grid = Grid(width=20, height=14,
                      difficult={(3, 9), (14, 5), (16, 12)},
                      blocked={(2, 12), (3, 12), (11, 2), (12, 11), (13, 11), (14, 2)},
                      floor={(4, 5): 1, (6, 4): 1, (17, 3): 1})
    scene.positions = {"pc": tuple(pc_at), "c1": tuple(spy_at)}
    scene.resync_zones()
    scene.turn = next(i for i, row in enumerate(scene.initiative) if row[0] == "c1")
    engine._battle_joined = False
    return scene, engine


def _run(engine, plan):
    res = engine.run(engine.validate([dict(p, because="test") for p in plan]))
    for _ in range(12):
        if not res.awaiting:
            break
        res = engine.resume(10)
    return res


TOWARD = {"op": "move", "actor": "c1", "target": "pc", "params": {}}
SLAM = {"op": "attack", "actor": "c1", "target": "pc", "params": {}}


# --- who may share a square -------------------------------------------------------------

@pytest.mark.parametrize("size,shares", [("fine", True), ("diminutive", True),
                                         ("tiny", True), ("small", False),
                                         ("medium", False), ("large", False)])
def test_only_creatures_under_a_square_across_enter_an_occupied_one(size, shares):
    """Read off SPACE_AND_REACH's space column (2.5 ft for Tiny), not a list of words:
    the rule is "a Fine, Diminutive, or Tiny creature" (ID=176), the three rows under 5."""
    assert enters_occupied(size) is shares


# --- the refusal ------------------------------------------------------------------------

def test_a_reach_of_zero_names_the_targets_own_square():
    """Measured: `square_in_reach` returned None for the spy — the one square in a reach
    of 0 is Sam's, and it was counted taken — so the refusal said "There is no open
    square in reach of Sam". The square is Sam's own, 45 ft by the open route (the walls
    at (2,12) and (3,12) and the rough square at (3,9) are in the way)."""
    scene, _ = _owners_board()
    spy, pc = scene.get("c1"), scene.get("pc")
    assert spy.size == "tiny"
    assert position_mod.square_in_reach(scene, spy, pc, 0) == ((5, 7), 45)


def test_the_refusal_names_the_real_reason_not_no_open_square():
    """The owner's refusal named no open square, which was false. A slam declared from
    forty feet is still refused — more than one move off (the owner's ruling of
    2026-09-29) — but now with the distance and the instruction to close."""
    scene, engine = _owners_board()
    with pytest.raises(IntentError) as caught:
        engine.validate([dict(SLAM, because="test")])
    said = str(caught.value)
    assert "There is no open square" not in said
    assert "[5, 7], is 45 ft away" in said and "move toward them this turn" in said


# --- the move ---------------------------------------------------------------------------

def test_a_move_at_the_player_walks_the_grid_on_the_owners_board():
    """The measured line: `move target=pc` with no square resolved "Clockwork Spy moves
    from far to far." and left it at (0, 13), 40 ft off. Now it walks its 30 ft toward
    Sam and the tell says where it stopped."""
    scene, engine = _owners_board()
    assert scene.distance_between("c1", "pc") == 40
    res = _run(engine, [TOWARD])
    (move,) = res.outcomes
    assert move.status == "resolved"
    assert scene.positions["c1"] != (0, 13)
    assert scene.distance_between("c1", "pc") == 10
    assert move.tell == ("Clockwork Spy moves 30 ft toward Kesst Vayr and is still "
                         "10 ft away.")
    effect = move.effects[0]
    assert effect["kind"] == "position" and effect["feet"] == 30
    assert effect["toward"] == "pc" and effect["gap_ft"] == 10
    assert "far to far" not in move.tell


def test_the_next_round_it_enters_the_square_is_swung_at_and_slams():
    """Ten feet off with its move fresh, the slam closes the last step into Sam's own
    square (ID=179) — the walk the engine composes for a blow one move short — and the
    entry provokes Sam's attack of opportunity, rolled with the spy where it LANDED.
    Asked before the move, the first cut measured that swing from 10 ft and refused it:
    "Kesst Vayr reaches 5 ft with the rapier and Clockwork Spy is 10 ft away"."""
    scene, engine = _owners_board()
    _run(engine, [TOWARD])
    scene.round += 1
    res = _run(engine, [SLAM])
    ops = [(o.op, o.status) for o in res.outcomes]
    assert ops == [("move", "resolved"), ("attack", "resolved"),
                   ("attack", "resolved")], [o.tell for o in res.outcomes]
    step, swing, slam = res.outcomes
    assert scene.positions["c1"][:2] == scene.positions["pc"][:2] == (5, 7)
    assert step.tell == "Clockwork Spy closes 10 ft on Kesst Vayr to strike."
    assert swing.tell.startswith("Kesst Vayr")
    assert "reaches 5 ft" not in swing.tell
    assert slam.tell.startswith("Clockwork Spy")
    assert "reaches 0 ft" not in slam.tell


def test_move_then_slam_in_one_turn_when_one_move_reaches():
    """[move toward, attack] is a move action and a standard action: from fifteen feet
    the move goes all the way into the square the slam needs, so the slam lands this
    turn rather than being refused at the floor."""
    scene, engine = _owners_board(spy_at=(5, 10))
    assert scene.distance_between("c1", "pc") == 15
    res = _run(engine, [TOWARD, SLAM])
    move = res.outcomes[0]
    assert move.tell == "Clockwork Spy moves 15 ft into Kesst Vayr's square."
    assert [o.op for o in res.outcomes] == ["move", "attack", "attack"]
    assert res.outcomes[-1].status == "resolved"
    assert "reaches 0 ft" not in res.outcomes[-1].tell


def test_a_medium_creature_stops_beside_and_says_it_is_in_reach():
    """The same door for a creature with a reach: it walks to the nearest square in
    reach and stops there — beside the player, never on them."""
    scene, engine = _owners_board(spy_at=(5, 11), template="thug", name="the thug")
    res = _run(engine, [TOWARD])
    (move,) = res.outcomes
    assert scene.distance_between("c1", "pc") == 5
    assert scene.positions["c1"][:2] != scene.positions["pc"][:2]
    assert move.tell == "the thug closes 15 ft on Kesst Vayr and is within reach."


def test_already_in_reach_is_said_and_nothing_moves():
    scene, engine = _owners_board(spy_at=(5, 8), template="thug", name="the thug")
    res = _run(engine, [TOWARD])
    (move,) = res.outcomes
    assert scene.positions["c1"][:2] == (5, 8)
    assert move.tell == "the thug is already within reach of Kesst Vayr."


def test_walled_off_says_there_is_no_way_nearer_rather_than_far_to_far():
    """A creature boxed in by walls has nowhere nearer to go. Told as that — not "moves
    from far to far", the sentence the narrator dressed as a creature crossing forty
    feet."""
    scene, engine = _owners_board()
    scene.grid.blocked |= {(0, 12), (1, 12), (1, 13)}
    res = _run(engine, [TOWARD])
    (move,) = res.outcomes
    assert scene.positions["c1"][:2] == (0, 13)
    assert move.tell == ("Clockwork Spy finds no open way nearer to Kesst Vayr and is "
                         "still 40 ft away.")


def test_a_move_away_with_a_zone_word_is_not_turned_into_a_close():
    """`zone: far` at somebody is a retreat, and stays the zone branch's to tell."""
    scene, engine = _owners_board(spy_at=(5, 10))
    res = _run(engine, [{"op": "move", "actor": "c1", "target": "pc",
                         "params": {"zone": "far"}}])
    assert scene.positions["c1"][:2] == (5, 10)
    assert "toward" not in res.outcomes[0].tell


def test_a_model_may_not_write_toward_itself():
    """`toward` is the engine's mark; the move op's schema refuses it from a plan."""
    scene, engine = _owners_board()
    with pytest.raises(IntentError):
        engine.validate([{"op": "move", "actor": "c1", "because": "t",
                          "params": {"toward": "pc"}}])


# --- the square ---------------------------------------------------------------------------

def test_a_tiny_creature_may_be_moved_into_an_occupied_square_and_a_medium_may_not():
    """`_check_move` refused every occupied square: "cannot stand at (5, 7) — (5, 7) is
    taken". For a Tiny body that square is the only one its slam reaches from."""
    scene, engine = _owners_board(spy_at=(5, 10))
    engine.validate([{"op": "move", "actor": "c1", "because": "t",
                      "params": {"square": [5, 7]}}])
    scene2, engine2 = _owners_board(spy_at=(5, 10), template="thug", name="the thug")
    with pytest.raises(IntentError, match="is taken"):
        engine2.validate([{"op": "move", "actor": "c1", "because": "t",
                           "params": {"square": [5, 7]}}])


def test_entering_provokes_only_on_arrival_and_only_for_a_small_body():
    """`provoked_by_entering`: a Tiny body ending in Sam's square provokes Sam, even by
    a five-foot step (the rule's sentence has no step exception); a thug ending beside
    him provokes nothing by entering, and `provoked_by_move` is unchanged for both."""
    scene, _ = _owners_board(spy_at=(5, 8))
    assert [r for r, _ in reactions.provoked_by_entering(scene, "c1", (5, 8), (5, 7))] \
        == ["pc"]
    assert reactions.provoked_by_move(scene, "c1", (5, 8), (5, 7)) == []
    scene2, _ = _owners_board(spy_at=(5, 10), template="thug", name="the thug")
    assert reactions.provoked_by_entering(scene2, "c1", (5, 10), (5, 8)) == []
