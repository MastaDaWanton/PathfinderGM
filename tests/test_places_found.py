"""The places the player has found: the fog-of-war chart's record and its graph.

The engine kept no record of where the player had been; the owner's fog-of-war map needs
it. The owner, 2026-09-29: "the fog of war only being able to see places conected to where
you have been before … instead of displaying the number of places the rules know you
display the number of places found by the user"; and earlier, "new place[s] that the
engine creates should be added to this map". Found the same day (docs/fix-interfaces.md,
"The place map, with fog of war"): only `rules/schemes.py` kept a `visited` list, for its
own scheme. The mock stood in for the record with a `sessionStorage` set, which a reload
of another browser, or the packaged app, forgot.

What these hold: `Scene.been` is written at the one door every arrival goes through
(`Scene.stand`), an old save is seeded from where it stands and round-trips byte for
byte, and the chart (`play/places_found.py`) shows every place stood in and every place
one way from them, by name, and nothing else — read live, so a place the engine makes
later joins it.

World-agnostic where the machinery is (the standing instruction of 2026-09-28): the
`worlds` fixture runs each test once per export.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from django.test import Client, override_settings

from play import campaign as cm
from play import exits as exits_mod
from play import places_found
from rules import places, states
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene


class _Quiet:
    """Dice that never meet anything on the way (every d100 check misses), so a walk
    tested here is the walk and not a hawker — the Lane B tests' own."""

    def __init__(self, real):
        self.real = real

    def __getattr__(self, name):
        return getattr(self.real, name)

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        if notation == "1d100":
            return self.real.given(100, modifiers, label, notation)
        return self.real.roll(notation, modifiers, label, visibility)


def _settled(world):
    for row in world.play.get("settlements") or []:
        e = world.get(row["id"])
        if e is not None and places._settled(e, ""):
            yield e


def _party(world, town_id, at=""):
    s = Scene(location_id=town_id)
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    pc.hp = pc.hp_base = 60
    s.add(pc)
    e = Engine(s, Dice(seed=3), world=world)
    e.place_party(at)
    e.dice = _Quiet(e.dice)
    return s, e, pc


def _town(world):
    """The first settlement with a ring and at least a few rooms: somewhere to walk."""
    for loc in _settled(world):
        s, e, pc = _party(world, loc.id)
        if len(e.places()) >= 6 and any(places.is_ring(p.id) for p in e.places()):
            return loc
    pytest.skip("no settlement to walk in")


def _travel(e, pc, place_id):
    out = e.run(e.validate([{"op": "travel", "actor": pc.ref, "because": "t",
                             "params": {"place": place_id}}], origin="author:test"))
    return out.outcomes[0]


def _next_door(e, world, avoid=()):
    return next(x for x in exits_mod.exits(e, world)
                if x["group"] == "next_door" and not x["blocked"] and x["id"] not in avoid)


def _want(pc, town):
    tag = states.wanted_tag(town)
    pc.apply_effect(ActiveEffect(name="wanted", kind="situation", key=f"test:{tag}",
                                 source="test", origin="test",
                                 duration="until-dismissed", tags=(tag,)))


# --- the record ---------------------------------------------------------------------------

def test_travel_adds_where_the_party_went_in_the_order_it_went(worlds):
    """The engine kept no record of where the player had been; the owner's fog-of-war
    map needs it. A walk of two exits leaves three places on the record, first first."""
    loc = _town(worlds)
    s, e, pc = _party(worlds, loc.id)
    start = s.at
    assert s.been == [start]
    one = _next_door(e, worlds)
    assert _travel(e, pc, one["id"]).status == "resolved"
    two = _next_door(e, worlds, avoid={start})
    assert _travel(e, pc, two["id"]).status == "resolved"
    assert s.been == [start, one["id"], two["id"]]
    # Walking back is not a new place: the record does not repeat itself.
    assert _travel(e, pc, one["id"]).status == "resolved"
    assert s.been == [start, one["id"], two["id"]]


