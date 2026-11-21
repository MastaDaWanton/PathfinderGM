"""The law inside the walls, the theft a witness swore, and a temple's healing for pay.

Playtest 2026-11-16 (a human outlaw in Mirabalos, wanted for taking the Red Gull). Each test
names the item and what was measured:

* #73 a walk from the cathedral to the docks — inside the walls, the gate never on the
  route — was stopped at the east crossing: "the gate is where the watch stands";
* #73 / #84 the refusal's "leave by another way" listed every venture spot in town, the
  sewers and the outfall twice, all dead ends under the streets;
* #78 the exits row offered the docks as a few minutes' walk and every walk was refused;
* #85 the theft of the Red Gull "fell for want of proof: nobody saw" though the master she
  took it from swore it;
* #86 yielding, questioning and release took eight minutes of clock;
* #70 a city cathedral's priest could not heal for pay: no spellcasting service existed.
"""
from __future__ import annotations

import pytest

from play import exits
from rules import keepers, ontheway, places, services, states, trial
from rules.activeeffect import ActiveEffect
from tests.test_ships_and_piracy import _docks, _travel, held_at_quay  # noqa: F401
from tests.test_ships_at_sea import MIRABALOS, PANGRELLA, _at_port

CATHEDRAL = f"{MIRABALOS}~urban:the-cathedral"


@pytest.fixture
def quiet(monkeypatch):
    monkeypatch.setattr(ontheway, "street", lambda *a, **k: None)
    monkeypatch.setattr(ontheway, "road", lambda *a, **k: None)


def _want(pc, town=MIRABALOS):
    tag = states.wanted_tag(town)
    pc.apply_effect(ActiveEffect(name="wanted", kind="situation", key=f"test:{tag}",
                                 source="test:warrant", origin="test:warrant",
                                 duration="until-dismissed", tags=(tag,)))


def test_wanted_walks_to_the_docks_inside_the_walls(quiet):
    """#73: cathedral -> north crossing -> great square -> east crossing was stopped there,
    because the docks are one of `places.ENTRANCES` and were asked as the arch. In a town
    with a gate, the gate alone is where the watch stands on a walk that stays inside."""
    scene, engine, pc = _at_port()
    engine.place_party(CATHEDRAL)
    _want(pc)
    out = next(o for o in _travel(engine, "the docks") if o.op == "travel")
    assert "watch stands" not in out.tell, out.tell
    assert scene.at == _docks(engine).id
    # The arch itself is still shut to her, from inside as from outside.
    engine.place_party(CATHEDRAL)
    out = next(o for o in _travel(engine, "the gate") if o.op == "travel")
    assert "the gate is where the watch stands" in out.tell and scene.at == CATHEDRAL


def test_the_exits_row_and_the_walk_agree_about_the_docks(quiet):
    """#78: the row offered "the docks, a few minutes' walk" and the walk was refused. Asked
    one question (`watch_at_the_way_out`), they agree: open, and the gate shut."""
    scene, engine, pc = _at_port()
    _want(pc)
    for start in ("the-east-crossing", "the-gardens", "the-cathedral"):
        here = f"{MIRABALOS}~urban:{start}"
        engine.place_party(here)
        rows = {r["name"]: r for r in exits.ways_from(engine, PANGRELLA, [here])[here]}
        if "the docks" in rows:
            assert not rows["the docks"]["blocked"], (start, rows["the docks"])
        if "the gate" in rows:
            assert "wanted" in rows["the gate"]["blocked"]


def test_the_way_round_names_no_dead_end_under_the_streets(quiet):
    """#73/#84: "Leave by another way — the crypt, the stair, the niches, the deep chamber,
    the sewers, the outfall, the main channel, the sump, the sewers, the outfall, the main
    channel". Only ground outside the walls a walk reaches past no watch is named, each
    once; with none, the refusal names no place at all."""
    scene, engine, pc = _at_port()
    for under in ("the-great-square", "the-gardens"):
        engine.place_party(f"{MIRABALOS}~urban:{under}")
        engine.run(engine.validate([{"op": "venture", "actor": "pc", "because": "t",
                                     "params": {"kind": "sewers"}}], origin="author:test"))
    assert any(p.name == "the sewers" for p in engine.places())
    engine.place_party(CATHEDRAL)
    _want(pc)
    out = next(o for o in _travel(engine, "the gate") if o.op == "travel")
    assert "the sewers" not in out.tell and "outfall" not in out.tell, out.tell
    assert "Find another way past the watch, or clear your name." in out.tell


