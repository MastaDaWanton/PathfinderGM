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


# --- the scene has one ticker too ------------------------------------------------------


def test_a_ward_tied_to_a_condition_goes_when_the_condition_does_and_says_so():
    """"Cure the bleeding and the bleed ward evaporates" was already true and already
    silent: the `stops_with` branch removed the ward with no record at all, three lines
    above the branch that emitted one. One loop and one door out means a thing cannot
    leave the scene without both its teardown and its tell."""
    from rules.engine import Ward

    scene, pc, _ = _fight()
    pc.add_condition("bleed")
    scene.wards.append(Ward(owner="pc", trigger="each_round", stops_with="bleed",
                            source="a bleed ward", spec={}))
    pc.remove_condition("bleed")
    said = [_ward_tell(scene, r) for r in scene.tick_effects(1)]
    assert any("bleed ward" in s for s in said), said
    assert not scene.wards


def test_a_manifestation_always_gives_its_squares_back():
    """The teardown is why removal is a door rather than two `remove` calls. A
    manifestation's squares are a MUTATION of the grid that only `lift` undoes, and
    `ActiveEffect` has no teardown hook — an expiry routed through a generic ticker
    would drop the record and leave the fog's squares in `grid.obscuring` for the rest
    of the session, with no fog in the room to explain why it was blind."""
    from rules.engine import Manifestation
    from rules.grid import Grid

    scene, _, _ = _fight()
    scene.grid = Grid(width=20, height=20)
    scene.place(Manifestation(what="a bank of fog", terrain="obscuring",
                              squares=[(5, 5), (5, 6)], rounds_left=2,
                              source="fog cloud"))
    assert sorted(scene.grid.obscuring) == [(5, 5), (5, 6)]
    said = [_ward_tell(scene, r) for r in scene.tick_effects(5)]
    assert any("fog" in s for s in said), said
    assert not scene.grid.obscuring, "the room stayed blind"


def test_the_scene_expires_everything_in_one_loop():
    """Two loops three lines apart is how the two halves came to disagree."""
    import ast
    from pathlib import Path

    source = Path("rules/engine.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    scene = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.ClassDef) and n.name == "Scene")
    fn = next(m for m in scene.body
              if isinstance(m, ast.FunctionDef) and m.name == "tick_effects")
    body = ast.get_source_segment(source, fn)
    assert body.count("rounds_left -=") == 1, "the scene grew a second expiry loop"
