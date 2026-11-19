"""Hex travel on the region map (rules/hexes.py, docs/hexcrawl-plan.md, owner 2026-11-18/19).

Every test runs once per export (`worlds`: the standing instruction of 2026-09-28, fixes are
world-agnostic). The road's meeting table is held quiet with `monkeypatch` wherever a test
measures hours or places, because a meeting legitimately stops a move short; the one test
that counts the road's checks counts them through the same patch.
"""
from __future__ import annotations

from collections import Counter

import pytest

from play import atlas as atlas_mod
from rules import hexes, ontheway, states
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene


def _party(world, town=None):
    town = town or world.play["settlements"][0]["id"]
    s = Scene(location_id=town)
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    pc.hp = pc.hp_base = 60
    s.add(pc)
    e = Engine(s, Dice(seed=3), world=world)
    e.place_party("")
    return s, e, pc


def _horse(s, name="Bess"):
    horse = instantiate("horse", scene=s, name=name)
    s.add(horse)
    horse.apply_effect(ActiveEffect(name="travels with you", kind="situation", key="company",
                                    source=f"company:{name}", duration="until-dismissed",
                                    tags=(states.TRAVELS_WITH_YOU,)))
    return horse


def _move(e, to, face=10):
    r = e.run(e.validate([{"op": "hex_move", "actor": "pc", "params": {"hex": list(to)}}]))
    if r.awaiting:
        r = e.resume(face)
    return [o for o in r.outcomes if o.op == "hex_move"][0]


@pytest.fixture
def quiet_road(monkeypatch):
    calls = []

    def road(dice, hours, *a, **k):
        calls.append(hours)
        return None

    monkeypatch.setattr(ontheway, "road", road)
    return calls


def _grid(world, s=None):
    a = atlas_mod.atlas(world)
    return hexes.grid(a, hexes.held_layout(s or Scene(), a))


# --- the grid ----------------------------------------------------------------------------

def test_the_same_world_gives_the_same_board_twice(worlds):
    """The layout is a seeded spring pass; a re-run that moved a town would move every hex
    under a party standing in the wild."""
    a = atlas_mod.atlas(worlds)
    assert hexes.layout(a) == hexes.layout(a)


def test_a_town_added_to_the_export_moves_nothing_already_placed(worlds):
    """A campaign names its world by path and the export can be redone under it. Re-laid
    from scratch with one more town, every town shifts (the springs all pull); the stored
    layout keeps every town where it was and places only the new one."""
    a = atlas_mod.atlas(worlds)
    fewer = dict(a, cities=a["cities"][1:])
    s = Scene()
    first = hexes.held_layout(s, fewer)
    kept = {k: list(v) for k, v in first["pos"].items()}
    again = hexes.held_layout(s, a)
    assert all(again["pos"][k] == v for k, v in kept.items())
    assert a["cities"][0]["id"] in again["pos"]


def test_about_one_hex_in_three_holds_a_site_and_no_kind_is_more_than_half(worlds):
    """The plan's measure (§5, ruling 4): over 300 seeded hexes about one in three has a
    site, and no single kind is more than half of them. Before cave was a grassland kind,
    one nation's sites were 64 ruins of 128. The synthetic world has 265 land hexes in all,
    so the floor is 200: enough for the share to mean something on every export."""
    g = _grid(worlds)
    land = [c for n in g.nations for c in g.region(n) if c["land"] and not c["town"]]
    land = list({(c["q"], c["r"]): c for c in land}.values())
    assert len(land) > 200
    sites = [hexes.site_of(g, c["q"], c["r"]) for c in land]
    found = [x["kind"] for x in sites if x]
    assert 0.25 < len(found) / len(land) < 0.42
    assert max(Counter(found).values()) <= len(found) / 2


def test_the_same_hex_always_holds_the_same_site(worlds):
    """Daggerfall's re-roll farming: a site rolled on entry would differ every visit."""
    g = _grid(worlds)
    for c in g.region(sorted(g.nations)[0])[:200]:
        assert hexes.site_of(g, c["q"], c["r"]) == hexes.site_of(g, c["q"], c["r"])


def test_every_land_hex_is_ground_the_wild_acts_answer_on(worlds):
    """Never nothing (ruling 4): forage, hunt and living off the land read the ground the
    party stands on. A land hex of urban, underground or water ground would refuse them
    all; measured 2026-11-19, river crossings came out as "water" on dry land."""
    g = _grid(worlds)
    for n in g.nations:
        for c in g.region(n):
            if c["land"]:
                assert c["ground"] not in ("urban", "underground", "water", "ruins", "")


