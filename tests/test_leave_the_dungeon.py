"""Leaving a dungeon: the way out on the Site map, and a hex move from below ground walks it.

The owner's asks of 2026-11-26 (C:\\Users\\natha\\pgm-work\\owner-asks-2026-11-26.md), research
in docs/research/2026-11-26-leave-the-dungeon.md. The owner's later ruling the same day, "Hex
traveling should walk you out from anywhere unless you are in combat or trapped", replaced
the 0.5.2 refusal: the move walks the way up room by room, then makes the journey.
World-agnostic: every test runs on each export (`worlds`, the standing instruction of
2026-09-28).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from play import atlas, places_found
from rules import hexes
from tests.test_atlas import _site_town as _town_site, _with_site
from tests.test_hex_travel import _enter, _move, _party, _site_beside, _site_town, quiet_road  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
BOARD_JS = ROOT / "play" / "static" / "js" / "places-board.js"


def _dungeon_under(s, head: str):
    """Three dungeon rooms beneath a venture's head, as `dungeons.generate` founds them."""
    rooms = [(f"{head}/the-narthex", "the narthex", head, "entrance"),
             (f"{head}/the-narthex/the-hall", "the hall", f"{head}/the-narthex", "room"),
             (f"{head}/the-narthex/the-hall/the-crypt", "the crypt", f"{head}/the-narthex/the-hall",
              "climax")]
    for i, n, par, role in rooms:
        s.founded.append({"id": i, "name": n, "about": f"{n}, dark", "terrain": "ruins",
                          "exits": [], "parent": par, "origin": "dungeon", "kind": "",
                          "dungeon": {"of": head, "role": role, "door": {"state": "open"},
                                      "stocked": True}})
        s.been.append(i)
    return [r[0] for r in rooms]


def _in_a_hex_dungeon(worlds, monkeypatch):
    s, e, pc = _party(worlds, _site_town(worlds))
    monkeypatch.setattr(e, "_inhabit", lambda *a, **k: ([], ""))
    g = e.hex_world()
    to = _site_beside(e, g)
    _move(e, to, face=20)
    assert _enter(e).status == "resolved"
    head = s.at
    rooms = _dungeon_under(s, head)
    s.at = rooms[-1]
    return s, e, g, to, head, rooms


def _hex_click(e, g, march=False):
    r = e.run(e.validate([{"op": "hex_move", "actor": "pc", "params": {
        "hex": list(next(h for h in e.hex_reach(g) if g.cell(*h)["land"])),
        **({"march": True} if march else {})}}]))
    return r, next((o for o in r.outcomes if o.op == "hex_move"), None)


def test_a_hex_click_from_a_dungeon_room_walks_out_and_makes_the_journey(worlds, quiet_road,
                                                                         monkeypatch):
    """Owner ask 2026-11-26 A4: a hex click from a dungeon room was narrated as eight hours
    on the road; the clock and the PC never moved (0.5.1, the tower's hall of pillars). 0.5.2
    refused the click instead; the owner's ruling the same day wants it walked: "Hex
    traveling should walk you out from anywhere unless you are in combat or trapped". Now:
    the party walks up through every room of the way out (named in the tell), then the hex,
    and stands in the next hex with the walk's minutes and the hex's hours on the clock."""
    s, e, g, to, head, rooms = _in_a_hex_dungeon(worlds, monkeypatch)
    names = {d["id"]: d["name"] for d in s.founded}
    clock = s.clock_minutes
    s.hexes.pop("day", None)
    r, out = _hex_click(e, g)
    assert r.awaiting                      # the look's own die, asked before anything moves
    assert (s.clock_minutes, s.at) == (clock, rooms[-1])
    out = [o for o in e.resume(10).outcomes if o.op == "hex_move"][0]
    assert out.status == "resolved", out.tell
    assert e.party_hex(g) != to and not s.underground(s.at)
    assert s.clock_minutes - clock >= 5 * 60 + len(rooms)
    assert names[head] in out.tell and names[rooms[0]] in out.tell
    assert "hours on foot" in out.tell or "hours riding" in out.tell
    assert "~" not in out.tell and ":@" not in out.tell


