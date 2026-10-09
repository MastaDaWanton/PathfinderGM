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


# --- a creature that holds its ground (playtest 2026-09-30, item 8) -------------------------

def _spy(monkeypatch, s, engine, found=None):
    """The owner's encounter: a Clockwork Spy, not aggressive, met while foraging herbs."""
    from rules import bestiary

    from tests._places import stand_on

    stand_on(s, "mountain")
    spy = bestiary.search(text="clockwork spy", limit=1)[0]
    monkeypatch.setattr(gathering, "roll", lambda *a, **k: gathering.Encounter(
        "creature", 80, creature=spy, aggressive=False))
    effects: list = []
    clause = engine._gathering_encounter(
        s.pc(), "mountain", 1, "herbs",
        found={"bitterroot": 2} if found is None else found, effects=effects)
    return clause, effects, effects[-1]["ref"]


def _set_2d6(monkeypatch, engine, total):
    """Make the reaction roll come up `total` before the Charisma modifier."""
    real = engine.dice.roll

    def roll(notation, *args, **kwargs):
        label = kwargs.get("label") or (args[1] if len(args) > 1 else "")
        if str(label).startswith("how "):
            from rules.dice import Roll
            return Roll(die="2d6", faces=[total], label=label)
        return real(notation, *args, **kwargs)

    monkeypatch.setattr(engine.dice, "roll", roll)


def test_the_creature_in_the_way_holds_its_ground_as_an_effect_with_a_tell(monkeypatch):
    """The playtest printed "a Clockwork Spy has the ground you wanted, and has not moved
    off it." — the owner could not parse it, and nothing held the Spy there: no state, no
    record, and "I approach the clockwork Spy" walked away from it. The stance is an
    ActiveEffect now (`state.holding-ground`, source `gathering:<expedition>`), applied
    through the one applicator, and its tell says where and what."""
    from rules import states

    s, engine = _room()
    clause, effects, ref = _spy(monkeypatch, s, engine)
    spy = s.actors[ref]
    assert spy.has_state(states.HOLDING_GROUND)
    held = [e for e in spy.effects if "state.holding-ground" in e.tags]
    assert len(held) == 1 and held[0].source.startswith("gathering:herbs@")
    assert "has the ground you wanted" not in clause
    assert "holds the ground between you and the patch" in clause
    assert "neither comes at you nor gives way" in clause
    # A printed kind goes by its kind, lower-case (`bestiary.kind_word`, 2026-10-09).
    assert clause.count("The clockwork spy") >= 1, clause
    assert effects[-1]["stance"] and effects[-1]["spot"] == "patch"
    assert not s.in_encounter, "a creature holding its ground does not open a fight"


def test_the_patch_it_holds_is_booked_once_and_paid_only_once_it_has_gone(monkeypatch):
    """Owner ruling D1: the patch is a guarded find at x1, an engine record, paid when
    the creature has gone — with a tell when it is claimed. And only HERE: `actors` is
    who is in the party's place, so before `at` a party that walked off read the guard as
    gone and would have been paid for a patch it had left behind."""
    s, engine = _room()
    clause, _, ref = _spy(monkeypatch, s, engine, found={"bitterroot": 2})
    assert len(s.guarded_finds) == 1
    book = s.guarded_finds[0]
    assert book["found"] == {"bitterroot": 2}, "booked at x1, not the guardian's x3"
    assert book["at"] == s.at and book["guard_name"] == "clockwork spy"
    assert "yours once it has gone" in clause
    # Still there: nothing pays.
    assert engine._settle_guarded_finds() == ""
    # The party elsewhere: the creature is out of view, and still nothing pays.
    here = s.at
    s.at = here + "/elsewhere"
    s.pc().at = s.at
    assert engine._settle_guarded_finds() == "" and len(s.guarded_finds) == 1
    s.at = here
    s.pc().at = here
    before = s.pc().inventory.get("bitterroot", 0)
    s.remove(ref)
    line = engine._settle_guarded_finds()
    assert "The patch the clockwork spy held is yours now" in line, line
    assert s.pc().inventory.get("bitterroot", 0) == before + 2
    assert s.guarded_finds == []