def test_a_refused_move_is_not_a_place_been(worlds):
    """A way the rules shut is not walked, so it is not on the record — the refusal's
    snapshot takes the scene back whole, the record with it."""
    loc = _town(worlds)
    s, e, pc = _party(worlds, loc.id)
    _want(pc, loc.id)
    shut = next((x for x in exits_mod.exits(e, worlds) if x["blocked"]), None)
    if shut is None:
        pytest.skip("no way out shut to the wanted from where this town is entered")
    assert _travel(e, pc, shut["id"]).status == "refused"
    assert s.been == [s.at]


def test_a_journey_adds_the_place_it_arrives_at(worlds):
    """A journey is an arrival like any other: the far town's way in joins the record,
    and the places of the town left behind stay on it."""
    for loc in _settled(worlds):
        s, e, pc = _party(worlds, loc.id)
        for p in e.places():
            if places.setting_of(p.id) != "outside":
                continue
            e.place_party(p.id)
            road = next((x for x in exits_mod.exits(e, worlds)
                         if x["journey"] and not x["blocked"]), None)
            if road is None:
                continue
            before = list(s.been)
            for _ in range(20):
                e.run(e.validate([{"op": "journey", "actor": pc.ref, "because": "t",
                                   "params": {"to": road["id"]}}], origin="author:test"))
                if s.location_id != loc.id:
                    break
            assert s.location_id == road["id"], "the journey reached the far end"
            assert s.been[:len(before)] == before
            assert s.at in s.been and s.at not in before
            assert s.at.startswith(s.location_id)
            return
    pytest.skip("no road out of anywhere in this world")


def test_calling_on_somebody_at_home_adds_their_house():
    """Calling on a house moves the party into it through the same door (`call_on` →
    `move`), so the house is on the record. The call-on machinery's own fixture world
    (tests/test_calling_on_people.py), with her regard high enough to be let in."""
    from gm import judgement
    from rules import attitude, population
    from rules.sheet import load_pc
    from world.loader import load_cached

    world = load_cached("fixtures/aurvantis-campaign.json")
    s = Scene(location_id=world.by_name("Vormoor", kind="CITY").id)
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = 10 * 60
    e = Engine(s, Dice(seed=3), world=world)
    e.place_party()
    rec = population.note(s, "a woman selling bread")
    rec["life"].update(work="baker", work_name="baker", mobility="resident")
    ref = judgement.embody_sought(s, "I talk to the woman selling bread.", world)
    body = s.people[ref]
    e.run(e.validate([{"op": "say", "params": {"words": "Good day.", "to": ref}}],
                     origin="author:test"))
    body.remove_effects(source="talk")
    attitude.set_regard(body, 80, "test")
    elsewhere = next(p for p in e.places() if p.id != s.at)
    e.run(e.validate([{"op": "travel", "params": {"place": elsewhere.name}}],
                     origin="author:test"))
    s.advance(12 * 60)                        # ten at night: she is at home
    call = e.run(e.validate([{"op": "call_on", "params": {"who": "her", "visit": True}}],
                            origin="author:test")).outcomes[0]
    assert call.status == "resolved", call.tell
    house = call.effects[0]["house"]
    assert s.at == house
    assert s.been[-1] == house and elsewhere.id in s.been


def test_a_new_campaign_has_been_only_where_its_story_begins(worlds, tmp_path):
    """Measured on the first draft, 2026-09-30: 24 of 24 new campaigns (seeds 0–7 in
    each export) began with the way in on the record as visited, because a campaign is
    stood at the way in before its start moves it to the market or guildhall it opens
    in. `Scene.begin_here` makes the record begin with the story."""
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        for seed in range(3):
            c = cm.new_campaign(f"pf-new-{seed}", seed=seed, world_source=str(worlds.source))
            assert c.scene.places_been() == [c.scene.at], seed


def test_only_stand_and_the_start_write_the_record():
    """`at` and `been` are written in one step (`Scene.stand`), so they cannot drift; the
    one other writer is the start's `begin_here`. A third writer is a door an arrival
    could go through without reaching the map."""
    allowed = {("rules/engine.py", "stand"), ("rules/engine.py", "begin_here")}
    found = set()
    for folder in ("rules", "gm", "play"):
        for path in Path(folder).rglob("*.py"):
            src = path.read_text(encoding="utf-8")
            for fn in ast.walk(ast.parse(src)):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for node in ast.walk(fn):
                    hit = False
                    if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                        hit = any(isinstance(t, ast.Attribute) and t.attr == "been"
                                  for t in targets)
                    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                        owner = node.func.value
                        hit = (node.func.attr in ("append", "extend", "insert", "remove",
                                                  "pop", "clear")
                               and isinstance(owner, ast.Attribute) and owner.attr == "been")
                    if hit:
                        found.add((path.as_posix(), fn.name))
    assert found == allowed, found


