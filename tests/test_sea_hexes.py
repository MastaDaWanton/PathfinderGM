"""Hex travel on water: by ship, by small boat, and swimming (feat/sea-hexes, owner
2026-11-21: "hex travel while on boats or swimming"; docs/research/2026-11-21-sea-hexes.md).

Measured on 0.4.8 before this file:

- not one port of the shipped exports had a water hex within twelve hexes of its town's hex
  (Aurvantis 23 ports, Pangrella 4, the owner's fantasia 7; the synthetic world's one port
  eleven hexes off): the land is `landAt`'s discs round every town, far wider than a hex,
  so nothing could put out from a quay on the Region map;
- every water hex refused with "Crossing it waits for a ship", whatever the party had;
- the passage floor was a fortnight (672 miles), and a galley's floor rounded DOWN to ten
  days (960 miles, quicker than the floor it was).

Every engine test runs once per export (fixes are world-agnostic, 2026-09-28). The sea's
meeting check is held quiet wherever a test measures hours or places.
"""
from __future__ import annotations

import pytest

from play import atlas as atlas_mod
from rules import hexes, journey, ontheway, places, ships
from rules.engine import Scene
from tests.test_hex_travel import _party


@pytest.fixture
def calm(monkeypatch):
    calls = []

    def sea(dice, days, *a, **k):
        calls.append(k.get("percent"))
        return None

    monkeypatch.setattr(ontheway, "sea_stretches", sea)
    monkeypatch.setattr(ontheway, "road", lambda *a, **k: None)
    return calls


def _coast(world):
    """A port of this world, a party standing in it, and the water hex beside its own."""
    port = journey.ports(world)[0]
    s, e, pc = _party(world, port)
    g = e.hex_world()
    here = e.party_hex(g)
    wet = next(h for h in hexes.neighbours(*here) if not g.cell(*h)["land"])
    return s, e, pc, g, here, wet


def _move(e, to, how=None):
    params = {"hex": list(to), **({"how": how} if how else {})}
    r = e.run(e.validate([{"op": "hex_move", "actor": "pc", "params": params}]))
    if r.awaiting:
        r = e.resume(10)
    return [o for o in r.outcomes if o.op == "hex_move"][0]


def _ship_at_quay(e, pc, port, crew=20):
    vid = ships.vessel_id(port, "sailing ship", 7)
    v = ships.Vessel(id=vid, name=ships.name_for(vid), kind="sailing ship", hp=125,
                     crew=crew, at=port, held_by=pc.ref)
    e._keep_vessel(v)
    e.place_party(ships.deck_of(v))
    return vid


# --- the coast ----------------------------------------------------------------------------

def test_every_port_has_the_sea_beside_its_own_hex(worlds):
    """0.4.8: 0 of 34 ports on the shipped exports had a water hex within twelve hexes.
    Each coastal town now has its channel to the sea (`Grid._chart_channels`), and no
    town's hex moved for it."""
    a = atlas_mod.atlas(worlds)
    lay = hexes.held_layout(Scene(), a)
    g = hexes.grid(a, lay)
    before = hexes.Grid(a, lay, channels=False)
    ports = [p for p in journey.ports(worlds) if p in g.town_hex]
    assert ports
    for p in ports:
        assert any(not g.cell(*h)["land"] for h in hexes.neighbours(*g.town_hex[p])), p
        assert g.cell(*g.town_hex[p])["land"], p
    assert g.town_hex == before.town_hex


def test_inshore_water_and_open_sea_are_told_apart(worlds):
    """UC p.158 has one water hex; the board shows the coast's own water and the open sea
    beyond it apart (`sea`)."""
    s, e, pc, g, here, wet = _coast(worlds)
    assert g.cell(*wet)["sea"] == "inshore"
    far = next(h for h in hexes._spiral(wet, 30)
               if not g.cell(*h)["land"] and g.cell(*h)["sea"] == "open")
    assert all(not g.cell(*n)["land"] for n in hexes.neighbours(*far))
    assert g.cell(*here)["sea"] == ""