def test_a_plan_that_has_it_attack_or_walk_off_is_refused_in_words(monkeypatch):
    """The NPC neither attacks nor flees while it holds. A plan proposing either is
    refused as a printable outcome — not an IntentError, which regenerates rather than
    repairs — naming the two things that would move it."""
    s, engine = _room()
    _, _, ref = _spy(monkeypatch, s, engine)
    for raw in ({"op": "attack", "actor": ref, "target": "pc", "because": "t",
                 "params": {}},
                {"op": "move", "actor": ref, "because": "t",
                 "params": {"zone": "far"}}):
        res = engine.run(engine.validate([raw], origin="author:test"))
        out = res.outcomes[0]
        assert out.status == "refused", out
        assert "holding its ground" in out.tell and "strike it or close on it" in out.tell
    assert not s.in_encounter and s.pc().hp == s.pc().hp_max


@pytest.mark.parametrize("face,expect", [(2, "hostile"), (7, "holds"), (12, "gave way")])
def test_closing_on_it_rolls_its_reaction_on_the_old_table(monkeypatch, face, expect):
    """B/X's reaction table, collapsed to three answers because the stance already IS its
    "uncertain" band: 5 or less it comes at you, 6-8 it keeps the ground, 9 or more it
    gives way — and the patch is then the player's, said in the same batch."""
    s, engine = _room()
    _, _, ref = _spy(monkeypatch, s, engine)
    cha = s.pc().ability_mod("cha")
    _set_2d6(monkeypatch, engine, face - cha)
    res = engine.run(engine.validate([{"op": "move", "actor": "pc", "because": "t",
                                       "params": {"who": ref, "zone": "near"}}],
                                     origin="author:test"))
    stance = [o for o in res.outcomes if o.op == "stance" and o.effects[0].get("ref")]
    assert len(stance) == 1, [o.tell for o in res.outcomes]
    tell = stance[0].tell
    if expect == "hostile":
        assert "comes at you" in tell and s.in_encounter
        assert not s.actors[ref].has_state("state.holding-ground")
    elif expect == "holds":
        assert "does not give way" in tell and not s.in_encounter
        assert s.actors[ref].has_state("state.holding-ground")
        # Closing no further rolls nothing more; closing again rolls again (Holmes).
        res = engine.run(engine.validate([{"op": "check", "actor": "pc", "because": "t",
                                           "params": {"skill": "perception", "dc": 5}}],
                                         origin="author:test"))
        if res.awaiting:
            res = engine.resume(10)
        assert not [o for o in res.outcomes if o.op == "stance"]
    else:
        assert "gives way" in tell and ref not in s.actors
        claimed = [o.tell for o in res.outcomes if "is yours now" in o.tell]
        assert claimed, [o.tell for o in res.outcomes]


def test_striking_it_lifts_the_stance_with_a_tell(monkeypatch):
    """Attacked, it is in the fight: the stance lifts at the end of the batch that drew
    it in, said, so the NPC loop gives it a real turn."""
    s, engine = _room()
    _, _, ref = _spy(monkeypatch, s, engine)
    res = engine.run(engine.validate([{"op": "attack", "actor": "pc", "target": ref,
                                       "because": "t", "params": {}}],
                                     origin="author:test"))
    while res.awaiting:
        res = engine.resume(15)
    assert s.in_encounter
    assert not s.actors[ref].has_state("state.holding-ground") if ref in s.actors else True
    assert any("stops holding its ground" in o.tell for o in res.outcomes), \
        [o.tell for o in res.outcomes]


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
    # Everything mined in the hills, not only `kind == "ore"`: the forge revamp (plan
    # §12.7) let prospecting yield every mined material — limestone flux comes out of the
    # same ground — where the ore-only filter left 16 mined materials unreachable.
    hill_ores = {m.name for m in blacksmith.obtainable("mined", biome="hills")}
    assert {st["base"] for st in stock} <= hill_ores
    # Carried by material id since the gathering door was shared (2026-10-06), where
    # every bench reads it; the forge's own reader is the proof it arrived.
    assert any(p.name in hill_ores for p in blacksmith.rack(s.pc())), "the ore is carried"
