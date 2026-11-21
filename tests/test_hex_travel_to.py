"""Click-to-travel on the region map (owner decision 2026-11-21, research note
docs/research/2026-11-21-hex-travel-to.md).

Since the rescale (fix/hex-scale) a hex is still 12 miles but places are more hexes apart:
the owner's ruins lie three hexes out of Branford, and on 0.4.8 that walk took three
clicks (riding, two). A seen hex further than one move is now a destination, walked one
move at a time through `_op_hex_move`'s own per-hex step, and stopped short by a meeting,
a fight, a new sighting or the end of the travel day. Every test runs once per export.
"""
from __future__ import annotations

import pytest

from rules import hexes, journey, ontheway
from tests.test_hex_travel import _horse, _move, _party, quiet_road  # noqa: F401


def _far(e, g, n=3):
    """A land hex n out whose way over land is n hexes, none of them a town."""
    here = e.party_hex(g)
    for h in hexes._spiral(here, n):
        if hexes.distance(h, here) != n:
            continue
        route = hexes.land_route(g, here, h)
        if len(route) == n and not any(g.cell(*x)["town"] for x in route):
            return h, route
    pytest.skip("no clear land three hexes out of this town")


@pytest.fixture
def long_day(monkeypatch):
    monkeypatch.setattr(journey, "HOURS_PER_DAY", 1000)


def test_a_far_hex_is_walked_in_one_click_every_hex_a_real_step(worlds, quiet_road, long_day,
                                                                monkeypatch):
    """The ruins three hexes out took three clicks on 0.4.8. One click now walks all
    three, and every hex pays what a one-hex move pays: its own road check (3 checks, not
    1), its hours on the clock, entered on the board, and its own look (searched)."""
    s, e, pc = _party(worlds)
    g = e.hex_world()
    to, route = _far(e, g)
    # Nothing to see: a first sighting would (rightly) stop the walk early.
    monkeypatch.setattr(hexes, "site_of", lambda *a, **k: None)
    out = _move(e, to, face=1)
    assert out.status == "resolved", out.tell
    assert e.party_hex(g) == to
    crossed = [(x["q"], x["r"]) for x in out.effects if x.get("kind") == "hex"]
    assert crossed == route
    assert quiet_road[-3:] == [hexes.hours_through(g.cell(*h)["ground"]) for h in route]
    touched = s.hexes["touched"]
    for h in route:
        assert "entered" in touched[hexes.key(*h)] and "searched" in touched[hexes.key(*h)]
    assert out.tell.count("Looking over the land") == 3
    assert len(out.rolls) == 3
    looks = [x for x in out.effects if x.get("kind") == "hex_look"]
    assert [(x["q"], x["r"]) for x in looks] == route
    assert all(x["skill"] == "perception" and x["rolled"]["faces"] and "found" in x
               for x in looks)
    assert "The walk stops" not in out.tell


def test_riding_walks_the_same_hexes_at_half_the_hours(worlds, quiet_road, long_day,
                                                      monkeypatch):
    """Riding halves each hex's hours through the journey's own rule, and looks only where
    each two-hex move ends (ruling 9): three hexes ridden are two moves, two looks."""
    s, e, pc = _party(worlds)
    _horse(s)
    g = e.hex_world()
    to, route = _far(e, g)
    monkeypatch.setattr(hexes, "site_of", lambda *a, **k: None)
    out = _move(e, to, face=1)
    assert e.party_hex(g) == to, out.tell
    ridden = [x["hours"] for x in out.effects if x.get("kind") == "hex"]
    assert ridden == [journey.mounted_hours(hexes.hours_through(g.cell(*h)["ground"]),
                                            "ride")[0] for h in route]
    assert out.tell.count("Looking over the land") == 2