# --- moving --------------------------------------------------------------------------------

def test_a_move_costs_the_hours_of_one_hex_and_nothing_else_passes(worlds, quiet_road):
    """Ruling 2: moving is the only time that passes on its own. Ultimate Campaign's hex:
    5 hours on plain, 8 on anything else, plus the walk out of town on the first move."""
    s, e, pc = _party(worlds)
    g = e.hex_world()
    to = e.hex_reach(g)[0]
    _move(e, to)
    assert e.party_hex(g) == to
    t0 = s.clock_minutes
    nxt = next(h for h in e.hex_reach(g) if h != to and not g.cell(*h)["town"])
    out = _move(e, nxt)
    assert out.status == "resolved", out.tell
    assert s.clock_minutes - t0 == 60 * hexes.hours_through(g.cell(*nxt)["ground"])
    assert quiet_road[-1] == hexes.hours_through(g.cell(*nxt)["ground"])


def test_on_foot_a_hex_two_away_is_refused(worlds, quiet_road):
    """Ruling 8: on foot, one hex a move. The refusal names what would make it two."""
    s, e, pc = _party(worlds)
    g = e.hex_world()
    here = e.party_hex(g)
    two = next(h for h in hexes._spiral(here, 2) if hexes.distance(h, here) == 2
               and g.cell(*h)["land"])
    t0 = s.clock_minutes
    out = _move(e, two)
    assert out.status == "refused" and "horse" in out.tell
    assert s.clock_minutes == t0