# --- the save -----------------------------------------------------------------------------

def test_a_save_that_has_not_moved_round_trips_byte_identically(worlds, tmp_path):
    """G1's rule for every new scene key: omitted at default. The record's default is
    where the party stands, so a campaign that has not moved writes no `been` at all,
    and load → save gives the same bytes."""
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        c = cm.new_campaign("pf-still", seed=5, world_source=str(worlds.source))
        path = c.save()
        text = path.read_text(encoding="utf-8")
        assert '"been":' not in text
        again = cm.Campaign.load(path)
        assert again.scene.places_been() == [again.scene.at]
        again.save()
        assert path.read_text(encoding="utf-8") == text


def test_an_old_save_is_seeded_from_where_it_stands(worlds, tmp_path):
    """A save written before the record has no `been`: it is seeded from `at`, the one
    place the save can prove the party stood, and comes back out byte for byte. A save
    that has moved since writes the record and keeps it."""
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        c = cm.new_campaign("pf-old", seed=5, world_source=str(worlds.source))
        e = c.engine()
        e.dice = _Quiet(e.dice)
        if c.scene.in_encounter:
            c.scene.end_encounter()
        row = next((x for x in exits_mod.exits(e, c.world)
                    if not x["journey"] and not x["blocked"]), None)
        if row is None:
            pytest.skip("nowhere to walk from this start")
        assert _travel(e, c.scene.pc(), row["id"]).status == "resolved"
        path = c.save()
        moved = json.loads(path.read_text(encoding="utf-8"))
        assert moved["scene"]["been"] == c.scene.places_been()
        assert len(moved["scene"]["been"]) >= 2
        # The same save as the build before the record wrote it.
        moved["scene"].pop("been")
        old = json.dumps(moved, indent=1)
        path.write_text(old, encoding="utf-8")
        again = cm.Campaign.load(path)
        assert again.scene.been == [again.scene.at] == [row["id"]]
        again.save()
        assert path.read_text(encoding="utf-8") == old


def test_the_record_survives_a_reload(worlds, tmp_path):
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        c = cm.new_campaign("pf-keep", seed=5, world_source=str(worlds.source))
        c.scene.been = [c.scene.at, "x~urban:somewhere"]
        path = c.save()
        text = path.read_text(encoding="utf-8")
        again = cm.Campaign.load(path)
        assert again.scene.been == [c.scene.at, "x~urban:somewhere"]
        assert again.save().read_text(encoding="utf-8") == text


# --- the chart ----------------------------------------------------------------------------

def _chart(e, world):
    return places_found.chart(e, world)


def test_one_exit_beyond_every_place_been_and_nothing_else(worlds):
    """The owner's rule (a): the chart shows every place stood in and every place one
    exit beyond ANY of them, by name — exactly the exits rows of the places been, and
    not one place more."""
    loc = _town(worlds)
    s, e, pc = _party(worlds, loc.id)
    for step in range(3):
        c = _chart(e, worlds)
        been = set(s.places_been())
        want = set(been)
        for pid in been:
            e2 = e
            want |= {x["id"] for x in exits_mod.ways_from(e2, worlds, [pid])[pid]
                     if not x["journey"]}
        assert {n["id"] for n in c["nodes"]} == want, step
        known = {p.id: p for p in e.places()}
        for n in c["nodes"]:
            assert n["name"] == known[n["id"]].name
            assert n["visited"] == (n["id"] in been)
            assert n["current"] == (n["id"] == s.at)
        assert sum(n["current"] for n in c["nodes"]) == 1
        # Lines only for ways out of places stood in.
        assert {x["from"] for x in c["edges"]} <= been
        if step < 2:
            _travel(e, pc, _next_door(e, worlds, avoid=been)["id"])


