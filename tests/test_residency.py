"""Where people are when the party is not looking (docs/the-population.md §4).

The user's ruling of 2026-09-25: the woman in the doorway "should stay there until i leave
or something moves them ... and once I leave that woman remains a resident of the
city/town/village unless she is a merchant or traveller" — "those people should persist
move around and their lives should evolve".

Measured before this was built (2026-09-27): the road out of town destroyed everybody who
did not come along. A woman met at the gate — Soren Kragnirath, regard 70 — came back two
days later as Korvin Korvath at regard 35: the record kept her face and life, and her name
and her standing lived on the body the road had thrown away. Within a town nobody ever
moved: a stallholder seen at noon stood at the stall through the night. Travellers never
travelled, and `last_met` was written by nothing, so the finder's `met` ring was empty.
"""
from __future__ import annotations

import ast
import time
from pathlib import Path

import pytest

from gm import judgement
from rules import attitude, population, residency, scope
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world.loader import load_cached

WORLD = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = WORLD.by_name("Vormoor", kind="CITY").id
HOUR = 60
DAY = 24 * HOUR


def _engine(clock=10 * HOUR):
    s = Scene(location_id=VORMOOR)
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = clock
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.place_party()
    e.settle_people()
    return s, e


def _person(s, phrase, work, **life):
    rec = population.note(s, phrase)
    occ = next(o for o in __import__("rules.lives", fromlist=["x"]).tables()["occupations"]
               if o["id"] == work)
    rec["life"].update(work=work, work_name=occ["name"], mobility=occ["mobility"], **life)
    if occ["mobility"] != "resident":
        rec["anchor"] = {"loc": s.location_id, "place": s.at, "t": s.clock_minutes}
        rec.pop("route", None)
    return rec


def _journey(e, to):
    for _ in range(10):
        e._journeyed = ""
        e.run(e.validate([{"op": "journey", "params": {"to": to}}], origin="author:test"))
        if WORLD.get(e.scene.location_id).name == to:
            return
    raise AssertionError(f"never reached {to}")


def _travel(e, place):
    e.run(e.validate([{"op": "travel", "params": {"place": place}}], origin="author:test"))


# --- leaving town is not the end of anybody ------------------------------------------------

def test_somebody_met_is_the_same_person_when_you_come_back():
    """Measured: Soren Kragnirath at regard 70 came back as Korvin Korvath at 35."""
    s, e = _engine()
    rec = _person(s, "woman mending nets by the gate", "fisher")
    ref = judgement.embody_sought(s, "I talk to the woman mending nets.", WORLD)
    her = s.people[ref]
    name = her.true_name
    attitude.set_regard(her, 70, "test")
    _journey(e, "Ledgerwarren")
    assert ref in s.people and ref not in s.actors, "kept in the world, out of the room"
    _journey(e, "Vormoor")
    _travel(e, s.people[ref].at if not residency.is_offstage(s.people[ref].at)
            else "the way in")
    back = s.people[ref]
    assert back.true_name == name and attitude.regard_of(back) == 70
    assert rec["ref"] == ref


def test_a_spawned_creature_nobody_knows_is_still_left_to_the_road():
    """RimWorld keeps world pawns for a reason (kin, memory, relationship) and lets the
    rest go. A thug the plan spawned, with no record and no standing, still goes."""
    s, e = _engine()
    thug = instantiate("thug", scene=s, name="thug")
    s.add(thug)
    _journey(e, "Ledgerwarren")
    assert thug.ref not in s.people


# --- residents keep a day ----------------------------------------------------------------------

def test_a_resident_is_at_work_by_day_and_home_by_night():
    s, e = _engine(clock=10 * HOUR)
    market = e.places()[1]
    _travel(e, market.name)
    rec = _person(s, "a broad-shouldered baker", "baker")
    day = residency.whereabouts(rec, s.clock_minutes + 2 * HOUR, WORLD, s.founded)
    night = residency.whereabouts(rec, s.clock_minutes + 14 * HOUR, WORLD, s.founded)
    assert day.kind == "place" and day.place == market.id
    assert night.kind == "home" and residency.is_offstage(night.place)


def test_nobody_moves_while_the_party_stands_with_them():
    """The ruling: she stays "until i leave or something moves them". Midnight passing
    while the party waits at the stall sends nobody home."""
    s, e = _engine(clock=17 * HOUR)
    rec = _person(s, "a stallholder with a ledger", "stallholder")
    ref = judgement.embody_sought(s, "I talk to the stallholder with a ledger.", WORLD)
    s.advance(8 * HOUR)
    e.run(e.validate([{"op": "narrate_only", "because": "t"}], origin="author:test"))
    assert ref in s.actors and population.where_now(rec, s, WORLD).place == s.at