def test_a_ship_her_master_swore_is_a_witnessed_theft_and_goes_back(held_at_quay):
    """#85: turned in, "The accusation of theft falls for want of proof: nobody saw Vesna
    Kroll do it" — the accuser was the master who yielded her under the knife. His sworn
    word is a witness's: the charge stands, is priced at the ship's book price (CRB Table
    6-9), and at sentence the ship goes back to him."""
    from rules import ships

    scene, engine, pc, ship = held_at_quay
    ships_master = ships.master_of(engine.crew_of(ship))
    _travel(engine, _docks(engine).id)
    town = scene.location_id
    chs = trial.charges(engine, pc, town)
    assert [(c.kind, c.proof) for c in chs] == [("theft", "witnessed")], chs
    assert chs[0].worth_gp == 10000 and chs[0].subject_name == ships_master.name
    start = scene.clock_minutes
    out = trial.take_in(engine, pc, [], town)
    assert "want of proof" not in out.tell, out.tell
    held = trial.custody(pc)
    assert held is not None
    trial._after_questioning(engine, pc, held, town)
    done = trial._sentence(engine, pc, trial.custody(pc), town)
    assert engine.vessel(ship.id).held_by == "", done.tell
    assert f"{ship.name} to {ships_master.name}" in done.tell
    assert scene.clock_minutes > start


def test_questioning_takes_hours(held_at_quay):
    """#86: yielding, questioned and released took 8 minutes of clock, walk included. Being
    taken in and questioned is two hours (law.json `questioning`)."""
    scene, engine, pc, _ship = held_at_quay
    engine.place_party(f"{scene.location_id}~urban:the-market"
                       if places.find(engine.places(), "the market") else scene.at)
    start = scene.clock_minutes
    trial.take_in(engine, pc, [], scene.location_id)
    assert scene.clock_minutes - start >= 120


def _priest(engine):
    # Noon, when the temple keeps its doors open (`keepers.hours_of`).
    engine.scene.clock_minutes = (engine.scene.clock_minutes // 1440 + 1) * 1440 + 12 * 60
    _travel(engine, "the cathedral")
    priest = keepers.keeper_in(engine.scene, engine.scene.at)
    assert priest is not None and services.keeps_a_temple(priest)
    return priest


def test_the_book_prices_a_temples_castings():
    """#70: CRB, caster level x spell level x 10 gp at the lowest cleric caster level, the
    material added: cure light wounds 10 gp, cure moderate 60, restoration 280 + 100."""
    by = {r["spell"]: r["gp"] for r in services.menu("city")}
    assert by["cure-light-wounds"] == 10 and by["cure-moderate-wounds"] == 60
    assert by["restoration"] == 380
    # GameMastery Guide's settlement spellcasting caps what a small place casts.
    assert "restoration" not in {r["spell"] for r in services.menu("village")} or \
        services.MAX_LEVEL_BY_SCALE["village"] >= 4
    assert services.find("to heal me", "city")["spell"] == "cure-light-wounds"


def test_the_cathedral_priest_heals_for_pay(quiet):
    """#70 (T289): "Can you heal me? I can pay." got "I am not a doctor, nor do I possess the
    arts of healing", with 12 gp in her purse and a 10 gp cure in the book. The buy door
    casts it through the one cast door, the hit points back through the heal path."""
    scene, engine, pc = _at_port(gp=12)
    priest = _priest(engine)
    pc.damage = 0
    pc.hp = max(1, pc.hp_max - 6) if hasattr(pc, "hp_max") else pc.hp
    before_hp, before_cp = pc.hp, sum(pc.purse.values())
    res = engine.run(engine.validate(
        [{"op": "buy", "actor": "pc", "because": "healing",
          "params": {"item": services.PREFIX + "cure-light-wounds"}}],
        origin="author:test"))
    out = res.outcomes[0]
    assert out.status == "resolved", out.tell
    assert any(e.get("kind") == "heal" and e.get("ref") == "pc" for e in out.effects), out.tell
    assert pc.hp > before_hp and priest.name in out.tell
    assert pc.purse != {"gp": 12}
    # Too dear: nothing cast, nothing paid.
    purse = dict(pc.purse)
    res = engine.run(engine.validate(
        [{"op": "buy", "actor": "pc", "because": "healing",
          "params": {"item": services.PREFIX + "restoration"}}], origin="author:test"))
    assert pc.purse == purse and "Nothing is cast" in res.outcomes[0].tell


def test_healing_asked_of_the_priest_is_bought_never_begged(quiet):
    """#70: a request of the temple's keeper for healing is a purchase at the counter
    (`requests.offered`), never a Diplomacy favour that could take it for nothing."""
    from rules import requests

    scene, engine, pc = _at_port()
    priest = _priest(engine)
    got = requests.offered(scene, priest, "to heal my wounds")
    assert got is not None and got[0] == "goods" and got[1]["spell"] == "cure-light-wounds"
    assert requests.offered(scene, priest, "a sword") is None
