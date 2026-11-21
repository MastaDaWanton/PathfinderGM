"""The region map's scale against the road's journey, and walks between a hex and its town
(fix/hex-scale, owner rulings 2026-11-21; docs/research/2026-11-21-hex-scale.md).

Measured on 0.4.6 before this file:

- the board's scale came from the world's raw road miles alone, so walking the hexes
  between two towns beat the road's three-day floor on 56 of 190 land legs at Ultimate
  Campaign's plain 5 hours a hex (Aurvantis 50 of 152, Pangrella 4 of 12, the owner's
  fantasia 2 of 26), and on all 10 of the synthetic world's;
- every speed walked a hex in the 30-foot hours, so a 20-foot party crossed the board faster
  than its road;
- the ruins twelve miles out of Branford to its docks cost no time at all (the owner's save),
  and the exits row priced the gate "a quarter of an hour": the hex's step to the outskirts
  was a half-mile ring hop, and a passage booked from the ruins stood the party on deck.

Every engine test runs once per export (fixes are world-agnostic, 2026-09-28).
"""
from __future__ import annotations

import copy

import pytest

from play import atlas as atlas_mod
from play import exits as exits_mod
from rules import hexes, journey, ontheway, places
from rules.engine import Scene
from tests.test_hex_travel import _move, _party


@pytest.fixture
def quiet(monkeypatch):
    monkeypatch.setattr(ontheway, "road", lambda *a, **k: None)
    monkeypatch.setattr(ontheway, "road_stretches", lambda *a, **k: None)
    monkeypatch.setattr(ontheway, "sea_stretches", lambda *a, **k: None)


def _grid(world):
    a = atlas_mod.atlas(world)
    return a, hexes.held_layout(Scene(), a)


def test_no_walk_across_the_hexes_beats_the_road(worlds):
    """0.4.6: 56 of 190 land legs (and 10 of the synthetic world's 10) were quicker by the
    hexes on plain than by the road. Every road's journey hours on foot now take no fewer
    hours than the hexes between its towns at the quickest a hex goes."""
    a, lay = _grid(worlds)
    g = hexes.grid(a, lay)
    legs = 0
    for c in a["cities"]:
        for leg in journey.legs_from(worlds, c["id"]):
            hours, _w, how = journey.hours_for(leg, 30)
            if how == "sea" or leg.to_id not in g.town_hex:
                continue
            n = hexes.distance(g.town_hex[c["id"]], g.town_hex[leg.to_id])
            assert n * hexes.HOURS_PLAIN >= hours, (c["name"], leg.to_name, n, hours)
            legs += 1
    assert legs


def test_the_board_only_ever_gets_finer():
    """The rescale shrinks the hex and never grows it, so a save's hexes map one to one
    onto the new grid (`mend_save`)."""
    from world.loader import load_cached

    for path in ("fixtures/aurvantis-campaign.json", "fixtures/pangrella-campaign.json"):
        a, lay = _grid(load_cached(path))
        g = hexes.grid(a, lay)
        assert g.size <= (hexes.HEX_MILES / 2) / g.miles_per_unit


@pytest.mark.parametrize("speed,plain,rough", [(15, 11, 16), (20, 8, 12), (25, 8, 12),
                                               (30, 5, 8), (40, 4, 6), (50, 3, 5),
                                               (60, 3, 5), (10, 11, 16)])
def test_a_hex_takes_the_hours_of_the_partys_speed(speed, plain, rough):
    """Ultimate Campaign Table 3-2. Until 2026-11-21 every speed took the 30-foot row."""
    assert hexes.hours_through("grassland", speed) == plain
    assert hexes.hours_through("forest", speed) == rough


def test_the_walk_between_town_and_a_hex_costs_the_hex_and_the_row_says_so(worlds, quiet):
    """The first hex out hangs off the town's outskirts, and from town the exits row
    offered it as a ring hop: "a few minutes' walk" to ground twelve miles off, and the
    walk charged that. It now costs the hex's hours (Table 3-2), and the row's price is
    the walk's own."""
    s, e, pc = _party(worlds)
    g = e.hex_world()
    here = e.party_hex(g)
    out = next(h for h in hexes.neighbours(*here) if g.cell(*h)["land"]
               and not g.cell(*h)["town"])
    assert _move(e, out).status == "resolved"
    hex_id = s.at
    from rules import outskirts

    ring = e._ring(worlds.get(s.location_id), "")
    e.place_party(next(p.id for p in ring if p.name == outskirts.OUTSKIRTS))
    rows = exits_mod.ways_from(e, worlds, [s.at])[s.at]
    row = next(r for r in rows if r["id"] == hex_id)
    want = hexes.hours_through(g.cell(*out)["ground"], pc.speed_feet) * 60
    assert row["minutes"] >= want, row
    t = s.clock_minutes
    r = e.run(e.validate([{"op": "travel", "actor": "pc", "params": {"place": hex_id}}]))
    went = [o for o in r.outcomes if o.op == "travel"][0]
    assert went.status == "resolved", went.tell
    assert s.at == hex_id
    assert s.clock_minutes - t == row["minutes"], (s.clock_minutes - t, row["minutes"])


