"""The quest a found way down opens, and how it is finished (rules/dungeons.py `settle`).

The owner, 2026-11-16: "i would like finding the way down to give you a quest to complete
it and mark the location for returning. and completing it should be defeating the Boss at
the end or completing all trials." Measured before this: finding the culvert under the
gardens' sewers told one line and nothing else — no quest in the Journal, no award at the
end, nothing that said the dungeon had been done.
"""
from __future__ import annotations

import pytest

from play import places_found
from rules import cards, dungeons, objectives, xp
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

VYRAKON = "5bbd0c40345f"
WORLD = loader.load_cached("fixtures/pangrella-campaign.json")


@pytest.fixture
def always(monkeypatch):
    monkeypatch.setattr(dungeons, "chance", lambda *a, **k: 100)


def _run(engine, op, params):
    intents = engine.validate([{"op": op, "actor": "pc", "because": "t", "params": params,
                                "visibility": "hidden"}], origin="author:test")
    return engine.run(intents).outcomes


def _found_cave(seed=11):
    """Venture a cave, walk to its deep chamber, search until the way down is found."""
    s = Scene(location_id=VYRAKON)
    s.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(s, Dice(seed=seed), world=WORLD)
    told = [o.tell for o in _run(engine, "venture", {"kind": "cave"})]
    head = next(p for p in s.founded if p["id"] == s.at)
    told += [o.tell for o in _run(engine, "travel", {"place": head["deeper"]["spot"]})]
    while not head["deeper"]["found"]:
        told += [o.tell for o in _run(engine, "check", {"skill": "perception",
                                                        "search": True})]
    return s, engine, head, " ".join(told)


def _quest(s):
    return next(c for c in cards.quests(s) if dungeons.is_quest(c))


def _rooms(s, head):
    return [p for p in s.founded if (p.get("dungeon") or {}).get("of") == head["id"]]


def test_finding_the_way_down_opens_the_players_own_quest_told_and_in_the_journal(always):
    """The owner's "finding the way down to give you a quest": the batch that finds it
    opens a quest the player owns, titled from the place names, told as a tell, listed
    in the Journal with the place, and opened once however many turns follow."""
    s, engine, head, told = _found_cave()
    card = _quest(s)
    assert cards.is_own(card) and card.live
    # Titled from the dungeon's concept now (feat/dungeon-story), still naming the place.
    tag = dungeons.story()["tags"][head["deeper"]["concept"]["tag"]]
    assert "below the cave" in card.title and card.title.startswith(tag["quest"].split()[0])
    assert "takes it on: " + card.title in told
    log = cards.quest_log(s)
    row = next(r for r in log["active"] if r["id"] == card.id)
    assert "the split boulder" in " ".join(row["facts"])
    assert card.place == head["deeper"]["spot"]
    _run(engine, "check", {"skill": "perception", "search": True})
    assert sum(dungeons.is_quest(c) for c in cards.quests(s)) == 1


def test_the_plan_cannot_tick_the_dungeon_quest(always):
    """Only the engine finishes it: a model's quest_step is the engine's (passed over),
    so "I've cleared it" in a plan pays nothing."""
    s, engine, head, _ = _found_cave()
    card = _quest(s)
    assert objectives.judge(engine, card, 0).verdict == objectives.ENGINE
    xp_before = s.pc().xp
    _run(engine, "quest_step", {"quest": card.id, "objective": 1})
    assert cards.find(s, card.id).live and s.pc().xp == xp_before


