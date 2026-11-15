"""The way deeper a venture may hold, and the dungeon behind it (rules/dungeons.py).

The owner, 2026-11-15: "perhaps a percentage roll to turn any of those ventures into a full
dungeon, like you go to the cave and you find a boulder that has broken revealing a small
gap and a passage". Measured before this: every venture was three named spots and maybe
one creature — no rooms in sequence, no doors, no traps, no placed treasure, and `hazards`
told a trap to be "narrated, not rolled".
"""
from __future__ import annotations

import pytest

from rules import dungeons, places
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

VYRAKON = "5bbd0c40345f"
WORLD = loader.load_cached("fixtures/pangrella-campaign.json")


def _room(seed=3):
    s = Scene(location_id=VYRAKON)
    s.add(load_pc("fixtures/pc-kesst.json"))
    return s, Engine(s, Dice(seed=seed), world=WORLD)


def _run(engine, op, params, actor="pc"):
    # Hidden: the engine rolls the player's die, so a test never waits on the popup.
    intents = engine.validate([{"op": op, "actor": actor, "because": "t", "params": params,
                                "visibility": "hidden"}], origin="author:test")
    return engine.run(intents).outcomes[-1]


@pytest.fixture
def always(monkeypatch):
    """Every fitting venture holds a way down: the seed forced, as the brief allows."""
    monkeypatch.setattr(dungeons, "chance", lambda *a, **k: 100)


def _into_a_cave(engine, s):
    out = _run(engine, "venture", {"kind": "cave"})
    head = next(p for p in s.founded if p["id"] == s.at)
    return out, head


def test_the_roll_is_seeded_off_the_venture_and_refused_on_the_rooftops():
    """The same cave always has, or lacks, the same way down; the rooftops and the alley
    never have one (the owner: "A rooftop wouldnt make sense for this")."""
    ids = [f"~underground:somewhere/the-cave-{i}" for i in range(400)]
    assert [dungeons.rolled(i) for i in ids] == [dungeons.rolled(i) for i in ids]
    hits = sum(dungeons.rolled(i) <= dungeons.BASE_CHANCE for i in ids)
    assert 50 <= hits <= 110, hits          # the 20% base, near enough over 400 caves
    assert not dungeons.fits("rooftops") and not dungeons.fits("alley")
    assert all(dungeons.fits(k) for k in ("cave", "mine", "ruins", "crypt", "sewers",
                                          "cellar", "tower"))


def test_a_layout_is_four_to_six_rooms_with_a_climax_a_setback_and_a_loop():
    """Five Room Dungeon skeleton: the last room the climax (a guarded fight and the
    hoard), the room before it a trap; five rooms or more carry one loop (Brogue and
    Unexplored both abandoned the dead-end tree)."""
    sizes = set()
    for i in range(60):
        head = f"~ruins:somewhere/the-ruins-{i}"
        rooms = dungeons.generate(head, "ruins", head + "/the-undercroft", "ruins",
                                  dungeons.FEATURES["ruins"][0], apl=1)
        sizes.add(len(rooms))
        d = [r["dungeon"] for r in rooms]
        assert d[-1]["role"] == "climax" and d[-1]["stock"] == "monster" and d[-1]["cache_gp"]
        assert d[0]["door"]["name"] == "the trapdoor" and d[0]["door"]["force"] == 16
        assert any(x["trap"] for x in d)
        if len(rooms) >= 5:
            assert sum(bool(r["exits"]) for r in rooms) == 2
        assert dungeons.generate(head, "ruins", head + "/the-undercroft", "ruins",
                                 dungeons.FEATURES["ruins"][0], apl=1) == rooms
    assert sizes == {4, 5, 6}


def test_a_cave_way_down_is_found_walked_trapped_and_left(always, monkeypatch):
    """End to end through the ops a turn plans: venture, travel to the deep chamber, a
    search finds the split boulder, the rooms exist only then, a trap rolls its printed
    numbers, and the way back up is open."""
    s, engine = _room(seed=11)
    out, head = _into_a_cave(engine, s)
    assert head.get("deeper") and head["deeper"]["feature"]["name"] == "the split boulder"
    assert not any(p.get("origin") == "dungeon" for p in s.founded)   # nothing before found
    spot = head["deeper"]["spot"]
    _run(engine, "travel", {"place": spot})
    if not head["deeper"]["found"]:
        hit = _run(engine, "check", {"skill": "perception", "search": True})
        while not head["deeper"]["found"]:
            hit = _run(engine, "check", {"skill": "perception", "search": True})
        assert "split boulder" in hit.tell
    rooms = [p for p in s.founded if p.get("origin") == "dungeon"]
    assert 4 <= len(rooms) <= 6
    first = rooms[0]
    assert first["parent"] == spot and first["dungeon"]["door"] is None
    # Walk in. A cave has passages, not doors: nothing shuts the way.
    s.pc().hp = s.pc().hp_max = 200
    went = _run(engine, "travel", {"place": first["id"]})
    assert s.at == first["id"], went.tell
    assert first["name"] in went.tell.lower() or first["name"] in went.tell
    # And back up: the way up is always there.
    if s.in_encounter:
        s.end_encounter()
    back = _run(engine, "travel", {"place": spot})
    assert s.at == spot, back.tell


