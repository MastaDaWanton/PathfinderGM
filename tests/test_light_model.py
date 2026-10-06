"""Light, darkness, and smoke as a miss chance (alchemy plan §16.3-§16.5).

CRB, Vision and Light (legacy.aonprd.com/coreRulebook/additionalRules.html): dim light —
"outside at night with a moon in the sky ... the area between 20 and 40 feet from a
torch" — gives "concealment (20% miss chance in combat)"; in darkness "creatures without
darkvision are effectively blinded", 50%. Low-light vision doubles a light's radius;
darkvision sees "dark areas within 60 feet". A sunrod lights 30 ft and raises 60.

Measured before (build/alchemy, 3bbd361): there was no light model at all
(`reactions.py`: "the map has no light level yet"), so a sunrod was a blade coating
dealing 1d4 fire and a fight in a cave was fought as if at noon; a fog cloud's squares
were walls, so whoever stood in one was untargetable (total cover), where the book gives
20% within 5 ft and 50% beyond. The owner's ruling (open point 8): miss chance only now;
Stealth and Perception in the dark are a later pass (NOT read here — `Actor.concealment`
is the only reader).
"""
from __future__ import annotations

import pytest

from rules import places
from rules.bestiary import instantiate
from rules.crafting import Stock
from rules.dice import Dice
from rules.engine import Engine, Manifestation, Scene
from rules.sheet import load_pc

ROAD = "5bbd0c40345f~road"
CAVE = "5bbd0c40345f~underground:the-cave"
NOON, MIDNIGHT = 12 * 60, 0
SUNROD = [{"type": "light", "radius_ft": 30, "raised_ft": 60,
           "duration": {"amount": 6, "unit": "hour"}}]


def _put(s, at):
    """Everyone here goes where the scene goes: who is here is derived from each
    person's own `at` (`Scene.actors`), so moving the scene alone empties it."""
    for a in list(s.actors.values()):
        a.at = at
    s.at = at


def _board(at=ROAD, clock=MIDNIGHT, gap=4):
    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    e = Engine(s, Dice(seed=5))
    e._ensure_encounter("pc")
    _put(s, at)
    s.clock_minutes = clock
    s.positions["pc"] = (2, 10)
    s.positions["c1"] = (2 + gap, 10)
    s.resync_zones()
    return s, e, pc, s.actors["c1"]


def _eyes(actor, tag):
    actor.add_condition("probe-eyes", source="test")
    actor.effects[-1].tags = (tag,)


def test_the_ambient_light_is_the_place_and_the_clock():
    s, e, pc, thug = _board()
    _put(s, ""); s.clock_minutes = MIDNIGHT
    assert s.ambient_light() == "normal"          # placed nowhere: nothing is known
    _put(s, ROAD); s.clock_minutes = NOON
    assert s.ambient_light() == "bright"
    s.clock_minutes = MIDNIGHT
    assert s.ambient_light() == "dim"             # "outside at night with a moon"
    _put(s, CAVE)
    assert s.ambient_light() == "dark"            # "most caverns"


def test_a_roofed_place_is_lit_by_its_own_lamps(monkeypatch):
    s, e, pc, thug = _board()
    monkeypatch.setattr(places, "is_indoors", lambda *a, **k: True)
    assert s.ambient_light() == "normal"


def test_dim_light_is_20_percent_and_darkness_50_unless_the_eyes_say_otherwise():
    s, e, pc, thug = _board(at=ROAD, clock=MIDNIGHT)
    assert e._concealment_of(pc, thug) == (20, "dim light")
    s.clock_minutes = NOON
    assert e._concealment_of(pc, thug) == (0, "")
    _put(s, CAVE)
    assert e._concealment_of(pc, thug) == (50, "darkness")
    _eyes(pc, "sense.darkvision.60")
    assert e._concealment_of(pc, thug) == (0, "")
    s.positions["c1"] = (16, 10)                  # 65 ft: past the darkvision
    assert e._concealment_of(pc, thug)[0] == 50


def test_low_light_vision_sees_a_moonlit_night_as_lit():
    """The Bestiary's low-light vision "retains the ability to distinguish color and
    detail" in moonlight and starlight; read here as seeing the night's dim as normal."""
    s, e, pc, thug = _board(at=ROAD, clock=MIDNIGHT)
    _eyes(pc, "sense.low-light")
    assert e._concealment_of(pc, thug) == (0, "")


