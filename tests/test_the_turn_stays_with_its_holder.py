"""The turn stays with whoever holds it, whatever happens to the order around them.

`Scene.turn` is an INDEX into `Scene.initiative`, so every door that appends to that
list, sorts it or removes from it moves the turn unless it puts the pointer back.
Measured 2026-09-20 as an intermittent failure of `test_a_free_action_does_not_hand_the
_round_to_the_enemy` (`assert 'c3' == 'pc'`): the narrator introduced somebody,
`join_fight` rolled them in, their d20 beat the player's, they sorted in above the
player, and the turn the player still held went to them. Four doors wrote their own
re-pointing; three read `current_ref()` AFTER the append and the sort, so it "kept"
whoever the sort had just moved into the slot, and the troop branch adjusted nothing.
The fix for that sat uncommitted in a worktree for five days; ported 2026-09-25.

And the removal side, measured by probe 2026-09-25: `_rout` cut a troop out of the
order before `scene.remove` ran, so `_unseat` read a shifted list (the turn moved from
the player to c3); and when the creature HOLDING the turn left, its successor slid into
the slot and the next advance stepped one past it — skipped.
"""
from __future__ import annotations

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


class _Rigged(Dice):
    """A d20 whose initiative rolls land on a chosen face: the defect is decided by the
    newcomer's roll, so a seed would only move the coin flip somewhere else."""

    def __init__(self, face: int, seed: int | None = 99):
        super().__init__(seed)
        self.face = face

    def d20(self, modifiers=None, label="", visibility="hidden"):
        if "initiative" in label:
            return self.given(self.face, modifiers, label)
        return super().d20(modifiers, label, visibility)


def _fight_with_a_bystander(face: int):
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    s.add(instantiate("thug", scene=s, name="a watcher"))
    e = Engine(s, Dice(seed=99))
    e.run(e.validate([{"op": "begin_encounter",
                       "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
    while s.current_ref() != "pc":
        s.advance_turn()
    e.dice = _Rigged(face)
    return s, e


def test_a_bystander_joining_does_not_take_the_turn_out_of_your_hand():
    for face in (1, 20):
        scene, engine = _fight_with_a_bystander(face)
        assert engine.join_fight("c2", "them")
        assert scene.current_ref() == "pc", f"a bystander rolling {face} took the turn"


def test_a_creature_spawning_mid_fight_does_not_take_the_turn():
    for face in (1, 20):
        scene, engine = _fight_with_a_bystander(face)
        engine.run(engine.validate([{"op": "spawn", "actor": "pc",
                                     "params": {"template": "thug", "count": 1,
                                                "name": "a latecomer"},
                                     "because": "test"}]))
        assert scene.current_ref() == "pc", f"a spawn rolling {face} took the turn"


def test_a_troop_arriving_mid_fight_does_not_take_the_turn():
    for face in (1, 20):
        scene, engine = _fight_with_a_bystander(face)
        engine.run(engine.validate([{"op": "spawn", "actor": "pc",
                                     "params": {"template": "thug", "count": 6,
                                                "name": "a mob"},
                                     "because": "test"}]))
        assert scene.current_ref() == "pc", f"a troop rolling {face} took the turn"


def test_a_troop_scattering_does_not_move_the_turn_either():
    scene, engine = _fight_with_a_bystander(20)
    engine.run(engine.validate([{"op": "spawn", "actor": "pc",
                                 "params": {"template": "thug", "count": 6,
                                            "name": "a mob"},
                                 "because": "test"}]))
    mob = next(r for r, _ in scene.initiative if r not in ("pc", "c1", "c2"))
    assert scene.initiative[0][0] == mob, "the mob rolled 20: it is ahead of the player"
    engine._rout(scene.actors[mob])
    assert scene.current_ref() == "pc", "a scattering troop moved the turn"


def test_when_the_holder_leaves_their_successor_is_next_not_skipped():
    s = Scene()
    for name in ("a", "b", "c", "d"):
        s.add(instantiate("thug", scene=s, name=name))
    refs = list(s.actors)
    s.initiative = [(r, 20 - i) for i, r in enumerate(refs)]
    s.turn = 1                                   # b holds the turn
    s.leave_order(refs[1])                       # b dies on their own turn
    assert s.advance_turn() == refs[2], "c, who was next, was skipped"


def test_when_the_first_holder_leaves_the_round_is_not_charged_twice():
    s = Scene()
    for name in ("a", "b", "c"):
        s.add(instantiate("thug", scene=s, name=name))
    refs = list(s.actors)
    s.initiative = [(r, 20 - i) for i, r in enumerate(refs)]
    s.turn, s.round = 0, 3
    s.leave_order(refs[0])
    assert s.advance_turn() == refs[1]
    assert s.round == 3, "the successor's turn is in the round already running"


def test_when_the_last_holder_leaves_the_round_turns_over():
    s = Scene()
    for name in ("a", "b", "c"):
        s.add(instantiate("thug", scene=s, name=name))
    refs = list(s.actors)
    s.initiative = [(r, 20 - i) for i, r in enumerate(refs)]
    s.turn, s.round = 2, 3
    s.leave_order(refs[2])
    assert s.advance_turn() == refs[0]
    assert s.round == 4


def test_somebody_else_leaving_leaves_the_turn_alone():
    s = Scene()
    for name in ("a", "b", "c"):
        s.add(instantiate("thug", scene=s, name=name))
    refs = list(s.actors)
    s.initiative = [(r, 20 - i) for i, r in enumerate(refs)]
    s.turn = 2
    s.leave_order(refs[0])
    assert s.current_ref() == refs[2]
    assert s.advance_turn() == refs[1]


def test_the_successor_waiting_survives_a_save(tmp_path):
    from django.test import override_settings

    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=str(tmp_path)):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        for name in ("a", "b"):
            c.scene.add(instantiate("thug", scene=c.scene, name=name))
        refs = [r for r in c.scene.actors if r != "pc"]
        c.scene.initiative = [("pc", 20), (refs[0], 15), (refs[1], 10)]
        c.scene.turn = 1
        c.scene.leave_order(refs[0])
        c.save()
        back = cm.Campaign.load(c.path())
        cm._LIVE.clear()
    assert back.scene.turn_is_next
    assert back.scene.advance_turn() == refs[1]