def test_the_travel_day_ends_the_walk_and_says_so(worlds, quiet_road, monkeypatch):
    """CRB overland: eight hours of travel a day (`journey.HOURS_PER_DAY`). A walk three
    hexes long stops when the day's hours are walked, on that hex, and the tell names why
    and where; the player chooses what comes next."""
    s, e, pc = _party(worlds)
    monkeypatch.setattr(pc, "skill_modifiers", lambda skill: [])
    g = e.hex_world()
    to, route = _far(e, g)
    out = _move(e, to, face=1, fresh_day=False)
    walked = [x["hours"] for x in out.effects if x.get("kind") == "hex"]
    assert sum(walked) >= journey.HOURS_PER_DAY and sum(walked[:-1]) < journey.HOURS_PER_DAY
    assert e.party_hex(g) == route[len(walked) - 1] != to
    assert "the day's travelling is done" in out.tell
    assert [x for x in out.effects if x.get("kind") == "hex_walk"][0]["why"] == "day"


def test_a_meeting_on_the_way_stops_the_walk_on_its_hex(worlds, long_day, monkeypatch):
    """A meeting stops the walk where it happens (plan §3), a peaceful one too: the second
    hex's road check meets a toll-keeper, and the party stands on the second hex."""
    s, e, pc = _party(worlds)
    calls = []

    def road(dice, hours, *a, **k):
        calls.append(hours)
        if len(calls) == 3:   # the way out of town, then hex one, then hex two
            return ontheway.Meeting(kind="toll", roll=50, words=("toll-keeper", "warden"),
                                    count=1, template="guildhand", price_cp=20)
        return None

    monkeypatch.setattr(ontheway, "road", road)
    g = e.hex_world()
    to, route = _far(e, g)
    out = _move(e, to, face=1)
    crossed = [(x["q"], x["r"]) for x in out.effects if x.get("kind") == "hex"]
    assert e.party_hex(g) == crossed[-1] != to, out.tell
    assert "someone met on the way" in out.tell


def test_a_new_sighting_stops_the_walk(worlds, quiet_road, long_day, monkeypatch):
    """Something new to head for is the player's call (Goblin Punch: rumours of what lies
    ahead make direction matter): a tower first seen from hex one stops the walk there."""
    s, e, pc = _party(worlds)
    g = e.hex_world()
    to, route = _far(e, g)
    tower = next(h for h in hexes.neighbours(*route[0])
                 if hexes.distance(h, e.party_hex(g)) == 2 and h not in route)
    monkeypatch.setattr(hexes, "site_of", lambda g_, q, r, kept=None:
                        {"kind": "tower", "dc": 0} if (q, r) == tower else None)
    out = _move(e, to, face=20)
    assert e.party_hex(g) == route[0], out.tell
    assert "something new is in sight" in out.tell
    assert hexes.key(*tower) in s.hexes["spotted"]


def test_the_way_goes_round_water_never_through_it():
    """Sea hexes wait for ships: where the straight hex line crosses water, the route walks
    round it on land; with no land way at all, there is no route. On a stub grid, since
    after the rescale no export has sea that close to a town (measured: skipped in all
    three)."""
    class Stub:
        def __init__(self, wet):
            self.wet = wet

        def cell(self, q, r):
            land = (q, r) not in self.wet
            return {"land": land, "ground": "grassland" if land else "water"}

    a, b = (0, 0), (4, 0)
    wall = {(2, r) for r in range(-1, 2)}
    route = hexes.land_route(Stub(wall), a, b)
    assert route and route[-1] == b
    assert not set(route) & wall
    assert all(hexes.distance(x, y) == 1 for x, y in zip([a] + route, route))
    moat = {h for h in hexes._spiral(b, 1) if h != b}
    assert hexes.land_route(Stub(moat), a, b) == []
    # Open ground walks the straight line the board draws.
    assert hexes.land_route(Stub(set()), a, b) == [hexes.along(a, b, k / 4) for k in (1, 2, 3, 4)]


