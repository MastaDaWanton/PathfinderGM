"""The first swing opens the battle; it never fights the battle.

The defect, measured in live play 2026-08-27 (campaign mastadawanton, turn 5): the
player wrote "i strike him one final time to put him out of his misery" over a
stranger dying at -7. One spoken turn then spawned a thug from nowhere ("the player
started a fight with somebody" — inject_fight's default template), began an
encounter, swung, confirmed a critical for 30, killed the thug, ended the fight and
paid out 135 XP — an entire war inside one narrated paragraph, the map never shown,
the combat panel never reached, and the dying man untouched.

Two rules fell out. An attack that finds no fight running (or rides the batch that
started one) is deferred: the encounter forms — initiative, sides, the grid laid —
the tell announces that battle is joined, and the first blow is the player's to
declare on their own combat turn. And a coup de grâce is not a fight being started:
the finishing words plus a downed body silence the fight-making repairs entirely.
"""
from __future__ import annotations

import pytest

from gm import judgement
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from tests._board import face_to_face


@pytest.fixture
def scene():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    return s


def test_a_first_swing_opens_the_battle_and_asks_for_the_players_die(scene):
    """The attack finds no fight, so it makes one — encounter live, grid laid, the
    initiator holding the turn — and then the declared blow waits on the PLAYER's own d20.

    It used to stop there, the swing deferred to the combat panel. Overturned by the
    owner's play, 2026-10-01: "i shot an arrow and did not get a to hit roll or dmg roll,
    the action was narrated and no dmg was dealt then combat starts". What 2026-08-27's
    defect forbids still holds: no die is rolled for the player in secret, and nothing is
    hurt before their roll."""
    engine = Engine(scene, Dice(seed=5))
    thug_hp = scene.actors["c1"].hp
    scene.zones["c1"] = "engaged"           # within reach: the blow can land from here
    res = engine.run(engine.validate([
        {"op": "attack", "actor": "pc", "target": "c1", "because": "she swings"}]))

    assert scene.in_encounter and scene.grid is not None
    assert scene.current_ref() == "pc", "the initiator keeps the turn they declared"
    assert scene.awaiting and scene.awaiting["label"].startswith("Attack with"), \
        "the declared blow asks for the player's own die"
    assert scene.actors["c1"].hp == thug_hp, "nothing is hurt before the player rolls"
    out = res.outcomes[0]
    assert out.op == "attack" and not out.rolls
    assert any(e.get("kind") == "battle_joined" for e in out.effects)
    assert "Battle is joined" in out.tell and "the thug" in out.tell


def test_the_players_spell_damage_is_the_players_to_roll(scene):
    """The owner's Magic Missile, 2026-10-01: "no damage dice user roll for the spell I
    assume the engine rolled them but the user should be doing that". `cast` defaulted to
    hidden, so a spell the planner proposed was rolled by the engine (the save shows the
    roll labelled "Magic Missile — damage", visibility hidden). The player's cast is the
    player's dice at every door it comes through: the plan (repaired here, whatever the
    model wrote), the combat panel and the Spells tab (both now send `visibility:
    player`). An NPC's cast is left alone; the engine's own doors keep their dice."""
    from pathlib import Path

    from gm import judgement
    from rules.intents import parse

    assert parse({"op": "cast", "actor": "pc", "params": {"spell": "magic-missile"}}
                 ).visibility == "hidden", "the parser's default, which is the defect"
    raw = [{"op": "cast", "actor": "pc", "visibility": "hidden",
            "params": {"spell": "magic-missile", "at": "c1"}},
           {"op": "cast", "params": {"spell": "magic-missile", "at": "c1"}},
           {"op": "cast", "actor": "c1", "params": {"spell": "magic-missile", "at": "pc"}}]
    out = judgement.the_players_spell_dice(raw, "I cast magic missile", scene)
    assert [r.get("visibility") for r in out] == ["player", "player", None]
    views = Path("play/views.py").read_text(encoding="utf-8")
    assert views.count('"visibility": "player"') >= 2, "the panel and the Spells tab"


def test_an_arrow_landing_before_any_roll_is_caught():
    """The owner's beat, 2026-10-01, on a turn whose only blow was the battle joined: the
    landing check knew swords and fists and not a missile, so the arrow "strikes the
    small, twitching shape" and the spy "is knocked backward ... its brass casing
    buckling" shipped with no die rolled."""
    from gm import narration

    beat = ("The arrow whistles through the dry air, a streak of gray against the pale "
            "stone. It strikes the small, twitching shape with a sharp ping of metal on "
            "metal. The spy is knocked backward into the crevice, its brass casing "
            "buckling and sparking as it skitters across the rocks. The dirt of the "
            "plateau kicks up in a small cloud.")
    early = narration.premature_blows(beat, [{"joined": True}])
    assert len(early) == 2 and "whistles" not in " ".join(early)
    assert not narration.premature_blows(beat, [{"joined": True}, {"rolled": True}])