def test_near_is_the_exits_row_of_where_the_party_stands(worlds):
    loc = _town(worlds)
    s, e, pc = _party(worlds, loc.id)
    c = _chart(e, worlds)
    row = {x["id"] for x in exits_mod.exits(e, worlds) if not x["journey"]}
    assert {n["id"] for n in c["nodes"] if n["near"]} == row


def test_stubs_are_the_ways_out_of_places_only_seen(worlds):
    """Mudlet's exit stubs: a way drawn whose far end is not known yet. Every way out of
    a place seen and not stood in, to anywhere not stood in, is a stub; a stub never
    carries the far end's name or id, only its index in the anonymous layout."""
    loc = _town(worlds)
    s, e, pc = _party(worlds, loc.id)
    c = _chart(e, worlds)
    been = set(s.places_been())
    seen = [n["id"] for n in c["nodes"] if not n["visited"]]
    assert seen, "a town's way in has neighbours"
    ways = exits_mod.ways_from(e, worlds, seen)
    want = sorted((pid, x["group"]) for pid in seen for x in ways[pid] if x["id"] not in been)
    assert sorted((x["from"], x["group"]) for x in c["stubs"]) == want
    for x in c["stubs"]:
        assert set(x) == {"from", "group", "dashed", "toward"}
        assert x["dashed"] == (x["group"] != "next_door")
        assert x["toward"] is None or 0 <= x["toward"] < c["layout"]["size"]


def test_the_header_counts_places_found_not_the_places_the_rules_know(worlds):
    """The owner: "instead of displaying the number of places the rules know you display
    the number of places found by the user". Found is visited plus seen; the rules' own
    count is only the layout's size, and at the way in it is larger."""
    loc = _town(worlds)
    s, e, pc = _party(worlds, loc.id)
    c = _chart(e, worlds)
    assert c["found"] == len(c["nodes"])
    assert c["visited"] == sum(n["visited"] for n in c["nodes"]) == 1
    assert c["found"] < len(e.places()) == c["layout"]["size"]
    _travel(e, pc, _next_door(e, worlds)["id"])
    c2 = _chart(e, worlds)
    assert c2["visited"] == 2 and c2["found"] >= c["found"]


def test_the_layout_names_nothing(worlds):
    """The layout is the whole graph's shape for a stable drawing, and nothing more: no
    id or name of a place under the fog crosses to the page."""
    loc = _town(worlds)
    s, e, pc = _party(worlds, loc.id)
    c = _chart(e, worlds)
    text = json.dumps(c)
    shown = {n["id"] for n in c["nodes"]} | {r["to"] for r in c["roads"]}
    for p in e.places():
        if p.id not in shown:
            assert p.id not in text, p.id
    size = c["layout"]["size"]
    assert all(0 <= i < j < size for i, j in c["layout"]["links"])


def test_a_place_founded_later_joins_the_chart(worlds):
    """"new place[s] that the engine creates should be added to this map": a place
    founded where the party stands is on the chart the moment it exists, one way from
    here, because the graph is read live and nothing is cached."""
    loc = _town(worlds)
    s, e, pc = _party(worlds, loc.id)
    before = {n["id"] for n in _chart(e, worlds)["nodes"]}
    out = e.run(e.validate([{"op": "found", "actor": pc.ref, "because": "t",
                             "params": {"name": "the Crooked Lantern", "kind": "tavern"}}],
                           origin="author:test")).outcomes[-1]
    assert out.status == "resolved", out.tell
    made = s.founded[-1]["id"]
    c = _chart(e, worlds)
    node = next(n for n in c["nodes"] if n["id"] == made)
    assert made not in before
    assert node["near"] and not node["visited"] and node["name"].lower().endswith("lantern")
    assert c["found"] == len(before) + 1
    # And walked into, it is visited, with its own ways drawn.
    assert _travel(e, pc, made).status == "resolved"
    assert next(n for n in _chart(e, worlds)["nodes"] if n["id"] == made)["visited"]


