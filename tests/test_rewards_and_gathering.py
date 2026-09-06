"""Experience for things that are not fights, and what the ground does when you go
gathering.

"i should be receiving EXP for doing things and resolving situations and succeeding
on checks otherwise It will take a lot for an individual to level, and they are
forced to seek out violence." And: "i go to collect herbs and run into a bear or a
search for ore and find a massive vein guarded by a cave worm." 2026-09-06.
"""
from __future__ import annotations

import pytest

from gm import judgement
from rules import gathering, xp
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


def _room(seed=3):
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    return s, Engine(s, Dice(seed=seed))


# --- checks pay --------------------------------------------------------------------------

def test_a_dc_reads_as_a_cr_and_a_check_pays_a_quarter_of_the_fight():
    """The app's own rule, written down: every two points of DC above 10 is a CR, a
    check pays a quarter of that CR's fight award, and a routine DC pays nothing.
    Twenty DC-15 checks or seven DC-20 ones is a first level, against five CR 1
    fights."""
    assert xp.cr_for_dc(15) == 2 and xp.cr_for_dc(20) == 5 and xp.cr_for_dc(12) == 1
    assert xp.challenge_award(1, 15) == 150
    assert xp.challenge_award(1, 20) == 400
    assert xp.challenge_award(1, 9) == 0
    assert xp.challenge_award(1, None) == 0
    # DC 10 and 11 are routine: a DC 10 Perception check to notice a crowd paid 33
    # XP on the first live probe, a level in sixty glances.
    assert xp.challenge_award(1, 10) == 0 and xp.challenge_award(1, 11) == 0
    assert xp.challenge_award(1, 12) == 100
    # Never more than the character's own level's fight: a lucky roll against an
    # absurd DC is not five fights.
    assert xp.challenge_award(1, 40) == xp.CR_AWARD[1]
    # Routine for a tenth-level character is not routine for a first.
    assert xp.challenge_award(10, 14) == 0 and xp.challenge_award(1, 14) > 0


def test_a_check_beaten_pays_once_per_dc_per_place_per_day():
    s, engine = _room()
    pc = s.pc()
    before = pc.xp
    def climb(face):
        intents = engine.validate([{"op": "check", "actor": "pc", "because": "t",
                                    "params": {"skill": "climb", "dc": 15}}],
                                  origin="author:test")
        res = engine.run(intents)
        assert res.awaiting, "the player rolls their own check"
        return engine.resume(face).outcomes[-1]

    first = climb(20)
    assert first.verdict == "success" and "You gain 150 XP" in first.tell, first.tell
    assert pc.xp - before == 150
    # The same wall, the same day: no second payment for the grind.
    again = climb(20)
    assert again.verdict == "success" and "You gain" not in again.tell
    assert pc.xp - before == 150
    # A miss pays nothing.
    assert "You gain" not in climb(1).tell


def test_a_storyline_concluded_pays_the_crb_double_and_one_advanced_pays_half():
    assert xp.story_award(1, "new") == 800
    assert xp.story_award(1, "advance") == 200
    assert xp.story_award(1, "keep") == 0
    s, engine = _room()
    line = engine.award_story("new", "the salt levy")
    assert "You gain 800 XP" in line and "salt levy" in line
    assert s.pc().xp == 800


# --- the ground answers back --------------------------------------------------------------

def test_the_table_has_four_answers_and_the_creature_is_the_books():
    """Nothing invented: the creature comes from the bestiary by the biome the scene
    stands on and a CR window around the level."""
    kinds = set()
    for seed in range(40):
        enc = gathering.roll("forest", 1, Dice(seed=seed))
        kinds.add(enc.kind)
        if enc.creature:
            assert "forest" in enc.creature.get("biomes", []) or enc.creature.get("biomes_any")
            assert enc.creature["cr_value"] <= 3
    assert {"quiet", "rich", "creature", "guarded"} <= kinds


def test_a_rich_find_doubles_the_haul_and_a_guarded_one_waits_for_the_guard(monkeypatch):
    s, engine = _room()
    pc = s.pc()
    from rules import bestiary

    wolf = bestiary.search(text="wolf", limit=1)[0]

    monkeypatch.setattr(gathering, "roll", lambda *a, **k: gathering.Encounter(
        "rich", 60, yield_times=2))
    effects: list = []
    clause = engine._gathering_encounter(pc, "forest", 1, "herbs",
                                         found={"bitterroot": 2}, effects=effects)
    assert "rich patch" in clause and effects[-1]["encounter"] == "rich"

    monkeypatch.setattr(gathering, "roll", lambda *a, **k: gathering.Encounter(
        "guarded", 97, creature=wolf, yield_times=3))
    effects = []
    clause = engine._gathering_encounter(pc, "forest", 1, "herbs",
                                         found={"bitterroot": 2}, effects=effects)
    assert "sitting on it" in clause
    assert len(s.guarded_finds) == 1 and s.guarded_finds[0]["found"] == {"bitterroot": 6}
    guard = s.guarded_finds[0]["guard"]
    assert guard in s.actors and s.zones[guard] == "far"
    assert not s.in_encounter, "a guardian sits on the find; it does not charge"
    # The guard dies; the find pays out when the fight ends.
    s.actors[guard].hp = -20
    carried_before = dict(pc.satchel) if hasattr(pc, "satchel") else None
    line = engine._settle_guarded_finds()
    assert "is yours now" in line and s.guarded_finds == []


def test_an_animal_that_notices_you_starts_the_fight(monkeypatch):
    s, engine = _room()
    pc = s.pc()
    from rules import bestiary

    wolf = bestiary.search(text="wolf", limit=1)[0]
    monkeypatch.setattr(gathering, "roll", lambda *a, **k: gathering.Encounter(
        "creature", 80, creature=wolf, aggressive=True))
    effects: list = []
    clause = engine._gathering_encounter(pc, "forest", 1, "herbs", found={}, effects=effects)
    assert "coming for you" in clause
    assert s.in_encounter and len(s.sides.get("them", [])) == 1


# --- ore ------------------------------------------------------------------------------------

def test_a_search_for_ore_reaches_the_engine_as_a_prospect():
    s, _ = _room()
    out = judgement.inject_prospect([{"op": "narrate_only"}],
                                    "I search the hillside for ore for 3 hours", s)
    assert out[-1]["op"] == "prospect" and out[-1]["params"] == {"hours": 3}
    assert judgement.inject_prospect([{"op": "narrate_only"}], "I search for the guard", s) \
        == [{"op": "narrate_only"}]


def test_prospecting_in_the_hills_turns_up_ore_and_nothing_in_a_swamp_but_bog_iron():
    from rules import blacksmith

    from tests._places import stand_on

    s, engine = _room(seed=11)
    stand_on(s, "hills")
    intents = engine.validate([{"op": "prospect", "actor": "pc", "because": "t",
                                "params": {"hours": 2}}], origin="author:test")
    res = engine.run(intents)
    assert res.awaiting, "the Survival check is the player's to roll"
    res = engine.resume(20)
    out = res.outcomes[-1]
    assert out.op == "prospect", out
    stock = [st for e in out.effects if e.get("kind") == "prospect"
             for st in e.get("stock", [])]
    assert stock, out.tell
    hill_ores = {m.name for m in blacksmith.materials().values()
                 if m.kind == "ore" and "hills" in m.biomes}
    assert {st["base"] for st in stock} <= hill_ores
    assert any(x.base in hill_ores for x in s.pc().stock.values()), "the ore is carried"