def test_a_hex_click_from_a_dungeon_on_a_spent_day_is_the_days_refusal_and_moves_nothing(
        worlds, quiet_road, monkeypatch):
    """The other half of A4's defect: with the day's eight hours spent, the click is refused
    for the day, and nothing (not the walk out either) happens before the refusal."""
    s, e, g, to, head, rooms = _in_a_hex_dungeon(worlds, monkeypatch)
    clock = s.clock_minutes
    s.hexes["day"] = {"hours": 8, "woke": e._woke_at()}   # the owner's spent day
    r, out = _hex_click(e, g)
    assert not r.awaiting and out.status == "refused" and "travelling is done" in out.tell
    assert (s.clock_minutes, s.at, e.party_hex(g)) == (clock, rooms[-1], to)


def test_a_hex_click_in_a_fight_below_ground_is_refused(worlds, quiet_road, monkeypatch):
    """In combat the ruling's first exception: refused, no die asked, nothing moved."""
    s, e, g, to, head, rooms = _in_a_hex_dungeon(worlds, monkeypatch)
    clock = s.clock_minutes
    s.initiative, s.turn = [("pc", 20)], 0
    r, out = _hex_click(e, g)
    assert not r.awaiting and out.status == "refused" and "fight" in out.tell
    assert (s.clock_minutes, s.at) == (clock, rooms[-1])


@pytest.mark.parametrize("condition", ["grappled", "entangled", "paralyzed", "unconscious"])
def test_a_hex_click_while_held_fast_is_refused_naming_it(worlds, quiet_road, monkeypatch,
                                                          condition):
    """The ruling's second exception, trapped, read off the tag families (`state.held`,
    `state.unable`, `state.down`), never the condition's string: refused with the
    condition named and what to do first, no die asked, nothing moved."""
    s, e, g, to, head, rooms = _in_a_hex_dungeon(worlds, monkeypatch)
    clock = s.clock_minutes
    s.pc().add_condition(condition, source="author:test")
    r, out = _hex_click(e, g)
    assert not r.awaiting and out.status == "refused"
    assert condition in out.tell and "choose the hex again" in out.tell
    assert (s.clock_minutes, s.at) == (clock, rooms[-1])


def test_a_hex_click_with_a_shut_door_on_the_way_up_is_refused_naming_it(worlds, quiet_road,
                                                                         monkeypatch):
    """Trapped by the way, not the body: a door shut on the way up (the sealing trap's
    fallen portcullis) is refused before the die, naming the door and how to open it,
    rather than walked through."""
    s, e, g, to, head, rooms = _in_a_hex_dungeon(worlds, monkeypatch)
    hall = next(d for d in s.founded if d["id"] == rooms[1])
    hall["dungeon"]["door"] = {"name": "the fallen portcullis", "state": "stuck", "force": 25}
    clock = s.clock_minutes
    r, out = _hex_click(e, g)
    assert not r.awaiting and out.status == "refused"
    assert "portcullis" in out.tell and "Strength" in out.tell
    assert (s.clock_minutes, s.at) == (clock, rooms[-1])


def test_a_hex_click_with_no_known_way_up_is_refused(worlds, quiet_road, monkeypatch):
    """No route the engine knows: refused, never `travel`'s floor of one direct step, which
    is how 0.5.1 lifted the party straight out of the dungeon."""
    from rules import places as places_mod

    s, e, g, to, head, rooms = _in_a_hex_dungeon(worlds, monkeypatch)
    monkeypatch.setattr(places_mod, "route", lambda *a, **k: ())
    clock = s.clock_minutes
    r, out = _hex_click(e, g)
    assert not r.awaiting and out.status == "refused" and "way up" in out.tell
    assert (s.clock_minutes, s.at) == (clock, rooms[-1])


def test_a_walk_out_stopped_on_the_way_makes_no_journey(worlds, quiet_road, monkeypatch):
    """A foe lying in wait in a room on the way up stops the walk there; the journey never
    starts from inside the dungeon (before, a cut-short walk out went on across hexes)."""
    s, e, g, to, head, rooms = _in_a_hex_dungeon(worlds, monkeypatch)
    monkeypatch.setattr(e, "_lies_in_wait", lambda pid: ["a foe"] if pid == rooms[0] else [])
    s.hexes.pop("day", None)
    r, out = _hex_click(e, g)
    out = [o for o in e.resume(10).outcomes if o.op == "hex_move"][0]
    assert s.at == rooms[0] and e.party_hex(g) == to
    assert "walk out stops" in out.tell and "hours on foot" not in out.tell