def test_a_wanted_characters_shut_way_is_marked_with_the_rules_reason(worlds):
    """The mock's Wanted drawing: the ways the watch holds are barred, with the engine's
    own sentence (the exits row's `blocked`), and no walk goes through them."""
    loc = _town(worlds)
    s, e, pc = _party(worlds, loc.id)
    _want(pc, loc.id)
    c = _chart(e, worlds)
    row = {x["id"]: x["blocked"] for x in exits_mod.exits(e, worlds) if not x["journey"]}
    shut = [x for x in c["edges"] if x["shut"]]
    if not shut:
        pytest.skip("the way in of this town has no way out the watch holds")
    for x in c["edges"]:
        if x["from"] == s.at:
            assert x["shut"] == row[x["to"]]
    assert all("wanted" in x["shut"] for x in shut)
    for x in shut:
        node = next(n for n in c["nodes"] if n["id"] == x["to"])
        assert node["walk"] is None and "wanted" in node["why"]


def test_the_walk_there_goes_by_known_ways_only():
    """Inform's "best route ... through visited rooms". B is seen, never stood in; the
    shortest way to C is through it, and the walk goes the long way round by D, which
    was stood in. With D unvisited there is no known way, and the walk says so."""
    def row(to, minutes=5, blocked=""):
        return {"id": to, "name": to, "group": "next_door", "time_words": "w",
                "blocked": blocked, "journey": False, "minutes": minutes}

    ways = {"A": [row("B"), row("D")], "B": [row("C")], "D": [row("C", 7)]}
    legs, why = places_found.route(ways, {"A", "D"}, "A", "C")
    assert [(x["from"], x["to"]) for x in legs] == [("A", "D"), ("D", "C")] and not why
    assert sum(x["minutes"] for x in legs) == 12
    legs, why = places_found.route(ways, {"A"}, "A", "C")
    assert legs == [] and why == "No way there by the ways you know."
    # One step into the seen is a known way: it leaves a place stood in.
    legs, _ = places_found.route(ways, {"A"}, "A", "B")
    assert [(x["from"], x["to"]) for x in legs] == [("A", "B")]
    # A shut way is never walked, and the rule's own sentence says why.
    ways["A"][1] = row("D", blocked="The watch holds the way.")
    legs, why = places_found.route(ways, {"A", "D"}, "A", "D")
    assert legs == [] and why == "The watch holds the way."


def test_every_walk_on_the_chart_leaves_only_places_been(worlds):
    loc = _town(worlds)
    s, e, pc = _party(worlds, loc.id)
    _travel(e, pc, _next_door(e, worlds)["id"])
    c = _chart(e, worlds)
    been = set(s.places_been())
    for n in c["nodes"]:
        if n["current"]:
            assert n["walk"] is None
            continue
        assert n["walk"], n
        assert all(leg["from"] in been for leg in n["walk"]["legs"])
        assert n["walk"]["legs"][0]["from"] == s.at and n["walk"]["legs"][-1]["to"] == n["id"]
        assert all(leg["time_words"] for leg in n["walk"]["legs"])
        assert n["walk"]["minutes"] == sum(leg["minutes"] for leg in n["walk"]["legs"])


def test_exits_row_is_unchanged_by_the_refactor(worlds):
    """`exits.exits` is now `ways_from` for where the party stands; the row the page
    already reads keeps its six keys (G1: existing /api/state keys byte-identical)."""
    loc = _town(worlds)
    s, e, pc = _party(worlds, loc.id)
    row = exits_mod.exits(e, worlds)
    assert row and all(set(x) == {"id", "name", "group", "time_words", "blocked", "journey"}
                       for x in row)
    same = [{k: v for k, v in x.items() if k != "minutes"}
            for x in exits_mod.ways_from(e, worlds, [s.at])[s.at]]
    assert row == same


def test_the_state_carries_the_chart(worlds, tmp_path, monkeypatch):
    """`scene.places_found` on `/api/state`, beside the exits row it is read from."""
    from gm import watcher
    from play import concurrency
    from rules.sheet import load_pc

    monkeypatch.setattr(watcher, "kick", lambda c: None)
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        cm._LIVE.clear()
        concurrency.reset_for_tests()
        try:
            c = cm.begin_with(load_pc("fixtures/pc-thessaly.json"),
                              world_source=str(Path(worlds.source)))
            got = Client().get("/api/state").json()["scene"]["places_found"]
            assert got == places_found.chart(c.engine(), c.world)
            assert got["here"] == c.scene.at and got["visited"] == 1
        finally:
            cm._LIVE.clear()