def test_a_passage_booked_from_open_ground_walks_back_to_town_first(quiet):
    """The owner's save, 2026-11-21: "I head back to Branford's docks and book passage"
    from the ruins took no time and stood the party on deck. It now walks the hexes back
    first, at their hours, and only then goes aboard."""
    from tests.test_ships_at_sea import PANGRELLA, MIRABALOS, _at_port, _journey

    s, e, pc = _at_port()
    g = e.hex_world()
    here = e.party_hex(g)
    out = next(h for h in hexes.neighbours(*here) if g.cell(*h)["land"]
               and not g.cell(*h)["town"])
    assert _move(e, out).status == "resolved"
    assert s.location_id == MIRABALOS
    t = s.clock_minutes
    done = _journey(e)
    assert done.status == "resolved", done.tell
    assert e.aboard() is not None
    town_ground = g.cell(*here)["ground"]          # the hex walked back into
    assert s.clock_minutes - t >= hexes.hours_through(town_ground, pc.speed_feet) * 60
    assert PANGRELLA is not None


# --- a save from the older scale ------------------------------------------------------------

def _old_save(world):
    """A save as 0.4.6 wrote it: the party in a site in a hex beside the first town, on the
    raw-miles grid, with the hex touched, spotted and searched."""
    a, lay = _grid(world)
    old = hexes.Grid(a, lay, size=(hexes.HEX_MILES / 2) / hexes.grid(a, lay).miles_per_unit)
    town = a["cities"][0]["id"]
    h0 = old.town_hex[town]
    h = next(n for n in hexes.neighbours(*h0) if old.cell(*n)["land"] and not old.cell(*n)["town"])
    doc = hexes.place_doc(old, *h, parent=f"{town}~urban:the-gate")
    doc.pop("miles")                              # 0.4.6's docs carried none
    site = f"{town}~ruins:@{hexes.slug(*h)}/the-ruins"
    k = hexes.key(*h)
    data = {"world_source": "x", "ledger": [{"text": f"stood at {site}"}],
            "history": [{"role": "assistant", "content": f'{{"place": "{doc["id"]}"}}'}],
            "scene": {"location_id": town, "at": site,
                      "founded": [doc, {"id": site, "name": "the ruins", "parent": doc["id"],
                                        "origin": "venture", "terrain": "ruins"}],
                      "hexes": {"layout": lay, "touched": {k: {"entered": 1}},
                                "spotted": {k: "ruins"}}}}
    return a, old, h, data


def test_a_save_on_the_old_scale_is_rekeyed_onto_the_new_grid(worlds):
    """Every save of 0.4.4-0.4.6 holds hexes of the raw-miles grid (the owner stands in a
    hex site in the ruins). Re-keyed on load: the party's site, its hex place and the
    records move to the hex the old one's middle falls in, its site stays ruins, the hex
    place is the one this build would make there, and a second load changes nothing."""
    a, old, h, data = _old_save(worlds)
    assert hexes.mend_save(data, a)
    g = hexes.grid(a, hexes.held_layout(Scene(), a))
    to = hexes.hex_at(*hexes.centre(*h, old.size), g.size)
    s = data["scene"]
    assert hexes.parse_place(s["at"]) == to and s["at"].endswith("/the-ruins")
    fresh = hexes.place_doc(g, *to, parent="")
    hexdoc = next(d for d in s["founded"] if d.get("origin") == "hex")
    assert hexdoc["id"] == fresh["id"] and hexdoc["miles"] == fresh["miles"]
    assert hexdoc["name"] == fresh["name"]
    site = next(d for d in s["founded"] if d.get("origin") == "venture")
    assert site["parent"] == hexdoc["id"] and site["id"] == s["at"]
    assert s["location_id"] == places.location_of(s["at"])
    k = hexes.key(*to)
    assert list(s["hexes"]["touched"]) == [k] and s["hexes"]["spotted"] == {k: "ruins"}
    assert hexes.site_of(g, *to, kept=s["hexes"]["sites"])["kind"] == "ruins"
    assert hexes.slug(*to) in data["ledger"][0]["text"]
    assert hexes.slug(*to) in data["history"][0]["content"]
    again = copy.deepcopy(data)
    assert not hexes.mend_save(again, a) and again == data


def test_a_save_that_never_stood_on_a_hex_is_only_stamped(worlds):
    a, _lay = _grid(worlds)
    data = {"scene": {"location_id": "x", "at": "x~urban:the-gate", "hexes": {}}}
    assert not hexes.mend_save(data, a)
    assert data["scene"]["hexes"] == {"grid": hexes.GRID_VERSION,
                                      "coast": hexes.COAST_VERSION}


def test_the_way_up_from_a_site_to_its_own_hex_is_still_minutes(worlds, quiet):
    """Live on the rescaled owner save, 2026-11-21: the hex doc's new `miles` made it read
    as a reach of the hinterland (`outskirts.is_reach`), and the ruins' way up to their own
    hex, 36 miles from Branford, was priced "more than a day"."""
    from tests.test_hex_sites import _to_a_site

    s, e, pc, _went = _to_a_site(worlds)
    hex_id = next(p.id for p in e.places() if p.origin == "hex")
    rows = exits_mod.ways_from(e, worlds, [s.at])[s.at]
    row = next(r for r in rows if r["id"] == hex_id)
    assert row["minutes"] < 60, row