def test_no_crossing_by_the_sea_hexes_beats_the_three_week_passage(worlds):
    """Owner 2026-11-21: three weeks under a sailing ship at the least. A ship crosses at
    least as many hexes as the straight line between two ports, so the line's hexes at a
    water hex's miles (`Grid.sea_miles`) take a sailing ship no fewer days than the
    passage does (Pangrella's narrowest crossing, 81 hexes, wanted 12.44 miles a hex)."""
    a = atlas_mod.atlas(worlds)
    g = hexes.grid(a, hexes.held_layout(Scene(), a))
    crossings = 0
    for c in a["cities"]:
        for leg in journey.legs_from(worlds, c["id"]):
            if not leg.by_sea or leg.by == "river" or leg.to_id not in g.town_hex:
                continue
            n = hexes.distance(g.town_hex[c["id"]], g.town_hex[leg.to_id])
            days = ships.leg_days(leg, "sailing ship")
            assert n * hexes.ship_minutes("sailing ship", g.sea_miles) >= days * 24 * 60 - n
            crossings += 1
    if journey.ports(worlds) and len(a["continents"]) > 1:
        assert crossings


def test_the_passage_floor_is_three_weeks_and_never_rounds_down():
    """Owner 2026-11-21: 2 weeks to 3. A floor of distance (1,008 miles), so a faster ship
    is still quicker: a galley's 10.5 days is 11, never the 10 days (960 miles) that
    rounding to the nearest gave."""
    assert ships.PASSAGE_DAYS_AT_LEAST == 21 and ships.PASSAGE_MILES_AT_LEAST == 1008
    for kind in ships.VESSELS:
        assert ships.days_for(1, kind) * ships.miles_a_day(kind) >= 1008, kind
    assert ships.days_for(1, "galley") == 11
    assert ships.days_for(1, "galley", measured=True) == 1
    assert ships.days_for(1, "keelboat", river=True) == journey.ROAD_DAYS_AT_LEAST


# --- onto the water -----------------------------------------------------------------------

def test_walking_onto_water_is_refused_with_why_and_what_a_swim_costs(worlds, calm):
    """UC p.158: without "swim speeds or boats", treat oceans "as obstacles". Before, the
    refusal named only a ship; now it names the three ways and a swim's price, spends
    nothing, and never chooses the swim for the player."""
    s, e, pc, g, here, wet = _coast(worlds)
    pc.purse = {}
    at, clock = s.at, s.clock_minutes
    out = _move(e, wet)
    assert out.status == "refused"
    assert "boatman" in out.tell and "carries" in out.tell
    pc.purse = {}
    town = g.city[g.cell(*here)["town"]]
    town_near = list(town.get("near") or ())
    try:
        town["near"] = [n for n in town_near if n != "coast"]
        out = _move(e, wet)
    finally:
        town["near"] = town_near
    assert out.status == "refused"
    assert "choice to swim" in out.tell and "DC 20 Swim" in out.tell and "drowns" in out.tell
    assert (s.at, s.clock_minutes) == (at, clock)


def test_a_hired_rowboat_rows_a_hex_and_makes_landfall(worlds, calm):
    """UE's rowboat passage: 2 cp a mile a head, about 1-1/2 miles an hour. Out from the
    port, one hex of water (eight hours and more at the oars), and back ashore on the land
    hex beside it at the land's own hours."""
    s, e, pc, g, here, wet = _coast(worlds)
    pc.purse = {"gp": 5}
    start = s.clock_minutes
    out = _move(e, wet)
    assert out.status != "refused", out.tell
    assert e.afloat(g)[0] == "boat" and e.party_hex(g) == wet
    assert places.terrain_of(s.at) == ships.DECK
    assert s.clock_minutes - start == hexes.row_minutes(g.sea_miles)
    assert any(f.get("how") == "boat" and f.get("kind") == "give" for f in out.effects)
    assert calm and calm[-1] is not None, "the water hex rolled the sea's check"
    # Landfall: the hex the party put out from.
    assert here in e.hex_reach(g)
    back = _move(e, here)
    assert back.status != "refused", back.tell
    assert e.afloat(g)[0] == "" and e.party_hex(g) == here
    assert not places.terrain_of(s.at) in ("water", ships.DECK)


