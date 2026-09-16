"""The three doors a place comes in by, and the one derivation they all feed.

"places are meant to be able to be created right? why did it not make a docks?" and
"can we not use similar tactics to form the back alleys by the markets vs the back alley
by the library or what if i choose to explore the sewers or i go outside the city to a
cave." 2026-09-05. Measured before this: Vyrakon's paragraphs name its docks and a
guildhall, and `home_set` offered six fixed spots with neither; "I set up at Marra's
house" resolved to nothing; "I go down into the sewers" was a `travel` to a place that
did not exist, refused with the six fixed spots as the whole world.

The doors (docs/place-doors.md): the world's own words imply a spot; the player founds
one, with an owner; ground goes into, seeded so it is the same ground next time. All of
it lands in `Scene.founded` and is read back through `places.for_scene` — no second
store of where things are (docs/places-8b-plan.md).
"""
from __future__ import annotations

from gm import judgement
from play.campaign import Campaign
from rules import places
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

VYRAKON = "5bbd0c40345f"
WORLD = loader.load_cached("fixtures/pangrella-campaign.json")


def _room(seed=3):
    s = Scene(location_id=VYRAKON)
    s.add(load_pc("fixtures/pc-kesst.json"))
    return s, Engine(s, Dice(seed=seed), world=WORLD)


def _run(engine, op, params, actor="pc"):
    intents = engine.validate([{"op": op, "actor": actor, "because": "t", "params": params}],
                              origin="author:test")
    return engine.run(intents).outcomes[-1]


def _refused(out) -> bool:
    """A refusal is a printable Outcome with nothing done (`Engine._refuse`)."""
    return out.effects == []


# --- door one: the world's own words ------------------------------------------------------

def test_a_settlement_whose_paragraphs_name_its_docks_has_docks():
    """Vyrakon's fixture facts name its guilds and its ore; the four-spot settlement
    set offered neither a guildhall nor a mine head, so the player's "I go up to the
    mine" was refused with 'from here you can reach the market, the gate, ...'. (The
    live world's Vyrakon has docks in its paragraphs; this fixture's does not, and a
    docks it does not mention is exactly what must not be added.)"""
    # Vyrakon ships authored places now (schema 1.3), and an authored list replaces door
    # one entirely — so this reads the cue table and the GENERATED set, which is what the
    # defect was about. A settlement the world wrote places for is covered by
    # `tests/test_authored_places.py`.
    ent = WORLD.get(VYRAKON)
    earned = [spot for spot, _about in places.implied_spots(ent)]
    assert "the mine head" in earned and "the guildhall" in earned
    assert "the docks" not in earned, "a docks its paragraphs do not mention"

    class AsIfUnauthored:
        id, name, kind = ent.id, ent.name, ent.kind
        scale, facts = ent.scale, ent.facts
        prose = " ".join(str(x) for sec in (ent.sections or [])
                         for x in (sec.get("paragraphs") or []))
        places = []

    names = [p.name for p in places.home_set(AsIfUnauthored())]
    assert "the mine head" in names and "the guildhall" in names, names
    assert "the docks" not in names
    # Ceilinged by the settlement's own scale. The earned places are folded into that
    # budget rather than added on top of it — a port town spends a slot on its docks
    # rather than growing one — so a settlement with earned places holds exactly as many
    # rooms as one without.
    assert len(names) == places.PLACES_BY_SCALE[places.scale_of(ent)], names
    # And they are on the map: reachable, with the way back.
    by_id = {p.id: p for p in places.home_set(AsIfUnauthored())}
    hall = next(p for p in by_id.values() if p.name == "the guildhall")
    assert any(hall.id in by_id[x].exits for x in hall.exits if x in by_id)

def test_the_same_alley_off_two_parents_is_two_places():
    """'the back alley by the market vs the back alley by the library': the child id
    hangs off the parent's id, so the two are different places with different ids,
    and neither collides with the other's."""
    known = places.home_set(WORLD.get(VYRAKON))
    market = places.find(known, "the market")
    temple = places.find(known, "the temple")
    a = places.mint(market, "the back alley", "", origin="found")
    b = places.mint(temple, "the back alley", "", origin="found")
    assert a.id != b.id
    assert a.id.startswith(market.id + "/") and b.id.startswith(temple.id + "/")
    assert a.parent == market.id and b.parent == temple.id