def test_the_boss_down_finishes_it_and_pays_the_story_award_once(always):
    """(a) the climax room's creatures dealt with: the quest closes, the CRB's story award
    (double a CR = APL award, p.397) is paid once, a tell says so, and the rooms stay."""
    s, engine, head, _ = _found_cave()
    climax = next(r for r in _rooms(s, head) if r["dungeon"]["role"] == "climax")
    boss = engine._bring_in("wolf", count=1)[0]["ref"]
    s.move(boss, climax["id"])
    climax["dungeon"].update(stocked=True, foes=[boss])
    assert dungeons.completion(engine, head["id"]) == ""
    s.people[boss].die("test")
    before = s.pc().xp
    out = dungeons.settle(engine)
    card = cards.find(s, _quest(s).id)
    assert not card.live and card.stage == "resolved"
    assert s.pc().xp - before == xp.story_award(s.pc().level, "new")
    assert "is finished" in out[0].tell and head["deeper"]["cleared"] == "boss"
    assert dungeons.settle(engine) == [] and s.pc().xp - before == xp.story_award(
        s.pc().level, "new")
    assert len(_rooms(s, head)) >= 4
    assert any(r["id"] == card.id for r in cards.quest_log(s)["finished"])


def test_a_boss_that_yields_or_runs_is_dealt_with_but_one_still_fighting_is_not(always):
    s, engine, head, _ = _found_cave()
    climax = next(r for r in _rooms(s, head) if r["dungeon"]["role"] == "climax")
    boss = engine._bring_in("wolf", count=1)[0]["ref"]
    s.move(boss, climax["id"])
    climax["dungeon"].update(stocked=True, foes=[boss])
    s.move(boss, head["deeper"]["spot"])          # chased the party up the passage
    s.sides = {"party": ["pc"], "foes": [boss]}
    assert dungeons.completion(engine, head["id"]) == ""
    s.sides = {}
    assert dungeons.completion(engine, head["id"]) == "boss"   # ran off, fight over


def test_every_trial_finishes_a_dungeon_with_no_boss_and_one_armed_trap_does_not(always):
    """(b) every room entered, its creatures dealt with, every trap disarmed or sprung.
    A climax the bestiary stocked with nobody has no boss, so walking into it is not (a);
    only the trials finish it."""
    s, engine, head, _ = _found_cave()
    rooms = _rooms(s, head)
    for r in rooms:
        r["dungeon"].update(stocked=True, foes=[], trap=None)
    rooms[0]["dungeon"]["trap"] = {"id": "pit-trap", "on": "room", "found": True,
                                   "armed": True}
    rooms[1]["dungeon"]["stocked"] = False                   # never entered
    assert dungeons.completion(engine, head["id"]) == ""
    rooms[1]["dungeon"]["stocked"] = True
    assert dungeons.completion(engine, head["id"]) == ""       # the pit still armed
    rooms[0]["dungeon"]["trap"].update(armed=False, sprung=True)
    assert dungeons.completion(engine, head["id"]) == "trials"
    before = s.pc().xp
    out = dungeons.settle(engine)
    assert "Every room below has been seen through" in out[0].tell
    assert s.pc().xp - before == xp.story_award(s.pc().level, "new")


def test_a_save_with_a_found_way_and_no_quest_gets_its_quest(always):
    """Saves made before this: the way down found, the rooms minted, no quest. The first
    batch after the load opens it."""
    s, engine, head, _ = _found_cave()
    s.cards = [c for c in s.cards if not str(c.get("origin", "")).startswith("rule:dungeon/")]
    out = _run(engine, "check", {"skill": "perception", "search": True})
    assert _quest(s).live
    assert any("takes it on: " + _quest(s).title in o.tell for o in out)


def test_the_way_down_and_its_rooms_stay_on_the_chart_after_leaving(always):
    """"mark the location for returning": walked into the first room and back out to the
    venture's mouth, the chart still holds the spot and the room, with a walk back."""
    s, engine, head, _ = _found_cave()
    first = next(r for r in _rooms(s, head) if r["dungeon"]["role"] == "entrance")
    s.pc().hp = s.pc().hp_max = 500
    _run(engine, "travel", {"place": first["id"]})
    if s.in_encounter:
        s.end_encounter()
    _run(engine, "travel", {"place": head["id"]})
    assert s.at == head["id"]
    nodes = {n["id"]: n for n in places_found.chart(engine, WORLD)["nodes"]}
    assert head["deeper"]["spot"] in nodes and first["id"] in nodes
    assert nodes[first["id"]]["visited"] and nodes[first["id"]]["walk"]