def test_a_swim_across_a_water_hex_makes_the_body_pay(worlds, calm):
    """CRB Swim: half speed a round, and "each hour that you swim, you must make a DC 20
    Swim check or take 1d6 points of nonlethal damage from fatigue". Twelve miles is seven
    hours and more at 30 ft; a guildhand's Swim fails that check most hours, so the swim
    costs nonlethal damage (or worse) and every swimmer's record names the rule."""
    s, e, pc, g, here, wet = _coast(worlds)
    start = s.clock_minutes
    out = _move(e, wet, how="swim")
    assert out.status != "refused", out.tell
    swum = [f for f in out.effects if f.get("kind") == "swim"]
    assert swum and all(f["origin"] == "rule:swim" for f in swum)
    hurt = sum(f["amount"] for f in out.effects
               if f.get("kind") == "damage" and f.get("ref") == pc.ref)
    assert hurt > 0 or pc.is_down, out.tell
    assert s.clock_minutes - start >= 7 * 60
    if not pc.is_down:
        assert e.afloat(g)[0] == "swim" and places.terrain_of(s.at) == "water"


def test_a_swim_is_never_lit_on_the_board_only_offered(worlds, calm):
    """The reach lights the ways that are not a swim; the slip offers the swim with its
    price (`_hexes` "ways" and "swim")."""
    s, e, pc, g, here, wet = _coast(worlds)
    town = g.city[g.cell(*here)["town"]]
    near = list(town.get("near") or ())
    try:
        town["near"] = [n for n in near if n != "coast"]
        assert wet not in e.hex_reach(g)
        state = atlas_mod._hexes(e)
        assert state["ways"][hexes.key(*wet)] == ["swim"]
        assert "DC 20 Swim" in state["swim"]
    finally:
        town["near"] = near


# --- by ship --------------------------------------------------------------------------------

def test_a_held_ship_puts_out_sails_a_hex_and_makes_port(worlds, calm):
    """Owner 2026-11-09: ships become reachable (board, sail). From her quay she sails a
    hex in the hours of her Table 7-9 day's run, lies on that hex, and runs back into her
    port and ties up, the party still on her deck."""
    s, e, pc, g, here, wet = _coast(worlds)
    port = g.cell(*here)["town"]
    vid = _ship_at_quay(e, pc, port)
    assert e.party_hex(g) == here and wet in e.hex_reach(g)
    start = s.clock_minutes
    out = _move(e, wet)
    assert out.status != "refused", out.tell
    ship = e.vessel(vid)
    assert ship.hex == list(wet) and not ship.at and e.afloat(g)[0] == "ship"
    assert s.location_id == vid
    assert s.clock_minutes - start == hexes.ship_minutes("sailing ship", g.sea_miles)
    back = _move(e, here)
    assert back.status != "refused", back.tell
    ship = e.vessel(vid)
    assert ship.at == port and ship.hex is None and s.location_id == port
    assert ships.vessel_of(s.at) == vid


def test_a_ship_short_of_hands_does_not_put_out(worlds, calm):
    s, e, pc, g, here, wet = _coast(worlds)
    _ship_at_quay(e, pc, g.cell(*here)["town"], crew=2)
    out = _move(e, wet, how="ship")
    assert out.status == "refused" and "too few hands" in out.tell


