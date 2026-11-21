"""Fight text from the owner's 0.4.4 game (playtest 2026-11-20, items 16 and 18).

Measured on the owner's save (pgm-work/owner-1120-data, campaign shadow):
- #107 "The second lizard moves to near, out in open ground." The NPC move tell printed
  its internal zone word, "moves to near (15 ft)", and the page kept it.
- #108 "giant cockroach is still down, but the bleeding has stopped." The cockroach fell
  dying at #89, then lay dying through an hour of essence-gathering, and the next fight's
  rounds reported it. By the book a dying body bleeds every round, fight or no fight.
- #114 "You strike the third lizard. The third lizard is dead." This was an attack of
  opportunity (the record's `because`: "they moved out of reach"), and nothing on the page
  said so.
Sources and rejected options: docs/research/2026-11-20-battle-board.md.
"""
from __future__ import annotations

from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc

from test_creature_closes import _owners_board, _run

ABILITIES = {k: 10 for k in ("str", "dex", "con", "int", "wis", "cha")}


class Face(Dice):
    """Every d20 shows one face: the stabilise roll is the only d20 a dying body rolls."""

    def __init__(self, face: int):
        super().__init__(seed=1)
        self.face = face

    def d20(self, modifiers=None, label="", **kw):
        return self.given(self.face, modifiers or [], label=label)


def _left_dying(face: int):
    scene = Scene(location_id="here")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    roach = from_dict({"name": "giant cockroach", "kind": "npc", "hp": 10, "hp_max": 10,
                       "abilities": ABILITIES}, ref="c1")
    roach.from_template = "giant-cockroach"
    scene.add(roach)
    Engine(scene, Face(face))
    roach.hp = -2
    roach.apply_hp_state()
    assert roach.has_state("state.down.dying")
    return scene, roach


def test_an_hour_out_of_a_fight_settles_a_dying_body_and_says_so():
    """#108. An hour is 600 rounds, and each round is a stabilise roll or a point lost,
    so the body is settled by the end of it. Before the fix it was still dying an hour
    later and was reported mid-fight, in lower case."""
    scene, roach = _left_dying(20)
    scene.advance(60)
    # Stable, and with a natural 20 on the hourly check it may have come round too.
    assert not roach.has_state("state.down.dying") and not roach.is_dead
    said = [r.get("said") for r in scene.take_ended_said() if r.get("kind") == "said"]
    assert "The giant cockroach stabilises where they lie." in said

    scene, roach = _left_dying(1)
    scene.advance(60)
    assert roach.is_dead
    said = [r.get("said") for r in scene.take_ended_said() if r.get("kind") == "said"]
    assert "The giant cockroach has bled out where they fell." in said


def test_a_round_out_of_a_fight_bleeds_one_round_only():
    """The stretch's rounds, no more. One round with a failed check costs one point."""
    scene, roach = _left_dying(1)
    scene.advance(0, rounds=1)
    assert roach.hp == -3 and roach.has_state("state.down.dying")


def test_an_npc_move_says_feet_not_the_zone():
    """#107: "moves to near (15 ft)" printed the zone word. Now the tell gives the feet
    walked and how far that leaves the mover from the player."""
    scene, engine = _owners_board()
    res = _run(engine, [{"op": "move", "actor": "c1", "params": {"square": [0, 10]}}])
    (move,) = [o for o in res.outcomes if o.op == "move"]
    assert " to near" not in move.tell and " to far" not in move.tell
    gap = scene.distance_between("c1", "pc")
    assert f"is {gap} ft from Kesst Vayr." in move.tell, move.tell
    assert move.tell.startswith("Clockwork Spy moves ")