def test_a_hex_click_from_the_site_on_the_surface_still_walks_out(worlds, quiet_road,
                                                                   monkeypatch):
    """The line A4 draws: standing in the tower itself (a site on the surface, no way down
    taken), a hex click walks out of it as playtest 2026-11-20 #4 built it."""
    s, e, pc = _party(worlds, _site_town(worlds))
    monkeypatch.setattr(e, "_inhabit", lambda *a, **k: ([], ""))
    g = e.hex_world()
    to = _site_beside(e, g)
    _move(e, to, face=20)
    assert _enter(e).status == "resolved"
    other = next(h for h in e.hex_reach(g) if g.cell(*h)["land"])
    assert _move(e, other).status == "resolved"
    assert e.party_hex(g) == other


def test_a_hex_click_from_under_a_town_walks_up_and_out_of_the_walls(worlds, quiet_road):
    """Under a town (the cellars beneath a place inside the walls), 0.5.2 refused naming the
    place above; by the ruling the move walks up through it and out of the town's way out,
    then the hex."""
    sid, host, founded = _town_site(worlds)
    s, e = _with_site(worlds, sid, founded, [host.id] + [f["id"] for f in founded])
    s.at = founded[-1]["id"]
    g = e.hex_world()
    assert g is not None and e.party_hex(g) is not None
    here = e.party_hex(g)
    s.hexes.pop("day", None)
    r, out = _hex_click(e, g)
    if r.awaiting:
        out = [o for o in e.resume(10).outcomes if o.op == "hex_move"][0]
    assert out.status == "resolved", out.tell
    assert e.party_hex(g) != here and not s.underground(s.at)
    assert host.name in out.tell


def test_the_site_map_draws_the_way_out_and_walks_to_it(worlds, quiet_road, monkeypatch):
    """Owner ask 2026-11-26 A3: "add a representative room for the original map of the hex
    ... so that I can actually move back out". The Site map showed the tower's rooms and
    nothing for the hills it stands on, so no press on it could leave. Now the site carries
    `out`, its host, seated a column before the way in; the chart's Walk there reaches it from
    the deepest room through the engine's own ways; and the board draws and picks it."""
    s, e, g, to, head, rooms = _in_a_hex_dungeon(worlds, monkeypatch)
    site = next(x for x in atlas.known_places(e, worlds)["sites"] if x["id"] == head)
    host = site["host"]
    assert hexes.parse_place(host) == to and not hexes.in_site(host)
    root_at = next(r["at"] for r in site["rooms"] if r["id"] == head)
    assert site["out"]["id"] == host and site["out"]["at"] == [root_at[0] - 1, root_at[1]]
    assert host not in {r["id"] for r in site["rooms"]}   # rooms stay the site's own
    node = next(n for n in places_found.chart(e, worlds)["nodes"] if n["id"] == host)
    assert node["walk"] and node["walk"]["legs"][-1]["to"] == host
    src = BOARD_JS.read_text(encoding="utf-8")
    site_js = src[src.index("function siteMap("):src.index("function downArrow(")]
    assert "st.out" in site_js and "pickable: true" in site_js


def test_a_sleeper_is_refused_the_next_hex(worlds, quiet_road, monkeypatch):
    """Found by this lane's suite: a body the road's toll had put to sleep (`unconscious`,
    `survival._fall_asleep`) was walked on eight hours a click, hex after hex. Asleep is
    trapped by the ruling: refused, named as sleep, with rest as the way on."""
    from rules import survival

    s, e, g, to, head, rooms = _in_a_hex_dungeon(worlds, monkeypatch)
    pc = s.pc()
    pc.add_condition("unconscious", source=survival.SLEEP_SOURCE)
    assert survival.asleep(pc) is not None
    r, out = _hex_click(e, g)
    assert not r.awaiting and out.status == "refused"
    assert "asleep" in out.tell and "rest first" in out.tell
