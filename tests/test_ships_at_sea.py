"""Taking passage: a berth bought, a deck stood on, days at sea, and the storm that can
end it (`Engine._book_passage`, `_sail`, `_wreck`; `rules/ships.py`).

Owner, 2026-11-13: "make ships boardable and have sea/ocean travel be accessible ... I
should be able to get on a boat and travel", and "over sea/ocean travel should be rolled
by the day with a small chance based on volatility to have storm wreck the ship". Measured
the day before: the ~740 lines of ship rules were unreachable from play — a sea leg passed
the clock without anybody standing on a deck, nothing was ever paid, and no weather was
ever rolled. Pangrella's two continents could not be crossed by ship at all: its only sea
routes start inland, and its four ports had no route between them.
"""
from __future__ import annotations

from rules import encounter_budget, journey, places, ships, volatility
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

PANGRELLA = loader.load_cached("fixtures/pangrella-campaign.json")
MIRABALOS, ZHILVARNIA = "7ef5e373c993", "6953424c8a82"


def _at_port(seed: int = 4, gp: int = 500):
    scene = Scene(location_id=MIRABALOS)
    pc = load_pc("fixtures/pc-kesst.json")
    scene.add(pc)
    engine = Engine(scene, Dice(seed=seed), world=PANGRELLA)
    engine.place_party(f"{MIRABALOS}~urban:the-docks")
    pc.purse = {"gp": gp}
    return scene, engine, pc


def _journey(engine, to: str = "Zhilvarnia", **params):
    engine._journeyed = ""
    res = engine.run(engine.validate(
        [{"op": "journey", "actor": "pc", "because": "passage",
          "params": {"to": to, **params}}], origin="author:test"))
    return res.outcomes[-1]


def test_the_two_continents_are_a_passage_apart_both_ways():
    """Pangrella's stated sea routes both start inland, and its ports had no route between
    them: no ship crossed. Continents are separated by water (ruling 2026-09-16), so a
    port now sells passage to every port across it that no stated route reaches."""
    there = {l.to_id: l for l in journey.legs_from(PANGRELLA, MIRABALOS)}
    assert ZHILVARNIA in there and there[ZHILVARNIA].by == "sea"
    assert there[ZHILVARNIA].from_port and there[ZHILVARNIA].source == "derived"
    # As wide as the world's own stated crossings (192 and 216 miles), not the tree's
    # seven days: 7 days was 100 gp a head at the book's fare.
    assert there[ZHILVARNIA].days_apart == 2
    back = {l.to_id for l in journey.legs_from(PANGRELLA, ZHILVARNIA)}
    assert MIRABALOS in back
    # Never between two ports on one continent: the roads the world wrote stand.
    for leg in journey.legs_from(PANGRELLA, MIRABALOS):
        if leg.source == "derived" and leg.by == "sea":
            assert journey.continent_of(PANGRELLA, leg.to_id) \
                != journey.continent_of(PANGRELLA, MIRABALOS)


def test_booking_takes_the_fare_and_stands_the_party_on_a_real_deck():
    """1 sp a mile a head (CRB Table 6-9), out of the purse; then the deck is where they
    stand — a place with exits, the docks one of them while she lies at the quay."""
    from rules import goods

    scene, engine, pc = _at_port()

    had = goods.in_copper(pc.purse)
    out = _journey(engine)
    ship = engine.aboard()
    assert ship is not None and ship.bound_for == ZHILVARNIA, out.tell
    miles = ship.days_total * ships.miles_a_day(ship.kind)
    assert had - goods.in_copper(pc.purse) == miles * ships.PASSAGE_CP_PER_MILE
    here = engine.here()
    assert here.id == ships.deck_of(ship) and places.terrain_of(here.id) == ships.DECK
    assert f"{MIRABALOS}~urban:the-docks" in here.exits
    # Deck to hold is a step: live, the exits row priced it "about an hour" as open ground.
    assert places.setting_of(here.id) == "in"
    assert {"the captain", "a deckhand"} <= {a.name for a in scene.actors.values()}


def test_a_short_purse_is_refused_with_the_price_and_takes_nothing():
    scene, engine, pc = _at_port(gp=1)
    out = _journey(engine)
    assert out.status == "refused" or "a silver piece a mile" in out.tell, out.tell
    assert pc.purse == {"gp": 1}
    assert engine.aboard() is None


def test_the_exits_row_offers_the_passage_and_then_the_voyage():
    """The UI door: the docks offer the passage as a journey, and once aboard the deck
    offers sailing on — both rows go to the journey op (`views._take_the_exit`)."""
    from play import exits

    scene, engine, pc = _at_port()
    rows = exits.exits(engine, PANGRELLA)
    passage = next(r for r in rows if r["id"] == ZHILVARNIA)
    assert passage["journey"] and not passage["blocked"]
    _journey(engine, to=passage["id"])
    rows = exits.exits(engine, PANGRELLA)
    sail = next(r for r in rows if r["id"] == ZHILVARNIA)
    assert sail["journey"]
    assert any(r["name"] == "the docks" for r in rows), "no gangplank back ashore"
    out = _journey(engine, to=sail["id"])
    assert scene.location_id == ZHILVARNIA, out.tell