def test_leaving_and_coming_back_at_night_finds_them_gone_home():
    s, e = _engine(clock=10 * HOUR)
    first = s.at
    _person(s, "a stallholder with a ledger", "stallholder")
    ref = judgement.embody_sought(s, "I talk to the stallholder with a ledger.", WORLD)
    elsewhere = next(p for p in e.places() if p.id != first)
    _travel(e, elsewhere.name)
    s.advance(12 * HOUR)
    _travel(e, next(p.name for p in e.places() if p.id == first))
    assert ref not in s.actors
    assert residency.is_offstage(s.people[ref].at)
    line = scope.look_for(WORLD, "the stallholder with a ledger", s, VORMOOR)["line"]
    assert "at home" in line and "stallholder" in line.lower()
    assert "sells" not in line and "work" not in line


def test_somebody_who_came_along_stays_moved_until_the_party_leaves_them():
    """The plan moved them ("the guard walks you to the market"): an escort is where the
    party took them, not sent back to their post the moment they arrive."""
    s, e = _engine(clock=10 * HOUR)
    _person(s, "a young guard", "guard")
    ref = judgement.embody_sought(s, "I talk to the young guard.", WORLD)
    s.people[ref].remove_effects(source="talk")
    going = next(p for p in e.places() if p.id != s.at)
    e.run(e.validate([{"op": "travel", "params": {"place": going.name, "with": [ref]}}],
                     origin="author:test"))
    assert ref in s.actors


def test_a_reload_where_the_party_already_stands_is_not_an_arrival():
    """`place_party` runs on every load. Were that an arrival, a save at 17:59 at the
    stall reloaded at 18:00 would send the stallholder home mid-conversation."""
    s, e = _engine(clock=10 * HOUR)
    moves = s.moves
    e.place_party(s.at)
    assert s.moves == moves and e.settle_people() == []


def test_the_first_slot_they_were_seen_in_is_theirs():
    """An observation beats the key (Stardew's overrides): somebody first seen at the
    well at two in the morning is out at that hour, whatever their trade's day says."""
    s, _ = _engine(clock=2 * HOUR)
    rec = _person(s, "a lamplighter", "smith")
    rec["first_seen"] = 2 * HOUR
    assert residency.schedule_for(rec)[0] == residency.WORK


# --- travellers travel -------------------------------------------------------------------------

def test_a_merchant_met_here_is_down_the_road_days_later():
    s, _ = _engine()
    rec = _person(s, "a spice merchant with a mule", "merchant")
    stops = residency.route(rec, s.clock_minutes + 20 * DAY, WORLD)
    towns = {x["at"] for x in stops if "at" in x}
    assert len(towns) >= 3, stops[:4]
    # The party goes about its business; standing beside him for twenty days would keep
    # him there (the ruling), which is not this question.
    s.at = "elsewhere"
    s.clock_minutes += 20 * DAY
    line = population.seen_line(rec, s, WORLD)
    assert "merchant" in line and ("road" in line or "now, not here" in line), line


def test_a_travellers_road_is_stored_and_the_same_on_every_asking():
    """Store what was rolled: a reload never re-walks a road."""
    s, _ = _engine()
    rec = _person(s, "a peddler with a pack", "peddler")
    first = residency.route(rec, s.clock_minutes + 30 * DAY, WORLD)
    assert rec["route"] == first
    again = dict(rec)
    again.pop("route")
    assert residency.route(again, s.clock_minutes + 30 * DAY, WORLD) == first


def test_seeing_a_traveller_again_walks_their_roads_from_there():
    s, _ = _engine()
    rec = _person(s, "a minstrel with a lute", "minstrel")
    residency.route(rec, s.clock_minutes + 10 * DAY, WORLD)
    s.clock_minutes += DAY
    population.seen(s, rec)
    assert "route" not in rec and rec["anchor"]["t"] == s.clock_minutes


def test_a_trader_takes_the_trade_roads_more_often_than_chance(monkeypatch):
    """A merchant goes where the world's trade goes (`World.routes_touching`). In
    Aurvantis every road out of every town IS a trade road (measured: 64 of 64
    settlements), because the export's roads are its trade routes; so the weighting is
    proved here with two of Vormoor's five roads standing for the trade."""
    legs = residency._legs(WORLD, VORMOOR)
    partners = {legs[0].to_id, legs[1].to_id}
    monkeypatch.setattr(residency, "_trade_partners", lambda world, loc: partners)
    hits = 0
    for n in range(300):
        rec = {"id": f"p{n}", "life": {"work": "merchant"}}
        leg = residency._next_leg(rec, VORMOOR, "", 1, WORLD)
        hits += leg.to_id in partners
    share = len(partners & {lg.to_id for lg in legs}) / len(legs)
    assert hits / 300 > share + 0.15, (hits, share)