def test_riding_reaches_two_hexes_in_the_hours_of_one_on_foot(worlds, quiet_road):
    """Ruling 8 with the Q13 ruling (riding halves the time): two hexes ridden cost what
    one walked does, the hex between is entered and checked on the road (one meeting roll
    a hex, UC), and it is NOT searched (ruling 9: the look is made only where you stop)."""
    s, e, pc = _party(worlds)
    _horse(s)
    g = e.hex_world()
    first = next(h for h in e.hex_reach(g) if hexes.distance(h, e.party_hex(g)) == 1
                 and not g.cell(*h)["town"])
    _move(e, first)
    here = e.party_hex(g)
    two = [h for h in e.hex_reach(g) if hexes.distance(h, here) == 2
           and not g.cell(*h)["town"]]
    assert two, "riding offers the hexes two away"
    calls_before = len(quiet_road)
    t0 = s.clock_minutes
    out = _move(e, two[0])
    assert out.status == "resolved", out.tell
    assert e.party_hex(g) == two[0]
    crossed = [eff for eff in out.effects if eff.get("kind") == "hex"]
    assert len(crossed) == 2 and len(quiet_road) - calls_before == 2
    mid = (crossed[0]["q"], crossed[0]["r"])
    spent = sum(-(-hexes.hours_through(g.cell(*h)["ground"]) // 2) for h in (mid, two[0]))
    assert s.clock_minutes - t0 == 60 * spent
    touched = s.hexes["touched"]
    assert "entered" in touched[hexes.key(*mid)]
    # The stop's look reads the six round it, so the hex between is searched only if it is
    # one of them; it always is (it touches the stop), which is the point of checking it was
    # searched AFTER the stop and never by its own look.
    assert touched[hexes.key(*mid)]["searched"] == touched[hexes.key(*two[0])]["searched"]


def test_one_companion_on_foot_and_the_party_walks(worlds, quiet_road):
    """A horse for the PC and none for the companion: the party moves at the walker's
    pace, as a journey does (journey.MOUNTS, one mount a rider)."""
    s, e, pc = _party(worlds)
    _horse(s)
    friend = instantiate("guildhand", scene=s, name="Friend")
    s.add(friend)
    friend.apply_effect(ActiveEffect(name="travels with you", kind="situation", key="company",
                                     source="company:Friend", duration="until-dismissed",
                                     tags=(states.TRAVELS_WITH_YOU,)))
    assert not e.party_rides()
    g = e.hex_world()
    assert all(hexes.distance(h, e.party_hex(g)) == 1 for h in e.hex_reach(g))


def test_open_water_is_not_walked_onto(worlds, quiet_road):
    """Sea hexes wait for ships (plan §3)."""
    s, e, pc = _party(worlds)
    g = e.hex_world()
    here = e.party_hex(g)
    wet = next((h for h in hexes._spiral(here, 8) if not g.cell(*h)["land"]
                and hexes.distance(h, here) == 1), None)
    if wet is None:
        pytest.skip("no sea beside this town")
    assert wet not in e.hex_reach(g)
    assert _move(e, wet).status == "refused"


# --- looking round -------------------------------------------------------------------------

def test_a_stop_searches_its_hex_and_the_six_round_it_whatever_the_roll(worlds, quiet_road):
    """Ruling 10: a hex the Perception check covered looks different on the board, so the
    engine must hold which hexes were read: the stop and its six neighbours, on a natural 1
    as much as a 20."""
    s, e, pc = _party(worlds)
    g = e.hex_world()
    to = e.hex_reach(g)[0]
    _move(e, to, face=1)
    touched = s.hexes["touched"]
    for h in [to] + hexes.neighbours(*to):
        assert "searched" in touched[hexes.key(*h)]


def test_a_low_look_spots_nothing_and_says_so(worlds, quiet_road, monkeypatch):
    """Perception below every DC reveals nothing, and the tell says nothing stood out
    rather than leaving the narrator to fill the silence."""
    s, e, pc = _party(worlds)
    monkeypatch.setattr(pc, "skill_modifiers", lambda skill: [])
    g = e.hex_world()
    out = _move(e, e.hex_reach(g)[0], face=1)
    assert "nothing stands out" in out.tell
    assert not s.hexes.get("spotted")


def test_a_high_look_spots_the_sites_round_it_and_they_stay_spotted(worlds, quiet_road):
    """Ruling 3: entering gives a Perception check that can reveal something in a
    neighbouring hex; spotted is kept, so the board's model stays across a reload."""
    s, e, pc = _party(worlds)
    g = e.hex_world()
    for to in e.hex_reach(g):
        if any(hexes.site_of(g, *h) for h in [to] + hexes.neighbours(*to)):
            break
    else:
        pytest.skip("no site round this town")
    out = _move(e, to, face=20)
    want = {hexes.key(*h) for h in [to] + hexes.neighbours(*to) if hexes.site_of(g, *h)
            and 20 + sum(m.value for m in pc.skill_modifiers("perception"))
            >= hexes.site_of(g, *h)["dc"] + (hexes.OWN_HEX_DC if h == to else 0)}
    assert set(s.hexes["spotted"]) == want
    assert "Looking over the land" in out.tell


# --- explored -------------------------------------------------------------------------------

def test_an_hour_spent_in_an_empty_hex_explores_it_once(worlds, quiet_road):
    """UC: 100 XP an explored hex (+25 difficult ground), once. Explored with no site is
    an hour spent there (owner call 1, answered by default); leaving pays it, and coming
    back and leaving again pays nothing."""
    s, e, pc = _party(worlds)
    g = e.hex_world()
    to = next((h for h in e.hex_reach(g) if hexes.site_of(g, *h) is None
               and not g.cell(*h)["town"]), None)
    if to is None:
        pytest.skip("every neighbour holds a site")
    _move(e, to)
    s.advance(60)
    xp0 = pc.xp
    back = next(h for h in e.hex_reach(g) if not g.cell(*h)["town"])
    out = _move(e, back)
    want = hexes.EXPLORED_XP + (hexes.DIFFICULT_XP if g.cell(*to)["ground"] in hexes.DIFFICULT
                                else 0)
    assert pc.xp - xp0 == want and "exploring" in out.tell
    _move(e, to)
    s.advance(60)
    xp1 = pc.xp
    _move(e, back)
    assert pc.xp == xp1


def test_no_plan_can_move_a_party_across_the_board(worlds):
    """The move is the board's click (CODE_ONLY_OPS), never a plan's op: a model writing
    hex_move would cross twelve miles on its own say."""
    from rules.intents import CODE_ONLY_OPS

    assert {"hex_move", "hex_enter"} <= CODE_ONLY_OPS


def test_a_spotted_site_in_your_hex_opens_through_the_venture_door(worlds, quiet_road):
    """Every site opens a real place (plan §4): the venture door builds it from a seed off
    the hex's own place, so it is the same cave every time, and reaching it explores the
    hex (UC's 100 XP)."""
    s, e, pc = _party(worlds)
    g = e.hex_world()
    to = next((h for h in e.hex_reach(g) if hexes.site_of(g, *h)), None)
    if to is None:
        pytest.skip("no site beside this town")
    _move(e, to, face=20)
    assert hexes.key(*to) in s.hexes["spotted"]
    r = e.run(e.validate([{"op": "hex_enter", "actor": "pc", "params": {}}]))
    out = [o for o in r.outcomes if o.op == "venture"][0]
    assert out.status == "resolved", out.tell
    assert hexes.in_site(s.at, to)
    assert e.party_hex(g) == to
    assert s.hexes["touched"][hexes.key(*to)].get("explored")