def test_the_reader_takes_a_named_port_for_a_journey():
    """The narrated door: "I book passage to Zhilvarnia" filed as a go is still the
    journey (`interpret._road_to` reads the same legs)."""
    from gm import interpret

    scene, engine, pc = _at_port()
    frame = {"actions": [{"act": "go", "place": "Zhilvarnia"}]}
    assert "journey" in interpret.ops_for(frame, scene, engine.places())


def test_sailing_arrives_at_the_far_docks_after_the_days():
    scene, engine, pc = _at_port()
    _journey(engine)
    days = engine.aboard().days_total
    start = scene.clock_minutes
    out = _journey(engine)
    assert scene.location_id == ZHILVARNIA, out.tell
    assert engine.here().name == "the docks"
    assert scene.clock_minutes - start == days * ships.MINUTES_A_DAY
    assert "makes Zhilvarnia" in out.tell


def test_the_daily_storm_is_scaled_by_volatility_and_defaults_to_the_published_rate():
    """Ultimate Wilderness Table 4-28's windstorm (96-100) is a 5% day; one storm in ten
    is CRB Table 13-9's powerful kind, the one that wrecks. Volatility multiplies it.
    Over 4,000 seeded days calm water storms less than lawless water."""
    assert ships.storm_pct(2) == ships.STORM_PCT == 5.0
    assert volatility.factor(2) == 1.0
    counts = {}
    for level in (0, 2, 4):
        dice = Dice(seed=7)
        got = [ships.day_at_sea(dice, level) for _ in range(4000)]
        counts[level] = sum(1 for g in got if g != "calm")
    assert counts[0] < counts[2] < counts[4], counts
    assert 120 <= counts[2] <= 290, counts       # ~200 expected at 5%


def test_a_storm_is_told_as_a_storm_and_rides_an_effect(monkeypatch):
    scene, engine, pc = _at_port()
    _journey(engine)
    weather = iter(["storm"])
    monkeypatch.setattr(ships, "day_at_sea", lambda dice, level: next(weather, "calm"))
    out = _journey(engine)
    assert "storm" in out.tell.lower(), out.tell
    assert engine.aboard() is not None and engine.aboard().days_left > 0
    assert scene.location_id == engine.aboard().id, "at sea, the ship is the location"
    assert any(m.value == ships.STORM_PERCEPTION for m in pc.skill_modifiers("perception"))
    assert any(e.get("origin") == "rule:storm-at-sea" for e in out.effects)
    # Nobody walks from the deck to the market at sea.
    assert {p.name for p in engine.places()} <= {p.name for p in ships.rooms_at(scene.at)}


def test_a_wreck_washes_the_party_up_on_a_real_coast_with_what_it_cost(monkeypatch):
    scene, engine, pc = _at_port(seed=9)
    pc.inventory["woundwort"] = 3
    _journey(engine)
    vid = engine.aboard().id
    monkeypatch.setattr(ships, "day_at_sea", lambda dice, level: "wreck")
    out = _journey(engine)
    assert all(v["id"] != vid for v in scene.vessels), "the ship was not lost"
    assert scene.location_id in journey.ports(PANGRELLA)
    here = engine.here()
    assert here.id == scene.at and places.is_ring(here.id), here
    assert pc.has_state("state.impaired.fatigued")
    assert "woundwort" not in pc.inventory
    assert all(str(e.get("origin", "")).startswith("rule:") for e in out.effects
               if e.get("kind") in ("damage", "condition"))
    assert "storm breaks" in out.tell and "washes up" in out.tell, out.tell
    assert not any(a.name == "the captain" for a in scene.people.values())


def test_a_boarding_crew_is_priced_by_the_party_budget():
    """Up to four at the rail by the hull's crew, trimmed by `encounter_budget` on the
    guarded mix: a lone level-1 PC facing a galley's rail was four codex sailors."""
    from rules import npcs
    from tests.test_ships import _at_sea, _do

    sizes = set()
    for seed in range(6):
        scene, engine, _ours, theirs = _at_sea(seed=seed, theirs_scale="city")
        _do(engine, "close")
        _do(engine, "close")
        _do(engine, "board")
        met = [a for a in scene.actors.values() if not a.is_pc]
        apl = encounter_budget.party_apl(scene)
        each = encounter_budget.xp_of(npcs.choose(["sailor", "pirate"], scene.pc().level))
        assert 1 <= len(met) <= 4
        assert len(met) == 1 or len(met) * each <= encounter_budget.budget(
            apl + encounter_budget.TIERS["hard"]), (len(met), each, apl)
        sizes.add(len(met))
    assert sizes != {4}, "the budget never trimmed a galley's rail"


def test_a_save_mid_voyage_loads_and_sails_on(tmp_path, settings, monkeypatch):
    from play import campaign as cm

    settings.CAMPAIGN_DIR = tmp_path
    scene, engine, pc = _at_port()
    _journey(engine)
    _journey(engine, days=1)
    assert scene.location_id.startswith("ship-")
    c = cm.Campaign(id="voyage", world_source="fixtures/pangrella-campaign.json",
                    scene=scene)
    c.save()
    back = cm.Campaign.load(c.path())
    again = Engine(back.scene, Dice(seed=2), world=PANGRELLA)
    again.place_party(back.scene.at)
    ship = again.aboard()
    assert ship is not None and ship.sailed_at is not None and ship.passengers
    out = _journey(again)
    assert back.scene.location_id == ZHILVARNIA, out.tell
