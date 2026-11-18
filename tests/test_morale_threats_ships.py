"""Nobody yielded and nothing could be seized: threats, morale and taking a ship.

Playtest 2026-11-15 (the owner's run on 0.3.6, a human outlaw who robs, is gaoled and takes
passage, then tries to take the ship). Each test names the item and what was measured:

* #21 Intimidate 23 against DC 10 to rob a merchant: "The merchant warms: is well disposed
  towards you", and no purse changed hands;
* #26 the cowed merchant still read "Friendly" while she fought him;
* #30 a merchant punched in round 2 "remains unmoving in your space";
* #92 the captain and the hand stood idle five rounds while a creature bit their passenger;
* #93 / #94 / #97 a blade at the captain's throat, "the Red Gull is mine now" and "yield the
  Red Gull to me or die" (the captain at 1 of 11) did nothing at all;
* #98 the spoken demand used her whole turn in the fight;
* #18 / #52 a shove was "no rule applied", or a Strength check against nobody;
* #22 "a well-dressed merchant" was answered with a guild leader in another town;
* #60 "step back" ran her 30 ft;
* #89 a Small penguin at a sailing ship's rail bit a human; #90 her coin was renamed at sea.
"""
from __future__ import annotations

import pytest

from rules import attitude, morale, ontheway, ships
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from tests.test_ships_at_sea import _at_port, _journey
from world import loader

WORLD = loader.load_cached("fixtures/pangrella-campaign.json")
TOWN = "5bbd0c40345f"
MARKET = f"{TOWN}~urban:the-market"


def _table(seed: int = 5, template: str = "thug", name: str = "the merchant"):
    scene = Scene(location_id=TOWN)
    scene.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(scene, Dice(seed=seed), world=WORLD)
    engine.place_party(MARKET)
    who = scene.add(instantiate(template, scene=scene, name=name))
    return scene, engine, who


def _threaten(engine, who, face: int, demand: str = ""):
    res = engine.run(engine.validate(
        [{"op": "check", "actor": "pc", "target": who.ref, "because": "a threat",
          "params": {"skill": "intimidate", **({"demand": demand} if demand else {})}}],
        origin="author:test"))
    if res.awaiting:
        res = engine.resume(face)
    return next(o for o in res.outcomes if o.op == "check")


# --- #21, #26: a threat out of a fight -----------------------------------------------------

def test_a_robbery_by_threat_cows_him_and_hands_over_the_purse():
    """#21: Intimidate 23 vs 10 told the player the merchant "warms: is well disposed
    towards you" and nothing was handed over. By the book (CRB p.99) he complies with what
    does not endanger him and acts friendly for 1d6x10 minutes, then treats you as
    unfriendly."""
    scene, engine, who = _table()
    who.purse = {"sp": 7, "cp": 4}
    pc = scene.pc()
    before = dict(pc.purse)
    out = _threaten(engine, who, 20, demand="hand_over")
    assert out.verdict == "success"
    assert "warms" not in out.tell and "cowed" in out.tell, out.tell
    assert "hands over" in out.tell, out.tell
    assert who.purse == {} and pc.purse != before
    assert any(e.get("kind") == "give" and e.get("count") == 74 for e in out.effects)
    # Friendly while it holds; unfriendly when it lapses (the book's "treats you as
    # unfriendly"), which the standing regard now carries.
    assert attitude.of(who) == "friendly"
    who.remove_effects(match=lambda e: (e.payload or {}).get("cowed"))
    assert attitude.of(who) == "unfriendly"


def test_harm_breaks_the_friendliness_a_threat_forced():
    """#26: the merchant read "Friendly" in the scene list while she fought him. A cowed
    step is broken by harm as a charm is (`attitude.harmed`)."""
    scene, engine, who = _table()
    _threaten(engine, who, 20)
    assert attitude.of(who) == "friendly"
    attitude.harmed(engine, who, scene.pc(), "test", seen=True)
    assert attitude.of(who) == "hostile"


# --- #97: a threat in a fight is Demoralize, and a demand to yield is made good ----------

def _fight(engine, who):
    engine._ensure_encounter(engine.scene.pc().ref, target=who.ref)
    assert who.ref in [r for refs in engine.scene.sides.values() for r in refs]


def test_a_threat_in_a_fight_shakes_and_a_healthy_foe_fights_on():
    scene, engine, who = _table()
    _fight(engine, who)
    out = _threaten(engine, who, 20, demand="yield")
    assert out.verdict == "success" and who.has_state("state.fear.shaken"), out.tell
    assert not morale.yielded(who)


