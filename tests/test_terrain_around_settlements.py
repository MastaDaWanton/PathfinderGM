"""The hinterland: ground of its own a short walk out from every settlement.

The owner, 2026-10-05: "in the campaign im playing everywhere has been farmland i have not
found a single place that wasnt farmland outside of the urban city. this makes gathering
tha materials i need for crafting impossible." Measured the same day, on the click path
(the Places row, `outskirts.ring` walked from the outskirts):

  - from Vormoor every place within a day was farmland or the shore: the outskirts, three
    road heads, the crossroads and the fields; 0 forest, 0 hills reachable. The nearest
    other ground was the badlands eight hours out and the mountain sixteen;
  - settlements whose Places row listed no open ground but farmland and the shore within
    four hours: Aurvantis 15 of 64, Pangrella 0 of 12, the synthetic world 4 of 6, the
    owner's Fantasia 7 of 36.

The land the world says a settlement sits in (Drossakar's "iron-rich badlands",
"volcanic ridgelines") was filed `beyond`, as if the village stood outside its own
continent. docs/place-doors.md, "The hinterland", has the prior art and the rule.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import blacksmith, geography, ingredients, journey, outskirts, places
from world.loader import load, load_cached

AURVANTIS = "fixtures/aurvantis-campaign.json"
SYNTHETIC = "fixtures/synthetic-world.json"
VORMOOR = "bde94b038cba"
OPEN = frozenset({"grassland", "forest", "jungle", "swamp", "hills", "mountain", "desert",
                  "tundra"})
FEW_HOURS = 4 * 60


def _settlements(world):
    for row in world.play.get("settlements") or []:
        e = world.get(row["id"])
        if e is not None and places._settled(e, ""):
            yield e


def _listed(world, e) -> dict[str, int]:
    """{ground: minutes} for the open ground the Places row offers from the outskirts,
    walked the way `travel` walks it (`places.route`, `outskirts.hop_minutes`)."""
    ring = outskirts.ring(world, e)
    out = next(p for p in ring if p.name == outskirts.OUTSKIRTS)
    by_id = {p.id: p for p in ring}
    got: dict[str, int] = {}
    for p in ring:
        if p.terrain not in OPEN:
            continue
        prev, minutes = out, 0
        for pid in places.route(ring, out.id, p.id):
            minutes += outskirts.hop_minutes(prev, by_id[pid], places.scale_of(e))
            prev = by_id[pid]
        got[p.terrain] = min(got.get(p.terrain, 10 ** 6), minutes)
    return got


def test_from_vormoor_a_few_hours_reach_ground_that_is_not_farmland():
    """Before: from Vormoor every place within a day was farmland (or the shore): 0
    forest, 0 hills reachable, the badlands 8 hours out and the mountain 16. After: the
    ridgelines (hills) and the badlands (desert) are on the Places row, each under three
    hours, named in Drossakar's own words."""
    world = load_cached(AURVANTIS)
    vormoor = world.get(VORMOOR)
    got = _listed(world, vormoor)
    assert set(got) >= {"hills", "desert"}, got
    assert all(m <= FEW_HOURS for m in got.values()), got
    names = {p.name: p for p in outskirts.ring(world, vormoor)}
    assert names["the ridgelines"].terrain == "hills"
    assert names["the badlands"].terrain == "desert"
    assert names["the badlands"].about == "iron-rich badlands"      # the world's clause
    # And they are worth going to: ore for the smith on both.
    assert blacksmith.obtainable("mined", biome="hills")
    assert blacksmith.obtainable("mined", biome="desert")


