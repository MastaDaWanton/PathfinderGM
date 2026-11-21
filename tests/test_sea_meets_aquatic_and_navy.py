"""At sea, only aquatic creatures and ships are met (owner ruling 2026-11-21).

Before it, the sea's creature band read the Environment line alone (`ontheway.open_water`):
74 creatures of the shipped book could come up at a ship's rail, and one of them, the
living mirage ("any deserts or oceans", fly 20 ft., no swim), is no swimmer at all. The
patrol band ("naval") was one line with no ship, no flag and no crew.
Research: docs/research/2026-11-21-wild-draws.md.
"""
from __future__ import annotations

from rules import bestiary, maps, ontheway, states
from rules.activeeffect import ActiveEffect
from rules.dice import Dice
from tests.test_morale_threats_ships import at_sea  # noqa: F401 — the fixture


def _row(name):
    return next(r for r in bestiary.imported().values() if r["name"] == name)


def test_a_flyer_of_the_ocean_line_is_not_met_at_sea_and_the_sea_s_own_are():
    """The defect: the living mirage passed `open_water` on its Environment line alone.
    The dragon turtle ("temperate aquatic") was left out, and a frog of "marshes and
    aquatic" must stay out."""
    assert not ontheway.open_water(_row("Living Mirage"))
    for name in ("Shark", "Dragon Turtle", "Elasmosaurus", "Whale", "Penguin"):
        assert ontheway.open_water(_row(name)), name
    assert not ontheway.open_water(_row("Poison Frog"))


def test_every_creature_drawn_at_sea_swims_and_none_fits_falls_back_to_a_ship():
    """Real draws, 3 bands x 6 levels x 40 seeds: every creature the sea sends is aquatic
    by line and body; a draw with no aquatic creature becomes a merchant, never a land
    beast."""
    seen = 0
    for climates in ((), ("warm",), ("cold",)):
        for level in (1, 3, 5, 8, 12, 16):
            for seed in range(40):
                met = ontheway._sea_meeting(Dice(seed=seed), "creature", 50, level, None,
                                            climates)
                assert met.kind in ("creature", "merchant"), met.kind
                if met.kind == "creature":
                    seen += 1
                    assert ontheway.open_water(met.creature), met.creature["name"]
    assert seen


def _navy(engine, ship):
    met = ontheway.Meeting(kind="naval", roll=50, count=0)
    return engine._met_at_sea(ship, met)


def test_a_patrol_flies_the_flag_of_a_nation_of_her_waters_and_lets_an_honest_ship_go(at_sea):
    scene, engine, pc, ship = at_sea
    said, fx = _navy(engine, ship)
    ours = {maps.nation_of(engine.world, p) for p in (ship.came_from, ship.bound_for)}
    assert fx[0]["nation"] in ours and engine.world.get(fx[0]["nation"]) is not None
    assert engine.world.get(fx[0]["nation"]).name in said
    assert engine.vessel(fx[0]["vessel"]).kind == "warship"
    assert not scene.sea and fx[0]["hostile"] is False, said


def test_a_patrol_runs_down_a_ship_whose_master_is_wanted_in_her_nation(at_sea):
    """Wanted in a town of the patrol's nation: hostile, the pirate bands, and her people
    are marines when they come over the rail."""
    scene, engine, pc, ship = at_sea
    ours = {maps.nation_of(engine.world, p) for p in (ship.came_from, ship.bound_for)}
    for town in (r["id"] for r in engine.world.play["settlements"]):
        if maps.nation_of(engine.world, town) in ours:
            pc.apply_effect(ActiveEffect(name="a warrant", kind="situation",
                                         key=states.wanted_tag(town), source="test",
                                         duration="until-dismissed",
                                         tags=(states.wanted_tag(town),)))
    said, fx = _navy(engine, ship)
    assert scene.sea.get("hostile") and scene.sea.get("navy") in ours, said
    assert "wanted" in said
    theirs = engine.vessel(scene.sea["theirs"])
    met = engine._defenders(theirs, "deck")
    assert met and all("marine" in a.name for a in met)


def test_a_world_with_no_nation_for_her_ports_meets_a_merchant_not_an_invented_flag(at_sea,
                                                                                   monkeypatch):
    scene, engine, pc, ship = at_sea
    monkeypatch.setattr(maps, "nation_of", lambda world, sid: "")
    said, fx = _navy(engine, ship)
    assert fx[0]["met"] == "merchant" and "merchantman" in said