def test_the_swing_riding_begin_encounter_is_deferred_too(scene):
    """The GM's own [begin_encounter, attack] batch — inject_fight's triple — must
    not resolve the attack either, or the deferral has a hole exactly where the
    playtest fell through."""
    engine = Engine(scene, Dice(seed=5))
    thug_hp = scene.actors["c1"].hp
    res = engine.run(engine.validate([
        {"op": "begin_encounter",
         "params": {"sides": {"you": ["pc"], "them": ["c1"]}}},
        {"op": "attack", "actor": "pc", "target": "c1", "because": "she swung first"},
    ]))
    assert scene.in_encounter
    assert scene.actors["c1"].hp == thug_hp
    assert any("Battle is joined" in (o.tell or "") for o in res.outcomes)


def test_a_swing_inside_a_running_fight_resolves(scene):
    """The gate is about the first moment only: a fresh batch inside a running
    encounter fights exactly as before."""
    engine = Engine(scene, Dice(seed=5))
    engine.run(engine.validate([
        {"op": "attack", "actor": "pc", "target": "c1", "because": "she swings"}]))
    # The fight lays the thug fifteen feet off; a swing from there is refused and the
    # square to step to named (test_maneuver_reach.py). This test is about the gate.
    face_to_face(scene)
    res = engine.run(engine.validate([
        {"op": "attack", "actor": "pc", "target": "c1", "because": "round one"}]))
    assert scene.awaiting and scene.awaiting["die"] == "1d20"
    assert "Attack" in scene.awaiting["label"]
    _ = res


def test_a_mercy_stroke_on_the_dying_opens_nothing_and_lands(scene):
    """One living combatant is no encounter. The blow the playtest deferred to a
    phantom thug resolves against the body it was aimed at."""
    body = scene.actors["c1"]
    body.hp = -7
    body.add_condition("dying", source="the earlier fight")
    engine = Engine(scene, Dice(seed=5))
    res = engine.run(engine.validate([
        {"op": "attack", "actor": "pc", "target": "c1",
         "because": "out of his misery"}]))
    assert not scene.in_encounter, "a corpse cannot be an opponent"
    # The swing itself proceeds, suspending on the player's own d20, rather than being
    # announced as a battle. This used to read `awaiting or <no battle_joined>`, and it
    # passed through the second half for as long as the swing resolved as NOTHING — the
    # attack loop broke on `is_down` before the first swing (probed 2026-09-27; see
    # tests/test_coup_de_grace.py). Both halves are required now.
    assert scene.awaiting and scene.awaiting["die"] == "1d20", "no die was offered"
    assert all(e.get("kind") != "battle_joined" for o in res.outcomes for e in o.effects)


def test_inject_fight_stands_aside_for_a_finishing_blow(scene):
    """Turn 5, verbatim. Before the guard: this exact sentence appended
    [spawn thug, begin_encounter, attack c2] and the player fought a man who did
    not exist while the one they named lay untouched."""
    body = scene.actors["c1"]
    body.hp = -7
    body.add_condition("dying", source="the earlier fight")
    raw = [{"op": "attack", "actor": "pc", "target": "c1", "because": ""}]
    # Through the reading the live reader gave this line (2026-10-09: the regex door that
    # spawned the thug is gone, and the blow is the reading's `attack` act).
    from tests._violence import everyone, through_the_reading

    out, stop = through_the_reading(
        raw, "i strike him one final time to put him out of his misery", scene,
        ask=everyone)
    assert out == raw and not stop, "the mercy stroke is the whole turn — nothing added"


def test_the_redirect_leaves_the_mercy_stroke_on_the_body(scene):
    """With a living bystander in the scene, retargeting a coup de grâce would swing
    it at somebody who was never named. The finishing words pin it to the body."""
    body = scene.actors["c1"]
    body.hp = -7
    body.add_condition("dying", source="the earlier fight")
    scene.add(instantiate("guildhand", scene=scene, name="a bystander"))
    raw = [{"op": "attack", "actor": "pc", "target": "c1", "because": ""}]
    fixed = judgement.redirect_attacks_off_corpses(
        raw, "i finish him off", scene)
    assert fixed is None, "a finishing blow is aimed at the body on purpose"