def test_yield_or_die_to_a_foe_at_half_his_blood_makes_him_yield():
    """#97: "yield the Red Gull to me or die" to a captain at 1 of 11 was talk; he fought
    on. Made against somebody at half their hit points or worse, a person yields — or
    runs, ashore, where there is somewhere to run."""
    scene, engine, who = _table()
    _fight(engine, who)
    who.hp = 1
    out = _threaten(engine, who, 20, demand="yield")
    assert "runs" in out.tell or "yields" in out.tell, out.tell
    assert not any(who.ref in refs for refs in scene.sides.values())


def test_a_civilian_in_a_mugging_pays_and_gives_up_the_fight():
    """#21 again, inside the fight the shove opened: measured on the beat-16 snapshot,
    "demand his purse" only shook the merchant. A civilian threatened in a fight pays."""
    scene, engine, who = _table(template="merchant-level-1")
    who.purse = {"sp": 3}
    _fight(engine, who)
    out = _threaten(engine, who, 20, demand="hand_over")
    assert "hands over" in out.tell and morale.yielded(who), out.tell
    assert who.purse == {}


# --- #30: morale at the top of a creature's turn -----------------------------------------

def test_a_hurt_civilian_runs_from_the_fight():
    """#30: a merchant punched in round 2 "remains unmoving in your space". A civilian
    ashore, hurt, runs (the owner's splash ruling of 2026-10-06)."""
    scene, engine, who = _table(template="merchant-level-1")
    assert not engine.martial(who)
    _fight(engine, who)
    who.nonlethal = 2
    broke = engine.morale_turn(who.ref)
    assert broke and "runs" in broke[0].tell, broke
    assert who.ref not in scene.actors or not any(
        who.ref in refs for refs in scene.sides.values())