def test_a_stuck_door_refuses_the_walk_until_it_is_forced(always):
    """A good wooden door stuck at the CRB's 16 refuses the walk with the rule's sentence
    and gives to a Strength check; the exits row asks the same question."""
    s, engine = _room(seed=4)
    spot = places.find(engine.places(), engine.here().id)
    head = "~ruins:x/the-ruins"
    rooms = dungeons.generate(head, "ruins", spot.id, "ruins", dungeons.FEATURES["ruins"][0], 1)
    s.founded.extend(rooms)
    first = rooms[0]
    refused = _run(engine, "travel", {"place": first["id"]})
    assert s.at == spot.id and "stuck" in refused.tell, refused.tell
    s.pc().abilities["str"] = 40                        # cannot fail a DC 16
    forced = _run(engine, "break_in", {"how": "force"})
    assert first["dungeon"]["door"]["state"] == "open", forced.tell
    assert forced.dc == 16
    _run(engine, "travel", {"place": first["id"]})
    assert s.at == first["id"]


def test_traps_roll_the_crb_block_and_a_search_finds_them_first(always):
    """The pit trap's printed numbers: Reflex 20 or 2d6 for twenty feet (CRB p.420); a
    search one room back at Perception 20 finds it, and a found pit is stepped round."""
    s, engine = _room(seed=2)
    pc = s.pc()
    trap = {"id": "pit-trap", "on": "room", "found": False, "armed": True}
    pc.hp = pc.hp_max = 200
    rolls, fx, said = dungeons.spring(engine, trap, [pc])
    assert any("Reflex" in r.label for r in rolls)
    assert not trap["armed"] and said[0].startswith("A pit trap goes off")
    falls = [e for e in fx if e.get("kind") == "damage"]
    for e in falls:
        assert 2 <= e["amount"] <= 12 and e["origin"] == "rule:trap/pit-trap"
    arrow = {"id": "arrow-trap", "on": "door", "found": False, "armed": True}
    rolls, fx, said = dungeons.spring(engine, arrow, [pc])
    assert rolls[0].modifier_total == 15


def test_disable_device_at_a_found_trap_uses_the_traps_dc(always):
    s, engine = _room(seed=6)
    spot = engine.here()
    head = "~ruins:x/the-ruins"
    rooms = dungeons.generate(head, "ruins", spot.id, "ruins", dungeons.FEATURES["ruins"][0], 1)
    rooms[0]["dungeon"]["trap"] = {"id": "pit-trap", "on": "room", "found": True, "armed": True}
    s.founded.extend(rooms)
    out = _run(engine, "check", {"skill": "disable device", "dc": {"band": "easy"}})
    if out.dc:                                   # Kesst is trained; refused if not
        assert out.dc["value"] == 20
        trap = rooms[0]["dungeon"]["trap"]
        assert (not trap["armed"]) == (out.verdict == "success") or trap.get("sprung")


def test_a_strength_check_beside_a_stuck_door_is_the_doors_own_check(always):
    """Measured live 2026-11-15: "I grab the iron ring and heave the stuck trapdoor open"
    was planned as a plain Strength check at the plan's DC 10, rolled 9, and nothing it
    rolled could open the trapdoor. The check at a shut door is the door's, at the CRB's
    16, and opens it."""
    s, engine = _room(seed=4)
    spot = engine.here()
    rooms = dungeons.generate("~ruins:x/the-ruins", "ruins", spot.id, "ruins",
                              dungeons.FEATURES["ruins"][0], 1)
    s.founded.extend(rooms)
    s.pc().abilities["str"] = 40
    out = _run(engine, "check", {"skill": "strength", "dc": {"band": "easy"}})
    assert out.dc == 16 and rooms[0]["dungeon"]["door"]["state"] == "open", out.tell
    # And Disable Device at a door with no lock is an ordinary check, not a forcing.
    rooms[1]["dungeon"]["door"] = {"name": "a good wooden door", "state": "stuck", "force": 16}
    s.move("pc", rooms[0]["id"])
    out = _run(engine, "check", {"skill": "disable device", "dc": {"band": "easy"}})
    assert rooms[1]["dungeon"]["door"]["state"] == "stuck"


def test_a_walk_to_a_room_named_like_a_fixture_is_a_walk_there():
    """Measured live 2026-11-15: "I walk to the long gallery" (a dungeon room one exit
    away) was read with fixture `gallery`, and the plan's travel was dropped as a walk
    inside the undercroft. A place of its own by that exact name is a walk there."""
    from gm import interpret
    from rules.places import Place

    here = Place(id="x/the-undercroft", name="the undercroft")
    room = Place(id="x/the-undercroft/the-long-gallery", name="the long gallery")
    go = {"act": "go", "place": "the long gallery", "fixture": "gallery"}
    assert not interpret.within_place(go, (here, room), here.id)
    # With no such place, the gallery is still the room's own fixture.
    assert interpret.within_place(go, (here,), here.id)