def test_a_walk_stops_when_the_body_gives_out(worlds, quiet_road, long_day, monkeypatch):
    """Live 2026-11-21 on the owner's save: a third walk through the night said "they
    could not keep going" and the click walked on. A failed save against sleep now stops
    the walk on that hex."""
    from rules import survival

    s, e, pc = _party(worlds)
    g = e.hex_world()
    to, route = _far(e, g)
    monkeypatch.setattr(hexes, "site_of", lambda *a, **k: None)
    real = survival.pass_hours

    def spent(*a, **k):
        toll = real(*a, **k)
        toll.collapsed = True
        return toll

    monkeypatch.setattr(survival, "pass_hours", spent)
    out = _move(e, to, face=1)
    assert e.party_hex(g) == route[0], out.tell
    assert "could not keep going" in out.tell


def test_the_map_caption_names_a_hex_site_never_its_id():
    """0.4.8 hit test on the owner's save: the Map tab's heading read "The ground · @hex
    m113 76/the ruins", a hex id humanised onto the page (refs never on the page). The
    caption is the minted place's own name; an id nothing minted still loses the grammar."""
    from play.views import _where_the_ground_is
    from rules import places
    from rules.engine import Scene

    site = "fffcb34e546e~ruins:@hex-m52-35/the-ruins"
    s = Scene(location_id="fffcb34e546e")
    s.at = site
    s.founded = [{"id": "fffcb34e546e~forest:@hex-m52-35", "name": "the forest 12 miles east "
                  "of Branford", "parent": ""},
                 {"id": site, "name": "the ruins", "parent": "fffcb34e546e~forest:@hex-m52-35"}]
    name, _ = _where_the_ground_is(s)
    assert name == "the ruins"
    assert places.said_name("fffcb34e546e~forest:@hex-m52-35") == "the forest"
    assert places.said_name(site + "/the-gate") == "the gate"
    for pid in (site, "x~forest:@hex-m52-35", site + "/the-gate"):
        assert "@hex" not in places.said_name(pid) and "m52" not in places.said_name(pid)


# --- the travel day and the forced march (owner ruling 2026-11-21: "add forced march") ---

def _walk_until_day_spent(e, g, to):
    for _ in range(4):
        if e.travelled_today() >= journey.HOURS_PER_DAY:
            return
        _move(e, to, face=1, fresh_day=False)
    raise AssertionError("never spent the day")


def test_a_second_click_cannot_walk_a_second_day_unasked(worlds, quiet_road, monkeypatch):
    """The per-click loophole: two clicks walked 16 hours with no Constitution check,
    because each click had its own eight hours. The day is now the day since the last
    rest; with it spent, a click is refused, says it would be a forced march, and spends
    nothing."""
    s, e, pc = _party(worlds)
    monkeypatch.setattr(hexes, "site_of", lambda *a, **k: None)
    g = e.hex_world()
    to, route = _far(e, g)
    _walk_until_day_spent(e, g, to)
    if e.party_hex(g) == to:
        pytest.skip("the day reached the destination")
    t0, at = s.clock_minutes, e.party_hex(g)
    out = _move(e, to, face=1, fresh_day=False)
    assert out.status == "refused" and "forced march" in out.tell
    assert s.clock_minutes == t0 and e.party_hex(g) == at


