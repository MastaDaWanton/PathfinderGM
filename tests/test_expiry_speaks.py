"""Nothing that wears off wears off in silence.

`Scene.advance_turn` called four tickers on every actor and threw away every one of
their return values — so in a fight, a buff running out, a cooldown coming back, a
compulsion releasing and a stance running dry all happened with nothing said. Law 3 is
that the narrator may only dress what the engine recorded, so an expiry nobody records is
an expiry the player can never be told about, however good the prose.

Every test here asserts the RENDERED SENTENCE rather than the record, because
`_ward_tell` returns "" for a kind it does not know and `play/views.py` drops falsy
strings: a new record without a matching branch would be invisible *and* green.
"""
from __future__ import annotations

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene, _ward_tell
from rules.sheet import from_dict


def _fight():
    s = Scene()
    pc = from_dict({"name": "Kesst", "kind": "pc", "hp": 30, "hp_max": 30,
                    "class": "rogue", "level": 1,
                    "abilities": {k: 12 for k in
                                  ("str", "dex", "con", "int", "wis", "cha")}},
                   ref="pc")
    s.add(pc)
    s.add(instantiate("thug", scene=s, name="a thug"))
    e = Engine(s, Dice(seed=5))
    e.run(e.validate([{"op": "begin_encounter",
                       "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
    return s, pc, e


def _roll_a_round(scene):
    """Advance until the round number moves, and hand back what was said."""
    start = scene.round
    scene.hazards = []
    for _ in range(8):
        scene.advance_turn()
        if scene.round > start:
            break
    return [_ward_tell(scene, h) for h in scene.hazards]


def test_a_buff_running_out_mid_fight_is_said_out_loud():
    scene, pc, _ = _fight()
    pc.add_buff("save_mod", "will", 2, source="acacia tea", rounds=1)
    said = _roll_a_round(scene)
    assert any("acacia tea" in s and "wears off" in s for s in said), said


def test_a_cooldown_coming_back_is_said_out_loud():
    scene, pc, _ = _fight()
    pc.gain_pool("ki", 1)
    pc.start_cooldown("ki", 1)
    said = _roll_a_round(scene)
    assert any("ki" in s and "again" in s for s in said), said


def test_every_record_the_rollover_makes_has_a_sentence():
    """The trap this file exists for: a record whose kind `_ward_tell` does not know
    renders as "" and `play/views.py` drops falsy strings, so it is invisible AND
    green. Any new expiry record must arrive with its branch."""
    scene, pc, _ = _fight()
    pc.add_buff("save_mod", "will", 2, source="a tea", rounds=1)
    pc.gain_pool("ki", 1)
    pc.start_cooldown("ki", 1)
    start = scene.round
    scene.hazards = []
    for _ in range(8):
        scene.advance_turn()
        if scene.round > start:
            break
    assert scene.hazards, "the round produced no records at all"
    silent = [h for h in scene.hazards if not _ward_tell(scene, h)]
    assert not silent, f"records with no sentence: {silent}"


def test_a_ward_ending_speaks_as_a_manifestation_already_did():
    """The two halves of `tick_standing` disagreed: a manifestation ending emitted
    `manifest_ended` and a ward ending was removed in silence, three lines apart."""
    from rules.engine import Ward

    scene, _, _ = _fight()
    scene.wards.append(Ward(owner="pc", trigger="when_struck", rounds_left=1,
                            source="a bleed ward", spec={}))
    said = _roll_a_round(scene)
    assert any("bleed ward" in s for s in said), said
    assert not scene.wards


def test_a_stance_that_runs_dry_says_which_pool_ran_out():
    """`_drain_periodic` removed the record and cleared the pool beside it with no
    signature to report through — two silent mutations in the function that enforces
    upkeep, which is the shape law 2 forbids."""
    from rules.activeeffect import ActiveEffect

    scene, pc, _ = _fight()
    pc.gain_pool("rage", 0)
    pc.apply_effect(ActiveEffect(
        name="Blood Rage", kind="condition", key="blood rage", source="Blood Rage",
        periodic=[{"spend_pool": "rage", "amount": 1, "or_ends": True}]))
    said = _roll_a_round(scene)
    assert any("Blood Rage" in s and "runs dry" in s for s in said), said
    assert not pc.has_condition("blood rage")