def test_a_ship_meets_what_a_voyage_meets_and_a_rowboat_only_the_seas(worlds, monkeypatch):
    """Owner ruling 2026-11-21: at sea only aquatic creatures and ships. A pirate sail met
    by a ship the PC holds is the ship-to-ship bands (`scene.sea`); met by a rowboat it
    passes; an island a hand wants to put in at is a ship's scene, never a rowboat's."""
    monkeypatch.setattr(ontheway, "road", lambda *a, **k: None)
    met = {"kind": "pirates"}

    def sea(dice, days, *a, **k):
        return ontheway.Meeting(kind=met["kind"], roll=50, count=0, template="thug",
                                aggressive=True, day=1)

    monkeypatch.setattr(ontheway, "sea_stretches", sea)
    s, e, pc, g, here, wet = _coast(worlds)
    pc.purse = {"gp": 5}
    out = _move(e, wet)
    assert "sail on the horizon" in out.tell and not s.sea
    assert any(f.get("kind") == "sea_encounter" for f in out.effects)
    met["kind"] = "island"
    nxt = next(h for h in hexes.neighbours(*wet) if not g.cell(*h)["land"])
    out = _move(e, nxt)
    assert not any(f.get("kind") == "sea_encounter" for f in out.effects)

    s, e, pc, g, here, wet = _coast(worlds)
    _ship_at_quay(e, pc, g.cell(*here)["town"])
    met["kind"] = "pirates"
    out = _move(e, wet)
    assert s.sea and s.sea.get("hostile"), out.tell


# --- old saves ------------------------------------------------------------------------------

def test_a_vessel_from_an_older_save_has_no_hex_and_keeps_one_when_it_has_it():
    v = ships.Vessel.from_dict({"id": "ship-keelboat-abc", "kind": "keelboat", "hp": 60})
    assert v.hex is None and "hex" not in v.as_dict()
    v.hex = [3, -4]
    assert ships.Vessel.from_dict(v.as_dict()).hex == [3, -4]


def test_a_save_standing_where_the_coast_now_runs_is_stood_on_land(worlds):
    """A save from before the channels whose party stood on a hex a channel now covers is
    stood on the nearest land hex on load, its place id moved everywhere the scene writes
    it; a save already on the coast's version is left alone."""
    a = atlas_mod.atlas(worlds)
    s = Scene()
    lay = hexes.held_layout(s, a)
    g = hexes.grid(a, lay)
    before = hexes.Grid(a, lay, channels=False)
    cut = next(((q, r) for (q, r) in (unk for c in g.cities
                                      for unk in hexes._spiral(g.town_hex[c["id"]], 4))
                if not g.cell(q, r)["land"] and before.cell(q, r)["land"]), None)
    if cut is None:
        pytest.skip("no channel crosses land near a town in this export")
    old = before.cell(*cut)
    pid = f"{old['near']}~{old['ground']}:@{hexes.slug(*cut)}"
    data = {"scene": {"location_id": old["near"], "at": pid,
                      "people": {"pc": {"at": pid}},
                      "hexes": {"grid": hexes.GRID_VERSION, "layout": lay}}}
    assert hexes.mend_save(data, a)
    now = data["scene"]["at"]
    h = hexes.parse_place(now)
    assert h is not None and g.cell(*h)["land"] and now != pid
    assert data["scene"]["people"]["pc"]["at"] == now
    assert data["scene"]["hexes"]["coast"] == hexes.COAST_VERSION
    assert not hexes.mend_save(data, a)