def test_a_fighter_checks_once_at_half_and_a_mindless_thing_never():
    scene, engine, who = _table()
    assert engine.martial(who)
    _fight(engine, who)
    assert engine.morale_turn(who.ref) == []          # unhurt: fights on, nothing rolled
    who.hp = max(1, who.hp_max // 2)
    engine.morale_turn(who.ref)
    assert who.has_state(morale.TESTED)
    # Checked once: whatever came of it, a second turn rolls nothing new.
    if any(who.ref in refs for refs in scene.sides.values()):
        assert engine.morale_turn(who.ref) == []
    golem = scene.add(instantiate("skeleton", scene=scene, name="the skeleton"))
    golem.abilities["int"] = None
    assert not morale.checks_morale(golem)


# --- #92, #94, #97: a ship's people defend her, yield with her master, and she is yours --

@pytest.fixture
def at_sea(monkeypatch):
    monkeypatch.setattr(ships, "day_at_sea", lambda dice, level: "calm")
    monkeypatch.setattr(ontheway, "sea", lambda *a, **k: None)
    scene, engine, pc = _at_port()
    _journey(engine)                        # booked: aboard at the quay
    _journey(engine, days=1)                # a day out
    ship = engine.aboard()
    assert ship is not None and not ship.at
    return scene, engine, pc, ship


def test_the_captain_yields_his_hand_stands_down_and_the_ship_is_the_players(at_sea):
    """#94 and #97: "the Red Gull is mine now" and "yield the Red Gull to me or die" had no
    path; a ship could not be taken without killing her crew. At sea there is nowhere to
    run, so a broken master yields, his people with him, and she is the player's."""
    scene, engine, pc, ship = at_sea
    crew = engine.crew_of(ship)
    assert len(crew) == 2, [a.name for a in crew]
    master = ships.master_of(crew)
    _fight(engine, master)
    master.hp = 1
    out = _threaten(engine, master, 20, demand="yield")
    assert morale.yielded(master), out.tell
    assert all(morale.yielded(a) for a in crew), out.tell
    assert engine.aboard().held_by == pc.ref
    assert "is yours" in out.tell, out.tell


def test_a_held_ship_comes_about_for_any_port_her_waters_reach(at_sea):
    scene, engine, pc, ship = at_sea
    ship.held_by = pc.ref
    engine._keep_vessel(ship)
    turned = engine._come_about(engine.aboard(), "Khalmorin")
    assert not isinstance(turned, str) and turned is not None
    assert engine._settlement_name(turned.bound_for) == "Khalmorin"
    refused = engine._come_about(engine.aboard(), "Nowhere-at-all")
    assert isinstance(refused, str) and "Khalmorin" in refused


def test_her_people_defend_their_deck_when_something_comes_over_the_rail(at_sea):
    """#92: the captain and the deckhand stood idle five rounds while a creature attacked
    their passenger on their own deck."""
    scene, engine, pc, ship = at_sea
    shark = instantiate("shark", scene=scene, name="the shark")
    row = {"id": "shark", "name": "shark"}
    met = ontheway.Meeting(kind="creature", roll=90, creature=row, template="shark",
                           count=1, aggressive=True)
    engine._meet_on_the_way = lambda m, zone="near": [
        {"ref": scene.add(shark, zone="near").ref}]
    _said, fx = engine._met_at_sea(ship, met)
    crew = engine.crew_of(ship)
    mine = next(refs for refs in scene.sides.values() if pc.ref in refs)
    assert crew and all(a.ref in mine for a in crew), fx


# --- #89: a sea creature's climate and temperament ----------------------------------------

def test_a_small_beast_does_not_come_at_people_and_a_cold_one_stays_in_cold_water():
    penguin = {"creature_type": "animal", "size": "small", "climates": ["cold"]}
    shark = {"creature_type": "animal", "size": "large", "climates": []}
    swarm = {"creature_type": "vermin", "size": "diminutive", "subtype": "swarm"}
    assert not ontheway.comes_at_you(penguin)
    assert ontheway.comes_at_you(shark) and ontheway.comes_at_you(swarm)
    assert not ontheway.in_climate(penguin, ("warm",))
    assert ontheway.in_climate(penguin, ()) and ontheway.in_climate(shark, ("warm",))


# --- #90: the coin keeps its name at sea ----------------------------------------------------

def test_the_purse_keeps_the_port_coin_once_at_sea(at_sea):
    from rules import goods

    scene, engine, pc, ship = at_sea
    at_sea_coins = goods.coins_here(WORLD, scene)
    scene_port = Scene(location_id=ship.came_from)
    assert [c.name for c in at_sea_coins] == [c.name for c in goods.coins_here(WORLD,
                                                                                scene_port)]


# --- #22: "a merchant" is any merchant ---------------------------------------------------------

def test_an_indefinite_person_is_never_a_figure_of_another_town():
    """#22 exactly: in Zhilvarnia, "a well-dressed merchant" was answered "Lyraea, Leader of
    Valtorian Merchant Guild, is in Pangrella, not here". By its own article it wants any
    merchant (no flag passed: the brief's sought section asked without one)."""
    from rules import scope

    zhilvarnia = "6953424c8a82"
    scene = Scene(location_id=zhilvarnia)
    scene.add(load_pc("fixtures/pc-kesst.json"))
    # A bare trade or title, definite too, is no longer answered with a figure of another
    # town (playtest 2026-11-17b #23: "the master of the arena" found an apprentice in
    # Xylorvotha by the word "master"); her own name still finds her.
    named = scope.look_for(WORLD, "the merchant", scene, zhilvarnia)
    assert "Lyraea" not in named["line"], named
    assert "Lyraea" in scope.look_for(WORLD, "Lyraea", scene, zhilvarnia)["line"]
    got = scope.look_for(WORLD, "a well-dressed merchant", scene, zhilvarnia)
    assert got["scope"] == "" and got["line"] == "", got


# --- the reader's acts, built ------------------------------------------------------------------

def test_a_threat_is_an_intimidate_check_carrying_the_demand():
    from gm import acts_to_ops

    scene, engine, who = _table()
    frame = {"actions": [{"act": "threaten", "target": "the merchant",
                          "says": "your purse or your life", "demand": "hand_over",
                          "span": "x"}]}
    rows = acts_to_ops.table(frame, scene)
    built = [i for r in rows for i in r.intents]
    assert built == [{"op": "check", "actor": "pc", "target": who.ref,
                      "params": {"skill": "intimidate", "demand": "hand_over"},
                      "because": "the player threatens the merchant"}], rows
    engine.validate(built, origin="author:test")


def test_a_shove_is_a_bull_rush_and_a_named_blow_in_a_fight_is_never_dropped():
    """#18 / #52 and #93: "shove him against the wall" applied no rule; "I leave the
    penguin ... put it to the captain's throat" dropped the blow behind a `leave`."""
    from gm import acts_to_ops

    scene, engine, who = _table()
    _fight(engine, who)
    frame = {"actions": [{"act": "leave", "place": "the penguin", "span": "a"},
                         {"act": "attack", "target": "the merchant", "blow": "shove",
                          "span": "b"}]}
    rows = acts_to_ops.table(frame, scene)
    acts_to_ops.victims(rows, frame, scene)
    built = [i for r in rows for i in r.intents if i["op"] == "attack"]
    assert built and built[0]["target"] == who.ref, [r.note for r in rows]
    assert built[0]["params"]["manoeuvre"] == "bull rush"


def test_a_blow_after_a_seek_lands_on_the_one_the_plan_found():
    """#18 / #21: "I pick out a merchant ..., shove him against the wall and demand his
    purse" — the plan introduced the merchant, the shove was never struck, and the live
    replay printed "there is nobody here who is him" for the demand."""
    from gm import acts_to_ops, judgement

    scene, engine, who = _table(name="Grix")
    frame = {"actions": [{"act": "seek", "target": "a merchant", "span": "a"},
                         {"act": "attack", "target": "him", "blow": "shove", "span": "b"},
                         {"act": "threaten", "target": "him", "demand": "hand_over",
                          "span": "c"}]}
    rows = acts_to_ops.table(frame, scene)
    acts_to_ops.victims(rows, frame, scene)
    assert not any(r.missing for r in rows), [r.missing for r in rows]
    plan = [{"op": "introduce", "params": {"who": "merchant", "how": "already_here",
                                           "template": "merchant-level-1"}},
            {"op": "say", "actor": "pc", "target": "new1", "params": {"words": "purse"}}]
    out = judgement.inject_fight(plan, "", scene, rows=rows, frame=frame)
    assert out[1]["op"] == "attack" and out[1]["target"] == "new1", out
    assert out[1]["params"] == {"manoeuvre": "bull rush"}
    assert out[2]["op"] == "check" and out[2]["target"] == "new1", out
    assert out[2]["params"] == {"skill": "intimidate", "demand": "hand_over"}
    engine.validate(out, origin="author:test")
    # The live replay's plan wrote its own threat with no demand: it carries the reading's.
    own = plan + [{"op": "check", "actor": "pc", "target": "new1",
                   "params": {"skill": "intimidate"}}]
    out = judgement.inject_fight(own, "", scene, rows=rows, frame=frame)
    checks = [r for r in out if r["op"] == "check"]
    assert len(checks) == 1 and checks[0]["params"]["demand"] == "hand_over", out


def test_a_step_back_in_a_fight_is_one_square():
    """#60: "step back" read `go` with no place; the plan chose square (0, 0) and she ran
    30 ft into open ground."""
    from gm import acts_to_ops

    scene, engine, who = _table()
    _fight(engine, who)
    pc = scene.pc()
    here = tuple(scene.positions[pc.ref])[:2]
    rows = acts_to_ops.table({"actions": [{"act": "go", "span": "step back"}]}, scene)
    moves = [i for r in rows for i in r.intents if i["op"] == "move"]
    assert len(moves) == 1, [r.note for r in rows]
    to = moves[0]["params"]["square"]
    assert max(abs(to[0] - here[0]), abs(to[1] - here[1])) == 1


def test_the_reader_offers_threaten_with_its_demand_and_the_new_blows():
    from gm import interpret

    alts = interpret.per_act_schema()["properties"]["actions"]["items"]["anyOf"]
    threat = next(a for a in alts if a["properties"]["act"].get("const") == "threaten")
    assert threat["properties"]["demand"]["enum"] == list(interpret.DEMANDS)
    assert tuple(interpret.DEMANDS) == morale.DEMANDS
    blow = next(a for a in alts if a["properties"]["act"].get("const") == "attack")
    assert "shove" in blow["properties"]["blow"]["enum"]


# --- #98: words alone in a fight spend no action -------------------------------------------

def test_words_alone_in_a_fight_hand_the_turn_to_nobody():
    from types import SimpleNamespace

    from play import views

    scene, engine, who = _table()
    _fight(engine, who)
    said = SimpleNamespace(outcomes=[SimpleNamespace(op="say", actor="pc")])
    struck = SimpleNamespace(outcomes=[SimpleNamespace(op="say", actor="pc"),
                                       SimpleNamespace(op="check", actor="pc")])
    assert views._only_spoke(scene, said)
    assert not views._only_spoke(scene, struck)
