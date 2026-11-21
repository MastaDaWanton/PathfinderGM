"""Dungeon rules from the 2026-11-17 playtest (Vesna Kroll, the kept beast's dungeon):
the pit a trap drops you into, the door that paid XP, the dying boss nobody could find,
and the names tells print (playtest-2026-11-17.md #28 #38 #40 #44 #46 #47, and N7 of
playtest-2026-11-16.md)."""
from __future__ import annotations

import pytest

from gm import acts_to_ops
from rules import dice, dungeons, names, ontheway, scope
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

VYRAKON = "5bbd0c40345f"
WORLD = loader.load_cached("fixtures/pangrella-campaign.json")


def _run(engine, op, params):
    intents = engine.validate([{"op": op, "actor": "pc", "because": "t", "params": params,
                                "visibility": "hidden"}], origin="author:test")
    return engine.run(intents).outcomes


def _in_a_room(seed=4):
    s = Scene(location_id=VYRAKON)
    s.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(s, Dice(seed=seed), world=WORLD)
    spot = engine.here()
    rooms = dungeons.generate("~ruins:x/the-ruins", "ruins", spot.id, "ruins",
                              dungeons.FEATURES["ruins"][0], 1)
    for r in rooms:
        r["dungeon"]["door"] = None
    s.founded.extend(rooms)
    s.move("pc", rooms[0]["id"])
    s.pc().hp = s.pc().hp_max = 300
    return s, engine, spot, rooms


@pytest.fixture
def fell(monkeypatch):
    """Kesst at the bottom of the CRB pit trap: the Reflex save failed by force."""
    s, engine, spot, rooms = _in_a_room()
    trap = {"id": "pit-trap", "on": "room", "found": False, "armed": True}
    rooms[0]["dungeon"]["trap"] = trap
    monkeypatch.setattr(dice, "d20_succeeds", lambda *a, **k: False)
    _rolls, _fx, said = dungeons.spring(engine, trap, [s.pc()])
    monkeypatch.undo()
    return s, engine, spot, said


def test_a_pit_trap_leaves_you_in_the_pit_until_the_climb_at_its_own_dc(fell):
    """Playtest 2026-11-17 #38 and #40: the pit trap dropped her 20 ft and held nothing, so
    "I climb up out of the pit" built nothing, and the plan's Climb at "average (DC 10)"
    succeeded by 7 and changed nothing. Now the fall lands `in a pit` through the one
    applicator, the walk away is refused with the DC named, and a Climb check is the
    climb out at the trap's DC 15 whatever DC the plan wrote."""
    s, engine, spot, said = fell
    pc = s.pc()
    assert pc.has_state("state.position.pit")
    assert any("DC 15 Climb" in b for b in said)
    walk = _run(engine, "travel", {"place": spot.id})
    assert walk[-1].status == "refused" and "DC 15 Climb" in walk[-1].tell
    pc.abilities["str"] = 1
    low = _run(engine, "check", {"skill": "climb", "dc": 10})
    assert low[-1].dc == 15 and low[-1].verdict == "failure"
    assert pc.has_state("state.position.pit")
    pc.abilities["str"] = 60
    up = _run(engine, "check", {"skill": "climb", "dc": 10})
    assert up[-1].dc == 15 and up[-1].verdict == "success"
    assert not pc.has_state("state.position.pit")
    assert _run(engine, "travel", {"place": spot.id})[-1].status != "refused"


def test_leaving_at_the_bottom_of_a_pit_is_the_climb_not_a_walk(fell):
    """#38: the reader's `leave` in a pit is built whole as the Climb, and owes no walk
    (Inform's EXIT leaves the container you are in)."""
    s, _engine, _spot, _said = fell
    frame = {"actions": [{"act": "leave", "span": "climb up out of the pit"}]}
    rows = acts_to_ops.table(frame, s)
    assert rows[0].ops == []
    assert rows[0].intents[0]["op"] == "check"
    assert rows[0].intents[0]["params"] == {"skill": "climb"}


def test_forcing_a_stuck_door_pays_no_xp():
    """Playtest 2026-11-17 #44: "You gain 200 XP for the strength check (DC 16)", twice in
    four turns, 400 XP for two doors. A door has a break DC, not a CR (CRB p.397)."""
    s, engine, spot, rooms = _in_a_room()
    rooms[0]["dungeon"]["door"] = {"name": "a good wooden door", "state": "stuck", "force": 16}
    _run(engine, "travel", {"place": spot.id})
    s.move("pc", spot.id)
    pc = s.pc()
    pc.abilities["str"] = 60
    before = pc.xp
    out = _run(engine, "break_in", {"how": "force"})
    assert rooms[0]["dungeon"]["door"]["state"] == "open", [o.tell for o in out]
    assert pc.xp == before and "XP" not in out[-1].tell


def test_a_creature_shown_by_a_title_answers_to_its_kind():
    """Playtest 2026-11-17 #47: "I stab at the dog" at the dying "beast they kept" (a dog)
    found nobody once the fight was over, and the turn built nothing."""
    s, engine, _spot, rooms = _in_a_room()
    made = engine._bring_in("dog", name="the beast they kept")
    ref = made[0]["ref"]
    assert scope.in_the_room(s, "the dog") == ref


def test_a_tell_gives_a_kind_its_article_after_a_verb():
    """Playtest 2026-11-17 #28: "misses dire rat" — "the" three words back ("the dagger")
    was taken for the rat's own determiner."""
    said = names.with_articles(
        "Vesna Kroll's attack with the dagger misses dire rat (8 against AC 11).",
        ["dire rat"])
    assert "misses the dire rat" in said
    assert names.with_articles("the great bat hisses.", ["bat"]) == "the great bat hisses."
    assert names.with_articles("The ravenous rat bites.", ["rat"]) == "The ravenous rat bites."


def test_a_meeting_on_the_road_is_named_by_its_kind_in_lower_case():
    """Playtest 2026-11-16 N7: a street meeting minted "Commoner" and "second Commoner",
    the stat-block kind capitalised as a proper name on the people list."""
    s, engine, _spot, _rooms = _in_a_room()
    met = ontheway.Meeting(kind="squabble", roll=50, words=("commoner", "townsfolk"),
                           count=2, template="commoner-level-1")
    made = engine._meet_on_the_way(met, zone="near")
    shown = [s.people[m["ref"]].name for m in made]
    assert all(n[:1].islower() for n in shown), shown