def test_a_sunrod_raises_the_light_at_30_and_60_feet_and_the_miss_chance_with_it():
    """Struck in the hand (`use_item how=light`), it moves with its carrier: normal light
    to 30 ft, one step brighter to 60 (CRB light table)."""
    s, e, pc, thug = _board(at=CAVE)
    pc.stock["sunrod#1"] = Stock(base="Sunrod", count=1, specs=[dict(SUNROD[0])])
    assert e._concealment_of(pc, thug) == (50, "darkness")
    out = e.run(e.validate([{"op": "use_item", "actor": "pc", "because": "she strikes it",
                             "params": {"item": "sunrod#1", "how": "light"}}]))
    assert "strikes Sunrod" in out.outcomes[0].tell
    assert any(x.get("kind") == "grant" and x.get("light") for x in out.outcomes[0].effects)
    assert s.light_at(s.positions["c1"]) == "normal"               # 20 ft
    assert e._concealment_of(pc, thug) == (0, "")
    s.positions["c1"] = (11, 10)                                   # 45 ft: raised ring
    assert s.light_at(s.positions["c1"]) == "dim"
    assert e._concealment_of(pc, thug) == (20, "dim light")
    s.positions["c1"] = (16, 10)                                   # 70 ft: dark
    assert e._concealment_of(pc, thug) == (50, "darkness")
    assert "sunrod#1" not in pc.stock


def test_low_light_vision_doubles_the_sunrods_radius():
    s, e, pc, thug = _board(at=CAVE)
    pc.stock["sunrod#1"] = Stock(base="Sunrod", count=1, specs=[dict(SUNROD[0])])
    e.run(e.validate([{"op": "use_item", "actor": "pc", "params": {"item": "sunrod#1",
                                                                   "how": "light"}}]))
    s.positions["c1"] = (11, 10)                                   # 45 ft
    viewer = s.actors["c1"]
    _eyes(viewer, "sense.low-light")
    assert s.light_at(s.positions["c1"], viewer=viewer) == "normal"   # inside 60


def test_the_miss_chance_is_rolled_on_a_real_blow_in_the_dark():
    s, e, pc, thug = _board(at=CAVE, gap=1)
    res = e.run(e.validate([{"op": "attack", "actor": "pc", "target": "c1",
                             "because": "she swings",
                             "params": {"weapon": pc.wielded_key()}}]))
    for face in (20, 6, 5, 4):
        if res.status == "complete":
            break
        res = e.resume(face=face)
    labels = [r.label for o in res.outcomes for r in o.rolls]
    assert any("miss chance (darkness)" in x for x in labels), labels


def _fog(s, e, centre=(6, 10), size=20):
    e._manifest({"type": "manifest", "what": "a bank of fog", "terrain": "obscuring",
                 "shape": "radius", "size": size},
                {"square": list(centre), "caster": "pc", "source": "fog cloud"})


def test_fog_is_20_percent_within_5_feet_and_50_beyond_never_total_cover():
    """Fog cloud (CRB): "A creature within 5 feet has concealment (attacks have a 20%
    miss chance). Creatures farther away have total concealment (50% miss chance ...)".
    It was total COVER: obscuring squares were walls to `cover_of`, and the attack
    refused itself. The same reader serves the spell's manifest and a smokestick's."""
    from rules import position

    s, e, pc, thug = _board(at=ROAD, clock=NOON, gap=4)
    _fog(s, e)
    assert position.cover_of(s, pc, thug) != "total"
    assert e._concealment_of(pc, thug) == (50, "thick obscuring smoke")
    s.positions["c1"] = (3, 10)
    s.positions["pc"] = (2, 10)
    _fog(s, e, centre=(3, 10), size=5)
    assert e._concealment_of(pc, thug) == (20, "obscuring smoke")


def test_a_wall_is_still_total_cover():
    from rules import position

    s, e, pc, thug = _board(at=ROAD, clock=NOON, gap=4)
    for y in range(0, 30):
        s.grid.blocked.add((4, y))
    assert position.cover_of(s, pc, thug) == "total"


def test_a_smokestick_lit_lays_its_smoke_at_the_users_feet():
    s, e, pc, thug = _board(at=ROAD, clock=NOON, gap=4)
    pc.stock["smoke#1"] = Stock(base="Smokestick", count=1, specs=[
        {"type": "manifest", "what": "a cloud of thick smoke", "terrain": "obscuring",
         "shape": "radius", "size": 10, "duration": {"amount": 10, "unit": "round"}}])
    out = e.run(e.validate([{"op": "use_item", "actor": "pc", "params": {
        "item": "smoke#1", "how": "light"}}]))
    assert "thick smoke rises" in out.outcomes[0].tell.lower()
    assert (2, 10) in s.grid.obscuring
    assert e._concealment_of(thug, pc)[0] == 50