def test_pushing_on_is_a_forced_march_with_its_checks(worlds, quiet_road, monkeypatch):
    """Chosen (`march`), the walk goes on, and every hour past eight is a Constitution
    check at DC 10, +2 an hour; the hours keep counting.

    The checks live in the effects and the turn's rolls, never the tell: the owner's
    screenshot (2026-11-21) showed five "Shadow Constitution 15 vs DC 10, holds up" lines
    in the story, and the ruling put every check in the GM's section. The tell carries one
    sentence for the march (`march_said`), with no figure in it."""
    s, e, pc = _party(worlds)
    monkeypatch.setattr(hexes, "site_of", lambda *a, **k: None)
    g = e.hex_world()
    to, route = _far(e, g)
    _walk_until_day_spent(e, g, to)
    if e.party_hex(g) == to:
        pytest.skip("the day reached the destination")
    before = e.travelled_today()
    r = e.run(e.validate([{"op": "hex_move", "actor": "pc",
                           "params": {"hex": list(to), "march": True}}]))
    out = [o for o in (e.resume(1) if r.awaiting else r).outcomes if o.op == "hex_move"][0]
    assert out.status == "resolved", out.tell
    assert e.travelled_today() > before
    assert "a forced march" in out.tell.lower()
    assert "vs DC" not in out.tell and "Constitution" not in out.tell
    # As data, not English (owner ruling 2026-11-21: the numbers go to the GM's section,
    # routed by structure): one record a check, with its roll and its toll.
    marched = [x for x in out.effects if x.get("kind") == "forced_march"]
    dcs = [x["dc"] for x in marched]
    assert marched
    # Hour n past eight is DC 10 + 2(n-1): the first hour marched here is hour before+1.
    assert min(dcs) == 10 + 2 * (max(before, journey.HOURS_PER_DAY) + 1
                                 - journey.HOURS_PER_DAY - 1)
    # Each walker's check is a roll in the turn's dice log, the Rolls panel's source.
    checks = [x for x in marched if not x["mount"]]
    assert len([r for r in out.rolls if "forced march" in r.label.lower()]) == len(checks)
    for x in marched:
        assert x["ability"] == "con" and x["who"] and isinstance(x["passed"], bool)
        assert x["hour"] > journey.HOURS_PER_DAY and x["rolled"]["faces"]
        assert {"nonlethal", "lethal", "conditions"} <= set(x)


def test_a_failed_march_check_hurts_and_tires_and_mending_lifts_the_fatigue(worlds):
    """CRB Forced March: a failure is 1d6 non-lethal and fatigued, and "eliminating the
    nonlethal damage also eliminates the fatigue". Through the actor's own doors: the
    fatigue is a condition effect (law 2) and the check a real d20 with its modifiers."""
    from rules import survival
    from rules.dice import Dice

    s, e, pc = _party(worlds)
    for _ in range(50):
        toll, said = survival.forced_march(pc, 30, Dice(seed=1))   # DC 68: always fails
        if toll.nonlethal:
            break
    assert pc.nonlethal > 0 and pc.has_state("state.impaired.fatigued"), said
    assert "fails" in said and "vs DC 68" in said
    pc.heal_nonlethal(pc.nonlethal)
    assert not pc.has_state("state.impaired.fatigued")


def test_a_mount_fails_its_march_check_and_takes_it_as_wounds(worlds):
    """CRB Mounted Movement: a mount "can be ridden in a forced march, but its
    Constitution checks automatically fail, and the damage it takes is lethal"."""
    from rules import survival
    from rules.dice import Dice

    s, e, pc = _party(worlds)
    horse = _horse(s)
    hp = horse.hp
    toll, said = survival.forced_march(horse, 1, Dice(seed=2), mount=True)
    assert not toll.checks and horse.hp < hp and toll.lethal == hp - horse.hp
    assert horse.nonlethal == 0
    # Ridden through the walk, the engine lands the mount's fatigue (the gallop's rule).
    s.hexes["day"] = {"woke": e._woke_at(), "hours": 8}
    _lines, fx = e._forced_march(8, 1, rides=True)
    assert horse.has_state("state.impaired.fatigued")
    assert any(x["mount"] and not x["passed"] and x["lethal"] for x in fx)


def test_a_night_s_rest_starts_a_new_travel_day(worlds, quiet_road, monkeypatch):
    """Today is since the last rest of eight hours or more: the awake clock, reset by
    sleep, is the one clock read (no second clock). A two-hour nap is not a new day."""
    s, e, pc = _party(worlds)
    s.hexes["day"] = {"woke": e._woke_at(), "hours": 9}
    assert e.travelled_today() == 9
    s.clock_minutes += 120
    assert e.travelled_today() == 9            # a nap: awake clock paused, clock ran
    s.clock_minutes += 8 * 60
    pc.awake_minutes = 0                       # slept the night
    assert e.travelled_today() == 0