@pytest.mark.parametrize("path, before, most_without", [
    # before = settlements listing no non-farmland open ground within four hours,
    # measured 2026-10-05 before this change; most_without = what is allowed after.
    ("fixtures/aurvantis-campaign.json", 15, 3),
    ("fixtures/pangrella-campaign.json", 0, 0),
    ("fixtures/synthetic-world.json", 4, 1),
])
def test_every_world_lists_open_ground_within_a_few_hours(path, before, most_without):
    """Per world, the count of settlements whose Places row listed no open ground but
    farmland (and the shore) within four hours. Before → after: Aurvantis 15 → 3 of 64,
    synthetic 4 → 1 of 6, Pangrella 0 → 0 of 12 (and its mean rises from 1.2 to 2.0
    grounds). The ones left are honest: their roads cross farmland and only then the
    hills or the forest, and their region says nothing else that no road puts further
    (Kestwick's downs are half its road to Brindle Ford away)."""
    world = load_cached(path)
    without = [e.name for e in _settlements(world)
               if not [g for g, m in _listed(world, e).items() if m <= FEW_HOURS]]
    assert len(without) <= most_without, without
    assert before >= len(without)


def test_heading_into_the_hills_from_vormoor_is_the_ridgelines_and_its_ore():
    """The spoken path and the clicked path land on one place. `travel biome=hills` from
    Vormoor's market (what "I head into the hills" plans) goes to the ridgelines — the
    reach the Places row offers — at its own distance, not a nameless hills an hour out;
    and the ground underfoot is hills, so prospecting there digs the hills' ore. Before,
    the same travel was refused: "There is no hills near Vormoor"."""
    from rules.bestiary import instantiate
    from rules.dice import Dice
    from rules.engine import Engine, Scene

    world = load_cached(AURVANTIS)
    s = Scene(location_id=VORMOOR)
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    pc.hp = pc.hp_base = 60
    s.add(pc)
    e = Engine(s, Dice(seed=3), world=world)
    e.place_party("")
    real = e.dice

    class _Quiet:
        def __getattr__(self, name):
            return getattr(real, name)

        def roll(self, notation, modifiers=None, label="", visibility="hidden"):
            if notation == "1d100":
                return real.given(100, modifiers, label, notation)
            return real.roll(notation, modifiers, label, visibility)

    e.dice = _Quiet()
    before = s.clock_minutes
    out = e.run(e.validate([{"op": "travel", "actor": pc.ref, "because": "t",
                             "params": {"biome": "hills"}}], origin="author:test")).outcomes
    assert e.here().name == "the ridgelines", [o.tell for o in out]
    assert s.biome == "hills"
    assert 90 <= s.clock_minutes - before <= 180, s.clock_minutes - before
    e.run(e.validate([{"op": "prospect", "actor": pc.ref, "because": "t",
                       "params": {"hours": 2}}], origin="author:test"))
    got = e.resume(20).outcomes[-1]
    assert got.op == "prospect" and "no ore" not in got.tell, got.tell
    hills = {m.name for m in blacksmith.obtainable("mined", biome="hills")}
    assert any(st["base"] in hills for st in got.effects[0]["stock"]), got.tell


def test_further_out_stays_further():
    """Vormoor's three roads all cross farmland and THEN mountain, 72 to 96 miles. The
    mountain is not a reach (the roads put it half a road out, 36 miles, 16 hours), even
    though Drossakar's prose says "volcanic"; the reaches are the ground no road puts
    further."""
    world = load_cached(AURVANTIS)
    land = geography.land_around(world, VORMOOR)
    assert "mountain" in land.beyond and "mountain" not in land.near
    assert all(r.ground != "mountain" for r in land.reaches)
    assert outskirts.beyond_hours(world, world.get(VORMOOR), "mountain") == 16
    assert geography.grounded(land, "mountain") == ("beyond", "")
    assert geography.grounded(land, "hills") == ("near", "")