def test_a_merchant_with_a_body_is_there_when_the_party_reaches_his_town():
    s, e = _engine()
    rec = _person(s, "a spice merchant with a mule", "merchant")
    ref = judgement.embody_sought(s, "I talk to the spice merchant.", WORLD)
    s.people[ref].remove_effects(source="talk")
    stay = next(x for x in residency.route(rec, s.clock_minutes + 30 * DAY, WORLD)[1:]
                if "at" in x and x["at"] != VORMOOR)
    s.location_id = stay["at"]
    s.clock_minutes = stay["from"] + (stay["to"] - stay["from"]) // 2
    s.clock_minutes += (12 * HOUR - s.clock_minutes % DAY) % DAY  # midday
    if s.clock_minutes >= stay["to"]:
        pytest.skip("the stay is shorter than the walk to noon")
    e.place_party()
    e.settle_people()
    assert population.where_now(rec, s, WORLD).location == stay["at"]
    body = s.people[ref]
    assert not residency.is_offstage(body.at)


def test_a_pilgrim_passes_through_and_is_gone():
    s, _ = _engine()
    rec = _person(s, "a barefoot pilgrim", "pilgrim")
    s.clock_minutes += 10 * DAY
    s.at = "elsewhere"
    assert population.where_now(rec, s, WORLD).kind == "gone"
    assert "moved on" in population.seen_line(rec, s, WORLD)


# --- meeting is recorded --------------------------------------------------------------------------

def test_speaking_with_somebody_is_meeting_them():
    """`last_met` was written by nothing: the finder's `met` ring was always empty."""
    s, e = _engine()
    rec = _person(s, "a woman with a basket", "washer")
    ref = judgement.embody_sought(s, "I talk to the woman with a basket.", WORLD)
    e.run(e.validate([{"op": "say", "params": {"words": "Good day.", "to": ref}}],
                     origin="author:test"))
    assert rec["last_met"] == s.clock_minutes and rec["tier"] == "acquaintance"


# --- nothing iterates the population ---------------------------------------------------------

def test_nothing_is_reckoned_without_an_arrival():
    """Dwarf Fortress's trap: nothing ticks per turn. A batch in which the party did not
    move settles nobody."""
    s, e = _engine()
    _person(s, "a baker", "baker")
    judgement.embody_sought(s, "I talk to the baker.", WORLD)
    assert e.settle_people() == []


def test_the_finder_stays_fast_over_a_large_population():
    """Measured before residency: a missing search over 5,000 records took 66 ms. The
    schedule and the roads must not make the finder a population-wide cost."""
    s, _ = _engine()
    works = ["baker", "smith", "fisher", "merchant", "peddler", "guard"]
    for i in range(5000):
        rec = population.note(s, f"person number {i}", fresh=True)
        rec["life"]["work"] = works[i % len(works)]
        if i % 10 == 0:
            rec["home"] = "elsewhere"
    started = time.perf_counter()
    population.find(s, "a juggler with green gloves", world=WORLD)
    assert time.perf_counter() - started < 3.0


