"""The brief's space sections (Lane B): HERE outside, ROADS OUT with facts, THE LAND AROUND.

Measured 2026-09-28 (docs/playtest-2026-09-28.md, items 17.4, 19, 20.1): the brief named
the roads out and nothing else, so the prose invented "north to Dustgate, west to
Grotburrow" (the world has no bearings) and never mentioned three of the five routes; no
continent, nation or climate fact reached it, so the page described "endless flat desert"
and then a forest; and standing outside, HERE still said "Vormoor, a village".
"""
from __future__ import annotations

import re

from gm import prompts
from rules import geography, places
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from world.loader import load_cached

AURVANTIS = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = "bde94b038cba"
DIGIT = re.compile(r"\d")


def _stand(world, sid, at=""):
    s = Scene(location_id=sid)
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    s.add(pc)
    e = Engine(s, Dice(seed=3), world=world)
    e.place_party(at)
    return s, e


def _brief(world, s, e, reading=None, report=None):
    return prompts.scene_brief(world, s, world.get(s.location_id), here=e.here(),
                               known=e.places(), reading=reading, report=report)


def _block(text, head):
    lines = text.split("\n")
    i = next(n for n, ln in enumerate(lines) if head in ln)
    out = [lines[i]]
    for ln in lines[i + 1:]:
        if not ln.startswith("    "):
            break
        out.append(ln)
    return out


def test_roads_out_carry_their_facts_in_words_and_no_numbers(worlds):
    """17.4 and 19: each road with its kind of destination, how, where it leaves from,
    how long in days as words, and what it crosses — never a mileage or an hour count
    (the third law: no number a model can do sums with), and never a compass bearing the
    world did not state."""
    checked = 0
    for row in worlds.play.get("settlements") or []:
        e0 = worlds.get(row["id"])
        roads = geography.roads_out(worlds, e0)
        if not roads:
            continue
        s, e = _stand(worlds, e0.id)
        report: dict = {}
        text = _brief(worlds, s, e, report=report)
        block = _block(text, "ROADS OUT OF")
        assert "no compass bearing is recorded — never give one" in block[0]
        assert [ln.strip().split(" — ")[0] for ln in block[1:]] == [r.to_name for r in roads]
        for ln, r in zip(block[1:], roads):
            assert r.time_words in ln and r.leaves_from in ln
            assert not DIGIT.search(ln), ln
            assert not re.search(r"\b(north|south|east|west)\b", ln, re.I), ln
        assert report["facts"]["roads_out"]["roads"] == [r.to_name for r in roads]
        checked += 1
        if checked >= 4:
            break
    assert checked


def test_vormoor_s_roads_read_as_the_world_wrote_them():
    """Road column (Q12): Dustgate is 27 hours — about three days — on foot."""
    s, e = _stand(AURVANTIS, VORMOOR)
    block = _block(_brief(AURVANTIS, s, e), "ROADS OUT OF VORMOOR")
    assert block[1] == ("    Dustgate — a town; by road, from the outskirts; about three "
                        "days on foot; farmland, then mountain.")


def test_pangrella_s_town_is_sea_only():
    """Pangrella's only route is open sea: the block is one row, by sea, and no road."""
    world = load_cached("fixtures/pangrella-campaign.json")
    s, e = _stand(world, "5bbd0c40345f")
    block = _block(_brief(world, s, e), "ROADS OUT OF")
    assert len(block) == 2 and "by sea" in block[1] and "by road" not in block[1]


def test_a_bearing_question_gets_the_bearings_fact():
    """16.6: asked "where another larger city might be", the page answered with compass
    points. On a turn that asks which way, the brief says the world records none and
    how to answer instead."""
    s, e = _stand(AURVANTIS, VORMOOR)
    reading = {"actions": [{"act": "look",
                            "object": "a bearing of where another larger city might be"}]}
    text = _brief(AURVANTIS, s, e, reading=reading)
    assert "BEARINGS (fact): the world records no compass direction" in text
    assert "BEARINGS" not in _brief(AURVANTIS, s, e)


def test_the_land_around_is_the_world_s_own_words_outside():
    """19: Drossakar's "ash-fields, iron-rich badlands, geothermal vents" never reached
    the brief. Outside the village it does, unedited, with the ground close by and
    further out; in the market it does not (noise)."""
    s, e = _stand(AURVANTIS, VORMOOR,
                  next(p.id for p in places.home_set(AURVANTIS.get(VORMOOR))
                       if p.name == "the market"))
    assert "THE LAND AROUND" not in _brief(AURVANTIS, s, e)
    e._journeyed = ""
    e.run(e.validate([{"op": "travel", "actor": s.pc().ref, "because": "t",
                       "params": {"place": "the outskirts"}}], origin="author:test"))
    report: dict = {}
    text = _brief(AURVANTIS, s, e, report=report)
    block = _block(text, "THE LAND AROUND VORMOOR")
    assert "    underfoot here: farmland." in block
    # Since 2026-10-05 the land Vormoor sits in is close by too, and named (the
    # hinterland, docs/place-doors.md): the badlands and the ridgelines a walk out.
    assert "    close by: farmland, desert, hills." in block
    walk = next(ln for ln in block if ln.startswith("    within a walk: "))
    assert "the badlands (desert, " in walk and "the ridgelines (hills, " in walk
    assert not any(ch.isdigit() for ch in walk), walk          # words, never numbers
    assert any("ash-fields, iron-rich badlands, geothermal vents" in ln for ln in block)
    assert any(ln.startswith("    weather: hot, dry") for ln in block)
    facts = report["facts"]["land_around"]
    assert "ash-fields" in facts["lexicon"]
    assert facts["near"] == ["farmland", "desert", "hills"]
    assert facts["reaches"] == ["the badlands", "the ridgelines"]


def test_ground_the_player_names_that_is_not_there_is_said_before_the_plan():
    """20.2's other half: the planner is told there is no woodland before it plans the
    walk into the trees, so the refusal is not its first news of it."""
    s, e = _stand(AURVANTIS, VORMOOR)
    reading = {"actions": [{"act": "go", "place": "the gnarled dense trees"}]}
    text = _brief(AURVANTIS, s, e, reading=reading)
    assert "    not here: woodland (there is none near Vormoor)." in text


def test_here_says_outside_when_the_party_is(worlds):
    """20.1: outside, the HERE line said the settlement's name as if the party were in
    its market, and THE PLACES HERE was one flat list. Now HERE says outside, and the
    list says which side of the edge each name is on."""
    row = next(r for r in worlds.play["settlements"]
               if places._settled(worlds.get(r["id"]), ""))
    e0 = worlds.get(row["id"])
    s, e = _stand(worlds, e0.id)
    inside = _brief(worlds, s, e)
    assert f"\nHERE: {e0.name}, " in inside
    assert f"IN {e0.name.upper()}: " in inside and f"OUTSIDE {e0.name.upper()}: " in inside
    e._journeyed = ""
    e.run(e.validate([{"op": "travel", "actor": s.pc().ref, "because": "t",
                       "params": {"place": "the outskirts"}}], origin="author:test"))
    if places.setting_of(s.at) != "outside":
        return                                   # stopped in town; the walk is covered
    outside = _brief(worlds, s, e)
    assert f"\nHERE: outside {e0.name}, " in outside
    assert f"The party is at the outskirts, outside {e0.name}, and not anywhere else" \
        in outside
