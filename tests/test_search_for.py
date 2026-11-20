"""A search looks for what it names (the owner's ruling, playtest 2026-11-20 #19).

"If I type to search for anything I should be searching for that thing, not tracks. If I
look for a river and it tells me there are no tracks this is a bug." #28 of that game, "I
search the woods for the cave everyone has a story about", owed no op; the plan rolled a
track and a secret-door check and the page answered about footprints and seams. Every
search that names its object is now the engine's search, and the engine answers about that
object with its own finders (research note docs/research/2026-11-20-hex-sites.md).
"""
from __future__ import annotations

import pytest

from gm import acts_to_ops, interpret
from rules import places as places_mod
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene


def _party(world):
    town = world.play["settlements"][0]["id"]
    s = Scene(location_id=town)
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    pc.hp = pc.hp_base = 60
    s.add(pc)
    e = Engine(s, Dice(seed=3), world=world)
    e.place_party("")
    return s, e, pc


def _search(e, sought, seeking=""):
    params = {"skill": "perception", "search": True, "take": 10, "sought": sought}
    if seeking:
        params["seeking"] = seeking
    r = e.run(e.validate([{"op": "check", "actor": e.scene.pc().ref, "params": params}]))
    if r.awaiting:
        r = e.resume(10)
    return [o for o in r.outcomes if o.op == "check"][0]


def test_a_search_for_a_river_answers_about_water_never_tracks(worlds):
    """"I look for a river" is answered about water: what is wet here or a step away, or,
    out on open ground with none, that water is had by living off the land (CRB p.107). The
    page never says "no tracks"."""
    s, e, pc = _party(worlds)
    out = _search(e, "a river", "water")
    assert "water" in out.tell.lower(), out.tell
    assert "track" not in out.tell.lower()


def test_a_search_for_a_named_person_here_finds_them(worlds):
    s, e, pc = _party(worlds)
    who = instantiate("guildhand", scene=s, name="Marra Vell")
    s.add(who)
    e.place_party(s.at)
    out = _search(e, "Marra Vell", "a person")
    assert "Marra Vell is here" in out.tell, out.tell
    assert out.verdict == "success"


def test_a_search_for_an_item_here_finds_it(worlds):
    s, e, pc = _party(worlds)
    s.props.append({"name": "a brass key", "owner": "", "from_": "", "state": "intact",
                    "turn": 0, "at": s.at})
    out = _search(e, "the brass key", "a thing")
    assert "There is a brass key here" in out.tell, out.tell


def test_a_search_for_something_not_here_says_so_about_that_thing(worlds):
    """The thing is not there: the answer names it, and says nothing of tracks or secret
    doors (which are looked for only when asked for)."""
    s, e, pc = _party(worlds)
    out = _search(e, "the silver locket", "a thing")
    assert "silver locket" in out.tell and "does not find it" in out.tell, out.tell
    assert "track" not in out.tell.lower() and "door" not in out.tell.lower()
    assert out.verdict == "failure"


def test_a_search_for_a_cave_with_none_known_says_there_is_none_here(worlds):
    s, e, pc = _party(worlds)
    out = _search(e, "the cave everyone has a story about", "a place")
    assert "the cave everyone has a story about" in out.tell, out.tell
    assert "does not find it here" in out.tell


def test_a_search_for_a_place_close_by_says_where_it_is(worlds):
    s, e, pc = _party(worlds)
    here = e.here()
    near = next((p for p in e.places() if p.id in (here.exits or ())), None)
    if near is None:
        pytest.skip("nothing next door")
    out = _search(e, near.name, "a place")
    assert "close by" in out.tell, out.tell


def test_the_reader_carries_what_a_search_is_for(worlds):
    """The schema reader names the kind (`interpret.SEEKING`, closed) and the act table
    hands the words and the kind to the engine's search, wherever the reader put it."""
    assert "water" in interpret.SEEKING and interpret.SEEKING[0] == "anything"
    s, e, pc = _party(worlds)
    frame = {"actions": [{"act": "search", "object": "a river", "seeking": "water",
                          "span": "look for a river"}]}
    rows = acts_to_ops.table(frame, s, places=e.places(), sentence="I look for a river")
    built = [b for r in rows for b in r.intents if b["op"] == "check"]
    assert built and built[0]["params"]["sought"] == "a river"
    assert built[0]["params"]["seeking"] == "water"


def test_a_search_for_somebody_not_here_says_so_about_them(worlds):
    """Live 2026-11-20: "I look around the woods for the harbourmaster", who was at the
    docks. The answer names them, as a person."""
    s, e, pc = _party(worlds)
    out = _search(e, "the harbourmaster", "a person")
    assert "does not find them here" in out.tell, out.tell


def test_a_search_for_a_thing_at_a_heard_landmark_does_not_walk_into_the_place(worlds,
                                                                               monkeypatch):
    """Live 2026-11-20: "I search the woods for my lost silver locket", standing where the
    carter's old mine lies, found the mine and walked the party two hours into it. A search
    for a named thing looks for that thing; the heard way in waits for a search for it."""
    from rules import heard_places, ontheway

    monkeypatch.setattr(ontheway, "road", lambda *a, **k: None)
    s, e, pc = _party(worlds)
    woods = next((p for p in e.places() if places_mod.setting_of(p.id) == "outside"
                  and p.origin != "venture"), None)
    if woods is None:
        pytest.skip("no outside place")
    heard_places.record(s, {"name": "the old mine", "kind": "mine head",
                            "landmark": woods.id})
    e.place_party(woods.id)
    out = _search(e, "my lost silver locket", "a thing")
    assert s.at == woods.id, out.tell
    assert "silver locket" in out.tell


def test_the_plans_track_goes_when_no_look_for_tracks_was_asked_for(worlds):
    """Live 2026-11-20: "I look around the woods for the harbourmaster" was read `seek`;
    the engine said he was not here, and the plan's own `track` (with `follow`) rolled
    Survival against firm ground and the page told of footprints. Tracks are looked for
    only when the player asks (the owner, #19); a reading with `track` keeps its own."""
    s, e, pc = _party(worlds)
    frame = {"actions": [{"act": "seek", "target": "the harbourmaster",
                          "span": "look around the woods for the harbourmaster"}]}
    rows = acts_to_ops.table(frame, s, places=e.places(), sentence="…")
    plan = [{"op": "track", "actor": pc.ref, "params": {"follow": True}}]
    assert not any(r.get("op") == "track" for r in acts_to_ops.apply(plan, rows, frame, s))
    asked = {"actions": [{"act": "track", "span": "look for tracks"}]}
    rows = acts_to_ops.table(asked, s, places=e.places(), sentence="…")
    assert any(r.get("op") == "track" for r in acts_to_ops.apply([], rows, asked, s))