def test_founding_a_base_grants_the_owner_a_tag_through_the_one_applicator():
    """The friend's house becomes a base; the friend holds it. The holding is an
    `ActiveEffect` with `holds.place.<slug>`, source `place:<id>` — remove it and the
    tag evaporates, like everything else (law two)."""
    s, engine = _room()
    marra = s.add(instantiate("guildhand", s, name="Marra"))
    npc1 = marra.ref
    out = _run(engine, "found", {"name": "Marra's house", "owner": npc1})
    assert not _refused(out), out.tell
    assert marra.has_state("holds.place")
    made = places.find(engine.places(), "Marra's house")
    assert made is not None
    assert marra.has_state("holds.place." + made.id.rsplit("/", 1)[-1])
    eff = next(e for e in marra.effects if e.source.startswith("place:"))
    assert eff.tags and all(t.startswith("holds.place.") for t in eff.tags)
    marra.remove_effects(name=eff.name)
    assert not marra.has_state("holds.place")
    # It is a place now, off where the party stood, and the party can travel there.
    assert made.parent == engine.here().id and made.owner == npc1
    gone = _run(engine, "travel", {"place": "Marra's house"})
    assert not _refused(gone), gone.tell
    assert s.at == made.id
    # And a situation card so what is done to it accumulates.
    assert any(dict(c).get("place") == made.id for c in s.cards)


def test_founding_refuses_an_unknown_owner_and_a_second_of_the_same_name():
    s, engine = _room()
    out = _run(engine, "found", {"name": "the hideout", "owner": "npc9"})
    assert _refused(out) and "npc9" in out.tell
    assert not _refused(_run(engine, "found", {"name": "the hideout"}))
    again = _run(engine, "found", {"name": "the hideout"})
    assert _refused(again) and "already" in again.tell


def test_a_parent_holds_only_so_many_children():
    s, engine = _room()
    for n in range(places.MOST_CHILDREN):
        assert not _refused(_run(engine, "found", {"name": f"room number {n + 1}"}))
    over = _run(engine, "found", {"name": "one room too many"})
    assert _refused(over) and "as many" in over.tell


def test_founded_places_survive_the_save():
    s, engine = _room()
    _run(engine, "found", {"name": "the hideout"})
    c = Campaign(id="t-place-doors", world_source="fixtures/pangrella-campaign.json", scene=s)
    back = Campaign.load(c.save())
    assert back.scene.founded == s.founded
    assert places.find(Engine(back.scene, Dice(seed=1)).places(), "the hideout") is not None


# --- door three: ground gone into --------------------------------------------------------------

def test_the_sewers_under_the_market_are_the_same_sewers_next_time():
    """Seeded off the parent's id (the roguelike answer): the same stairs lead to the
    same tunnels with the same spots, and going down twice mints nothing the second
    time."""
    known = places.home_set(WORLD.get(VYRAKON))
    market = places.find(known, "the market")
    one = places.venture_set(market, "sewers")
    two = places.venture_set(market, "sewers")
    assert [p.id for p in one] == [p.id for p in two]
    assert [p.name for p in one] == [p.name for p in two]
    assert one[0].terrain == places.VENTURES["sewers"]["terrain"]
    assert all(p.parent == one[0].id for p in one[1:])


def test_venturing_moves_the_party_and_costs_the_hours():
    s, engine = _room(seed=5)
    pc = s.pc()
    before = s.clock_minutes if hasattr(s, "clock_minutes") else s.minutes
    out = _run(engine, "venture", {"kind": "cave"})
    assert not _refused(out), out.tell
    assert pc.at.startswith(s.location_id) and "cave" in s.at
    assert s.at == pc.at
    after = s.clock_minutes if hasattr(s, "clock_minutes") else s.minutes
    assert after - before >= places.VENTURES["cave"]["hours"] * 60
    # The second time is the same cave, and mints nothing more.
    n = len(s.founded)
    _run(engine, "travel", {"place": "the market"})
    again = _run(engine, "venture", {"kind": "cave"})
    assert not _refused(again) and len(s.founded) == n
    assert "as before" in again.tell


def test_an_unknown_kind_of_ground_is_refused_with_the_kinds_named():
    s, engine = _room()
    out = _run(engine, "venture", {"kind": "moon"})
    assert _refused(out) and "sewers" in out.tell


# --- what the player's words declare -----------------------------------------------------------

def test_setting_up_at_a_friends_house_is_a_found_with_that_friend_as_owner():
    s, engine = _room()
    marra = s.add(instantiate("guildhand", s, name="Marra Vell"))
    raw = judgement.inject_found([], "We set up our base at Marra's house.", s)
    assert raw and raw[-1]["op"] == "found"
    assert raw[-1]["params"]["name"] == "Marra's house"
    assert raw[-1]["params"]["owner"] == marra.ref
    # A question is not a declaration.
    assert judgement.inject_found([], "Could we set up a base at Marra's house?", s) == []


def test_going_into_the_sewers_by_the_market_is_a_venture_off_the_market():
    s, engine = _room()
    raw = judgement.inject_venture([{"op": "travel", "actor": "pc", "params": {"place": "the sewers"}}],
                                   "I go down into the sewers behind the market.", s)
    assert [r["op"] for r in raw] == ["venture"]
    assert raw[0]["params"] == {"kind": "sewers", "parent": "market"}
    raw = judgement.inject_venture([], "I head out to the caves in the hills.", s)
    assert raw and raw[-1]["params"]["kind"] == "cave"
    assert judgement.inject_venture([], "I wonder what is in the sewers.", s) == []