def test_never_ground_the_world_did_not_write():
    """A desert world stays a desert: every reach's ground is a word the world wrote —
    the settlement's own facts, a road's `crosses`, or its region's land facts — on every
    settlement of every shipped world. Nothing is added because villages usually had a
    wood."""
    for path in (AURVANTIS, "fixtures/pangrella-campaign.json", SYNTHETIC):
        world = load_cached(path)
        for e in _settlements(world):
            land = geography.land_around(world, e)
            said = {geography._canon(c) for leg in journey.legs_from(world, e.id)
                    for c in leg.crosses}
            for _who, words in land.words:
                said.update(geography.ground_in(words))
            for r in land.reaches:
                assert r.ground in said, (e.name, r)
                assert r.ground in land.near, (e.name, r)
                assert r.ground not in land.beyond, (e.name, r)


def test_ground_the_world_puts_somewhere_else_is_not_near():
    """Two of the world's own sentences put ground elsewhere and were read as near in the
    first cut: Lathwe's "salt marsh along the southern shore" gave the inland combe of
    Oakhollow a marsh, and Kaelinora's "Pangrellan grasslands, Kyropticus deserts" gave
    the town of Pangrella somebody else's desert. A localised clause and another
    people's proper name keep their ground out of the hinterland."""
    syn = load_cached(SYNTHETIC)
    oak = next(e for e in _settlements(syn) if e.name == "Oakhollow")
    assert "swamp" not in {r.ground for r in geography.land_around(syn, oak).reaches}
    pan = load_cached("fixtures/pangrella-campaign.json")
    town = next(e for e in _settlements(pan) if e.name == "Pangrella")
    reaches = geography.land_around(pan, town).reaches
    assert "desert" not in {r.ground for r in reaches}
    assert "grassland" in {r.ground for r in reaches}


def test_a_continent_s_whole_span_is_not_one_walk(tmp_path):
    """The owner's Fantasia: Terraverde's Biomes read "Scorched badlands, temperate
    savannas, arctic tundras", and the first cut put tundra and badlands both within five
    miles of Kaelinthal. Ground on both sides of the climate is a continent, not a walk:
    neither side is a reach; the savanna stands."""
    doc = json.loads(Path(SYNTHETIC).read_text(encoding="utf-8"))
    for ent in doc.get("entities") or []:
        facts = ent.get("facts") or {}
        if "Terrain" in facts and ent.get("kind", "").upper() == "CONTINENT":
            facts["Terrain"] = "Scorched badlands, temperate savannas, arctic tundras"
            facts.pop("Landscape", None)
    path = tmp_path / "span.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    world = load(path)
    seen = 0
    for e in _settlements(world):
        grounds = {r.ground for r in geography.land_around(world, e).reaches}
        assert not grounds & {"desert", "tundra"}, (e.name, grounds)
        seen += "grassland" in grounds
    assert seen


def test_a_reach_costs_its_own_miles_and_the_ridgelines_are_not_a_ring_hop():
    """A ring hop is half a mile (nine minutes on good going); a reach is its own miles at its ground's
    road column, walked either way. A place founded inside a reach is a ring hop from it,
    not the reach's miles a second time."""
    fields = places.Place(id="x~farmland:@the-fields", terrain="farmland")
    ridges = places.Place(id="x~hills:@the-ridgelines", terrain="hills", miles=4)
    cave = places.Place(id="x~hills:@the-ridgelines/the-cave", terrain="hills")
    there = outskirts.hop_minutes(fields, ridges, "village", 30)
    assert there == outskirts.hop_minutes(ridges, fields, "village", 30)
    assert 60 < there < 180
    # Half a mile over the hills' road column (x3/4): twelve minutes.
    assert outskirts.hop_minutes(ridges, cave, "village", 30) == 12
    assert "miles" not in ridges.as_dict()                 # derived, never saved
    assert places.terrain_of(ridges.id) == "hills"         # the id contract is unchanged