def test_the_rolls_use_only_the_stable_method():
    """Python promises `random()` stable across versions, not `choice` or `randint`
    (docs.python.org, "Notes on Reproducibility"). A traveller's roads must not change
    because the interpreter did."""
    tree = ast.parse(Path("rules/residency.py").read_text(encoding="utf-8"))
    called = {n.func.attr for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not called & {"choice", "choices", "randint", "randrange", "shuffle",
                         "sample", "uniform"}


# --- found live, 2026-09-27 (the `return` script, gemma-4-12B) -----------------------------

def test_the_answer_reads_as_a_sentence():
    """Live: "At this hour The somebody selling bread in the market would be indoors"."""
    s, e = _engine(clock=10 * HOUR)
    rec = population.note(s, "somebody selling bread in the market")
    s.at, s.clock_minutes = "elsewhere", 23 * HOUR
    line = population.seen_line(rec, s, WORLD)
    assert line.startswith("At this hour the one selling bread"), line
    assert "The somebody" not in line and "the somebody" not in line


def test_the_woman_who_sold_me_bread_is_the_one_selling_bread():
    """Live: the irregular past missed her ("sold" was never "sell"), and the plan spawned
    a stranger in her place."""
    s, _ = _engine(clock=10 * HOUR)
    rec = population.note(s, "somebody selling bread in the market")
    found = population.find(s, "the woman who sold me bread", world=WORLD)
    assert found.people and found.people[0]["id"] == rec["id"], found


def test_what_the_prose_says_she_does_is_her_trade():
    """Live: "somebody selling bread" was rolled a gravedigger and "the foreman with the
    tally board" a merchant, who then left town on the roads — the trade now decides
    where a person is, so a misread trade is a person in the wrong place."""
    from rules import lives

    assert lives.occupation_for("somebody selling bread in the market")["id"] == "baker"
    assert lives.occupation_for("the foreman with the tally board")["id"] == "labourer"


def test_her_name_is_not_a_person():
    """Live: "I ask her name." came back as `introduce who="her name"`; the population
    rolled "her name" a life and the prose check made the narrator write her in."""
    s, e = _engine()
    out = e.run(e.validate([{"op": "introduce", "params": {"who": "her name"}}],
                           origin="author:test"))
    assert out.outcomes[0].status == "refused"
    assert not any("name" in r["phrase"] for r in s.population.values())
    assert population.names_a_person("her husband")
    assert population.names_a_person("a hooded figure")
    # Live, the buying run: "I find somewhere to sleep until morning" introduced a
    # person called "somewhere".
    assert not population.names_a_person("somewhere")


def test_somebody_found_in_the_market_is_made_in_the_market():
    """Live: `introduce` the bread seller, `travel` to the market, `say` to her. She was
    made at the crossing the party was leaving, and the question went to the one other
    person standing in the market."""
    s, e = _engine()
    market = next(p for p in e.places() if p.id != s.at)
    out = e.run(e.validate([
        {"op": "introduce", "params": {"who": "somebody selling bread"}},
        {"op": "travel", "params": {"place": market.name}},
        {"op": "say", "params": {"words": "How much for a loaf?", "to": "new1"}},
    ], origin="author:test"))
    her = next(r for r in s.population.values() if "bread" in r["phrase"])
    assert her["ref"] in s.actors and s.people[her["ref"]].at == market.id
    said = next(o for o in out.outcomes if o.op == "say")
    assert said.effects[0]["to"] == her["ref"]


def test_a_question_for_somebody_not_here_goes_to_nobody_else():
    """The live case: the plan's listener exists but stands elsewhere; the one other
    person in the room is not who was asked."""
    s, e = _engine()
    away = population.embody(s, "a woman selling bread", "guildhand", world=WORLD)
    porter = population.embody(s, "a porter", "guildhand", world=WORLD)
    # Validated while she stands here, run after she has gone: what a placeholder bound
    # to somebody left behind looked like from inside the batch.
    planned = e.validate([{"op": "say", "params": {"words": "Where is she?",
                                                  "to": away.ref}}], origin="author:test")
    s.move(away.ref, next(p.id for p in e.places() if p.id != s.at))
    out = e.run(planned)
    said = next(o for o in out.outcomes if o.op == "say")
    assert said.effects[0]["to"] != porter.ref


def test_asking_around_for_her_by_what_she_did_finds_her():
    """Live: "I ask around for the woman who sold me bread" was read as "woman" — the
    capture stopped at "who" — and the plan spawned a stranger."""
    s, e = _engine(clock=10 * HOUR)
    rec = population.note(s, "somebody selling bread in the market")
    s.at = "elsewhere"
    sought = judgement.person_sought("I ask around for the woman who sold me bread.")
    assert sought == "woman who sold me bread"
    found = scope.look_for(WORLD, sought, s, VORMOOR)
    assert found.get("record") == rec["id"] and found["scope"] == scope.ELSEWHERE
    # And a clause nobody answers to still asks for the head.
    assert population.find(s, "the woman who waved at me", world=WORLD).people


def test_going_somewhere_and_looking_for_somebody_looks_for_the_somebody():
    """Live: "I go to the market and look for the bread seller" was read as looking for
    "market". The subject of "look for" is carried by "and", and a place is not a
    person."""
    assert judgement.person_sought(
        "I go to the market and look for the bread seller.") == "bread seller"
    assert judgement.person_sought("I go to the market.") == ""
    assert judgement.person_sought("I draw my sword and approach the guard.") == "guard"
    assert judgement.person_sought("I walk up to the gate guard.") == "gate guard"


def test_asking_after_somebody_known_spawns_nobody_new():
    """Live: "I ask around for the woman who sold me bread" spawned a body called
    "woman" beside the plan's own answer that she was at the north crossing — the older
    `inject_company` door read "ask" as addressing somebody."""
    s, e = _engine(clock=10 * HOUR)
    population.note(s, "somebody selling bread in the market")
    s.at = next(p.id for p in e.places() if p.id != s.at)
    for said in ("I ask around for the woman who sold me bread.",
                 "I talk to the woman selling bread."):
        out = judgement.inject_company([{"op": "narrate_only"}], said, s, WORLD)
        assert not any(i.get("op") == "spawn" for i in out), (said, out)