def test_no_road_starts_on_the_water(worlds, calm):
    """Live 2026-11-21: a party rowed out of Harpost walked its road to Grotburrow from the
    boat, and the exits row offered every road out of town. Afloat in a rowboat or the
    water, a journey is refused with the way off it named, and the row says so."""
    from play import exits

    s, e, pc, g, here, wet = _coast(worlds)
    pc.purse = {"gp": 5}
    assert _move(e, wet).status != "refused"
    leg = next((x for x in journey.legs_from(worlds, s.location_id) if not x.by_sea), None)
    if leg is not None:
        r = e.run(e.validate([{"op": "journey", "actor": "pc", "because": "x",
                                "params": {"to": leg.to_id}}], origin="author:test"))
        out = r.outcomes[-1]
        assert out.status == "refused" and "landfall" in out.tell
        assert e.afloat(g)[0] == "boat"
    assert all(row.get("blocked") for row in exits.exits(e, worlds))


def test_a_swimmer_swims_on_without_naming_it_again(worlds, calm):
    """Live 2026-11-21: in the water, the next click on a lit water hex was refused as
    though the party stood on the shore with no boat. The swim was chosen already."""
    s, e, pc, g, here, wet = _coast(worlds)
    pc.hp = pc.hp_base = 200
    assert _move(e, wet, how="swim").status != "refused"
    nxt = next((h for h in hexes.neighbours(*wet) if not g.cell(*h)["land"]), None)
    if nxt is None:
        pytest.skip("a one-hex channel here")
    assert nxt in e.hex_reach(g)
    assert _move(e, nxt).status != "refused"


def test_a_swim_speed_crosses_a_hex_in_the_hours_the_slip_states(worlds, calm):
    """Live 2026-11-21: the slip said "about five hours" to an undine (swim 30 ft) and the
    swim took four, `_swim_out` moving her a full tactical swim speed every round. A swim
    speed crosses at Table 3-2's hours for that speed, as a walker does."""
    from rules import water

    s, e, pc, g, here, wet = _coast(worlds)
    land = pc.speeds()
    pc.speeds = lambda: {**land, "swim": 30}      # an undine's body, as the owner's Shadow
    assert water.swim_speed(pc) == 30
    start = s.clock_minutes
    assert _move(e, wet, how="swim").status != "refused"
    want = hexes.swim_hours(pc.speed_feet, g.sea_miles, 30) * 60
    assert abs((s.clock_minutes - start) - want) <= 1


def test_a_body_out_cold_does_not_swim_on_with_ease(worlds, calm):
    """Live 2026-11-21: the owner's undine, out cold from a fortnight's thirst, "swims out
    ... with ease" hex after hex, her swim speed read before her body. A swimmer who
    cannot act is refused the next hex, and a swim speed no longer carries a body that is
    down."""
    s, e, pc, g, here, wet = _coast(worlds)
    pc.hp = pc.hp_base = 200
    assert _move(e, wet, how="swim").status != "refused"
    land = pc.speeds()
    pc.speeds = lambda: {**land, "swim": 30}
    pc.add_condition("unconscious", source="thirst", origin="author:test")
    assert pc.is_down
    nxt = next(iter(e.hex_reach(g)))
    out = _move(e, nxt)
    assert out.status == "refused" and "cannot swim" in out.tell
    made, _rounds, said = e._swim_out(pc, 60, "calm", goal="the shore", most_hours=1)
    assert not any("with ease" in x for x in said)


def test_her_stores_feed_and_water_her_people_under_sail(worlds, calm):
    """Live 2026-11-21: ten hexes under sail (sixty hours) left the PC 47 points of thirst
    damage, the hex step charging the body as a march with no water. A ship feeds and
    waters her people, as on any voyage (`_sail`)."""
    s, e, pc, g, here, wet = _coast(worlds)
    _ship_at_quay(e, pc, g.cell(*here)["town"])
    to, back = wet, here
    told = []
    for _ in range(10):
        out = _move(e, to)
        assert out.status != "refused", out.tell
        told.append(out.tell)
        to, back = back, to
    # Sleep is still the body's own (sixty hours awake tells), thirst and hunger are not.
    assert not any("thirst" in t or "hunger" in t for t in told), told
    assert int(getattr(pc, "thirst_checks", 0) or 0) == 0