def test_no_ring_place_offers_more_than_six_ways_on_with_the_reaches(worlds):
    """The reaches hang off the fields (past the ploughland) or the outskirts, at most
    four (`geography.MOST_REACHES`), and the six-ways ceiling still holds."""
    for e in _settlements(worlds):
        ring = outskirts.ring(worlds, e)
        assert len([p for p in ring if outskirts.is_reach(p)]) <= geography.MOST_REACHES
        for p in ring:
            assert len(p.exits) <= 6, (e.name, p.name, len(p.exits))
            if outskirts.is_reach(p):
                assert places.setting_of(p.id) == "outside"
                assert places.terrain_of(p.id) == p.terrain


def test_ridgelines_and_canyon_words():
    """"volcanic ridgelines" read as nothing, so Drossakar had no upland but its
    mountains; "beech hangers" read as nothing, so Lathwe had no wood. "Canyon" is
    deliberately still nothing: the book has no canyon terrain."""
    assert geography.ground_in("volcanic ridgelines") == ("mountain", "hills")
    assert geography.ground_in("beech hangers") == ("forest",)
    assert geography.ground_in("black-rock canyons") == ()
    assert geography.ground_phrases("ash-fields, iron-rich badlands, geothermal vents") \
        == (("desert", "badlands", "iron-rich badlands"),)


def test_the_export_s_landforms_beat_the_derivation(tmp_path):
    """docs/from-world-bible.md asks for `landforms` on each settlement row. Given one, it
    is the hinterland exactly: its names, its ground, its miles."""
    doc = json.loads(Path(SYNTHETIC).read_text(encoding="utf-8"))
    row = next(r for r in doc["play"]["settlements"] if r["name"] == "Kestwick")
    row["landforms"] = [
        {"name": "Hob Wood", "terrain": "forest", "miles": 2, "words": "old oak and holly"},
        {"name": "the Chalk Pits", "terrain": "hills", "miles": 3},
        {"name": "nowhere", "terrain": "not a ground", "miles": 1},
    ]
    path = tmp_path / "stated.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    world = load(path)
    land = geography.land_around(world, row["id"])
    assert [(r.name, r.ground, r.miles, r.source) for r in land.reaches] == [
        ("Hob Wood", "forest", 2.0, "stated"), ("the Chalk Pits", "hills", 3.0, "stated")]
    assert land.source == "exact"
    ring = outskirts.ring(world, world.get(row["id"]))
    assert {"Hob Wood", "the Chalk Pits"} <= {p.name for p in ring}


def test_herbs_and_ore_within_a_few_hours_rise_on_every_world():
    """What the change buys the crafter, per world, as the mean number of distinct
    forageable herbs and mined materials on the open ground the Places row lists within
    four hours (the fields and the shore included). Measured 2026-10-05, master 68a7758
    against this branch: Aurvantis herbs 41.0 → 64.4 and mined 8.0 → 13.0; Pangrella
    59.7 → 77.8 and 2.3 → 10.2; synthetic 25.7 → 81.2 and 1.2 → 4.8; the owner's
    Fantasia 78.9 → 99.6 and 0.9 → 5.9."""
    def mean(path):
        world = load_cached(path)
        herbs, ores, n = 0, 0, 0
        for e in _settlements(world):
            grounds = {p.terrain for p in outskirts.ring(world, e)}
            grounds = {g for g in grounds if g in OPEN or g in ("farmland", "coast")}
            listed = _listed(world, e)
            grounds = {g for g in grounds if g not in OPEN or listed.get(g, 10 ** 6)
                       <= FEW_HOURS}
            herbs += len({i.id for i in ingredients.all_ingredients().values()
                          if i.forageable and set(i.biomes) & grounds})
            ores += len({m.id for g in grounds
                         for m in blacksmith.obtainable("mined", biome=g)})
            n += 1
        return herbs / n, ores / n

    herbs, ores = mean(AURVANTIS)
    assert herbs >= 60 and ores >= 12, (herbs, ores)
    herbs, ores = mean(SYNTHETIC)
    assert herbs >= 80 and ores >= 4, (herbs, ores)
