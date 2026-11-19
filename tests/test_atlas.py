"""The atlas: what the place map's World, Continent, Region and Site draw from (play/atlas.py).

Phase 1 of docs/place-map-v2-build-plan.md: the server half, with no change on the page.
The owner chose the mock's 3D tabletop on 2026-11-18; these hold the data it needs to the
engine's own answers, so the map can never disagree with the game:

- every journey is `journey.legs_from`'s, read by its stated `by`. Measured on the mock:
  `play.travel` alone lists 2 of Ledgernook's 17 sea passages, and `by_sea` is also set on
  3 of its river legs, which the mock's first port list showed as sea;
- the ground round a settlement is `geography.land_around`'s;
- the sites and their rooms come through the same fog as the town chart: rooms stood in and
  rooms one passage on, and nothing of the rest;
- knowledge only grows.

World-agnostic (the standing instruction of 2026-09-28): the `worlds` fixture runs each test
once per export, Aurvantis, Pangrella and the synthetic world.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from django.test import Client, override_settings

from play import atlas
from play import campaign as cm
from rules import geography, journey, places
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene


def _party(world, town_id, at=""):
    s = Scene(location_id=town_id)
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    pc.hp = pc.hp_base = 60
    s.add(pc)
    e = Engine(s, Dice(seed=3), world=world)
    e.place_party(at)
    return s, e, pc


def _settlement_ids(world):
    return [row["id"] for row in world.play.get("settlements") or [] if world.get(row["id"]) is not None]


# --- the world ---------------------------------------------------------------------------

def test_every_settlement_is_in_the_atlas_with_its_nation_and_continent(worlds):
    """One entry a settlement, its nation and continent read off the containment chain.
    Kind names vary by export (Aurvantis calls all 64 CITY; the synthetic world uses VILLAGE,
    TOWN and CITY), so nothing keyed on a kind may decide this."""
    a = atlas.atlas(worlds)
    assert [c["id"] for c in a["cities"]] == _settlement_ids(worlds)
    for c in a["cities"]:
        assert c["nation"] in a["nations"] and c["continent"] in a["continents"]
        assert a["nations"][c["nation"]]["continent"] == c["continent"]
        assert worlds.get(c["nation"]).name == a["nations"][c["nation"]]["name"]


def test_the_journeys_are_the_engines_own(worlds):
    """Every leg the travel door offers is in the atlas once, by its stated way, and nothing
    else is. `play.travel` alone is not the list: the engine derives sea passages for ports
    (Ledgernook: 17 sea legs, 2 of them in `play.travel`)."""
    a = atlas.atlas(worlds)
    got = {tuple(sorted((r["a"], r["b"]))): r for r in a["routes"]}
    assert len(got) == len(a["routes"]), "a pair listed twice"
    want = {}
    for sid in _settlement_ids(worlds):
        for leg in journey.legs_from(worlds, sid):
            if worlds.get(leg.to_id) is not None:
                want.setdefault(tuple(sorted((sid, leg.to_id))), leg)
    assert set(got) == set(want)
    for pair, leg in want.items():
        assert got[pair]["by"] == (leg.by or "")
        assert got[pair]["miles"] == leg.miles and got[pair]["crosses"] == list(leg.crosses)


def test_a_river_leg_is_never_called_sea(worlds):
    """`by_sea` is true of river legs too (3 of Ledgernook's), so the atlas reads `by`. The
    mock's first sea-port list read the flag and listed Greenbrook, Koradin and Ledgerwarren,
    all up the river, as ports."""
    a = atlas.atlas(worlds)
    for sid in _settlement_ids(worlds):
        for leg in journey.legs_from(worlds, sid):
            if leg.by == "river":
                r = next(r for r in a["routes"] if {r["a"], r["b"]} == {sid, leg.to_id})
                assert r["by"] == "river"


def test_ledgernooks_sea_passages_are_all_there():
    """The measurement the module docstring cites, held: 17 sea legs from Ledgernook in
    Aurvantis, where `play.travel` states 2."""
    from world.loader import load_cached

    w = load_cached("fixtures/aurvantis-campaign.json")
    led = w.by_name("Ledgernook").id
    a = atlas.atlas(w)
    sea = [r for r in a["routes"] if r["by"] == "sea" and led in (r["a"], r["b"])]
    stated = [r for r in w.play["travel"] if r.get("by") == "sea" and led in (r["from_id"], r["to_id"])]
    assert len(sea) == 17 and len(stated) == 2


def test_the_ground_is_the_engines_reading(worlds):
    """`near`, `beyond` and the reaches are `geography.land_around`'s, so the region map's
    woods are the woods the outskirts ring lets the player walk to."""
    a = atlas.atlas(worlds)
    for c in a["cities"]:
        land = geography.land_around(worlds, c["id"])
        assert c["near"] == list(land.near) and c["beyond"] == list(land.beyond)
        assert c["reaches"] == [{"ground": r.ground, "name": r.name, "miles": r.miles, "source": r.source}
                                for r in land.reaches]


def test_the_atlas_is_built_once_per_world(worlds):
    """Static for a campaign: a second call hands back the same object."""
    assert atlas.atlas(worlds) is atlas.atlas(worlds)


def test_is_port_is_remembered_per_world(monkeypatch):
    """`legs_from` asks `is_port` of every neighbour on every call, and `is_port` built the
    whole place list each time. Measured 2026-11-18 on Aurvantis: 32 ms a call, 4.3 s for
    `legs_from` over its 64 settlements (the atlas took 10.7 s cold); remembered, 9 ms.
    Asked twice, the second answer must not rebuild the places."""
    from world.loader import load_cached

    w = load_cached("fixtures/aurvantis-campaign.json")
    sid = w.by_name("Ledgernook").id
    first = journey.is_port(w, sid)
    calls = []
    real = places.home_set
    monkeypatch.setattr(places, "home_set", lambda *a, **k: calls.append(1) or real(*a, **k))
    assert journey.is_port(w, sid) == first
    assert calls == []
    t = time.perf_counter()
    for row in w.play["settlements"]:
        journey.legs_from(w, row["id"])
    assert time.perf_counter() - t < 1.0


# --- what the player knows -------------------------------------------------------------------

def test_known_places_starts_with_the_settlement_stood_in(worlds):
    """A party standing in a town knows that town, and nothing heard or mapped yet (phase 5
    fills those)."""
    sid = _settlement_ids(worlds)[0]
    s, e, pc = _party(worlds, sid)
    k = atlas.known_places(e, worlds)
    assert k["been"] == [sid] and k["heard"] == {} and k["maps"] == []


def test_knowledge_only_grows(worlds):
    """`been` is read from `Scene.places_been`, which only grows: standing somewhere else
    adds the new town and keeps the old."""
    ids = _settlement_ids(worlds)
    if len(ids) < 2:
        pytest.skip("one settlement")
    s, e, pc = _party(worlds, ids[0])
    s.been.append(f"{ids[1]}~urban:the-gate")
    assert atlas.known_places(e, worlds)["been"] == [ids[0], ids[1]]


def _site_town(world):
    """A settlement with a small site dug under its first place inside the walls, the way
    play founds one (`Scene.founded`, grafted by `places.with_founded`): cellars, a vault
    beneath, a deeper vault beneath that. A fresh town has none of its own; caves and
    dungeons come from ventures and the dungeon builder during play."""
    sid = _settlement_ids(world)[0]
    s, e, pc = _party(world, sid)
    host = next(p for p in e.places() if places.setting_of(p.id) == "in" and "^" not in p.id
                and p.id not in s.places_been())   # not where the party starts: the tests choose what is stood in
    stem = host.id.split("~", 1)[1].split(":", 1)[1]
    root = f"{sid}~underground:{stem}/the-cellars"
    rooms = [(root, "the cellars", host.id, "entrance"), (root + "/the-vault", "the vault", root, "room"),
             (root + "/the-vault/the-deep-vault", "the deep vault", root + "/the-vault", "climax")]
    founded = [{"id": i, "name": n, "about": f"{n}, dark", "terrain": "underground", "exits": [], "parent": par,
                "origin": "dungeon", "kind": "", "dungeon": {"of": root, "role": role, "door": {"state": "open"}}}
               for i, n, par, role in rooms]
    return sid, host, founded


def _with_site(world, sid, founded, been):
    s, e, pc = _party(world, sid)
    s.founded.extend(founded)
    s.been.extend(been)
    return s, e


def test_a_site_shows_only_its_way_in_until_it_is_entered(worlds):
    """Stood at the site's host (the place above it), the site is on the map and nothing
    beneath its way in: a room not yet seen does not cross to the page at all, as a place
    under the fog does not on the town chart."""
    sid, host, founded = _site_town(worlds)
    s, e = _with_site(worlds, sid, founded, [host.id])
    root = founded[0]["id"]
    site = next(x for x in atlas.known_places(e, worlds)["sites"] if x["id"] == root)
    assert [r["id"] for r in site["rooms"]] == [root]
    assert site["rooms"][0]["visited"] is False and site["rooms"][0]["about"] == "" and site["rooms"][0]["role"] == ""


def test_an_entered_room_shows_the_rooms_one_passage_on(worlds):
    """Stood in the way in, the room one passage on is seen (its name and passages) and the
    room beyond it is not sent; what a room is about, its role and its door wait until it is
    stood in."""
    sid, host, founded = _site_town(worlds)
    root, vault, deep = (f["id"] for f in founded)
    s, e = _with_site(worlds, sid, founded, [host.id, root])
    site = next(x for x in atlas.known_places(e, worlds)["sites"] if x["id"] == root)
    rooms = {r["id"]: r for r in site["rooms"]}
    assert set(rooms) == {root, vault}
    assert rooms[root]["visited"] and rooms[root]["about"] == "the cellars, dark" and rooms[root]["role"] == "entrance"
    assert not rooms[vault]["visited"] and rooms[vault]["about"] == "" and rooms[vault]["role"] == ""
    assert rooms[vault]["parent"] == root


def test_the_room_you_stand_in_is_marked(worlds):
    """`here` names the room the party stands in, so the site map can light it."""
    sid, host, founded = _site_town(worlds)
    root, vault, deep = (f["id"] for f in founded)
    s, e = _with_site(worlds, sid, founded, [host.id, root, vault])
    s.at = vault
    site = next(x for x in atlas.known_places(e, worlds)["sites"] if x["id"] == root)
    assert site["here"] == vault and {r["id"] for r in site["rooms"]} == {root, vault, deep}


def test_a_site_nobody_has_reached_is_not_sent(worlds):
    """No room stood in and the host never visited: the site is not on the map."""
    sid, host, founded = _site_town(worlds)
    s, e = _with_site(worlds, sid, founded, [])
    assert host.id not in s.places_been()
    assert all(x["id"] != founded[0]["id"] for x in atlas.known_places(e, worlds)["sites"])


# --- on the wire ------------------------------------------------------------------------------

def test_the_atlas_endpoint_and_the_state_key(worlds, tmp_path, monkeypatch):
    """`/api/atlas` serves the atlas with no-store (the Electron cache outlives reinstalls);
    `/api/state` carries `known_places`, appended after the older scene keys."""
    from gm import watcher
    from play import concurrency
    from rules.sheet import load_pc

    monkeypatch.setattr(watcher, "kick", lambda c: None)
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        cm._LIVE.clear()
        concurrency.reset_for_tests()
        try:
            c = cm.begin_with(load_pc("fixtures/pc-thessaly.json"), world_source=str(Path(worlds.source)))
            r = Client().get("/api/atlas")
            assert r.status_code == 200 and r["Cache-Control"] == "no-store"
            # The atlas, and the campaign's stored layout beside it (rules/hexes.py,
            # 2026-11-19): the maps draw the towns where the engine's hexes put them.
            got_atlas = r.json()
            layout = got_atlas.pop("layout")
            assert got_atlas == atlas.atlas(c.world)
            assert layout == cm.current().scene.hexes["layout"]
            assert set(layout["pos"]) == {x["id"] for x in got_atlas["cities"]}
            got = Client().get("/api/state").json()["scene"]["known_places"]
            assert got == atlas.known_places(c.engine(), c.world)
            assert got["been"] == [c.scene.location_id]
        finally:
            cm._LIVE.clear()
