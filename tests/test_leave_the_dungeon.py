"""Leaving a dungeon: the way out on the Site map, and no hex move from below ground.

The owner's asks of 2026-11-26 (C:\\Users\\natha\\pgm-work\\owner-asks-2026-11-26.md), research
in docs/research/2026-11-26-leave-the-dungeon.md. World-agnostic: every test runs on each
export (`worlds`, the standing instruction of 2026-09-28).
"""
from __future__ import annotations

from pathlib import Path

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
                          "dungeon": {"of": head, "role": role, "door": {"state": "open"}}})
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


def test_a_hex_click_from_a_dungeon_room_is_refused_with_the_way_out(worlds, quiet_road,
                                                                      monkeypatch):
    """Owner ask 2026-11-26 A4: a hex click from a dungeon room was narrated as eight hours
    on the road; the clock and the PC never moved. Four clicks from the tower's hall of
    pillars all answered the travel day's refusal instead of where the party stood, and
    with the day fresh (or a forced march) the same click lifted the party straight out
    of the dungeon. Now: refused, the clock and the square unmoved, the tell names the room,
    the site above it and each room of the way out, whether or not the march is pushed."""
    s, e, g, to, head, rooms = _in_a_hex_dungeon(worlds, monkeypatch)
    names = {d["id"]: d["name"] for d in s.founded}
    clock, at = s.clock_minutes, s.at
    s.hexes["day"] = {"hours": 8, "woke": e._woke_at()}   # the owner's spent day
    assert e.travelled_today() == 8
    for march in (False, True):
        r = e.run(e.validate([{"op": "hex_move", "actor": "pc", "params": {
            "hex": list(next(h for h in e.hex_reach(g))), **({"march": True} if march else {})}}]))
        assert not r.awaiting
        out = [o for o in r.outcomes if o.op == "hex_move"][0]
        assert out.status == "refused"
        assert "travelling is done" not in out.tell
        assert names[rooms[-1]] in out.tell and names[head] in out.tell
        assert names[rooms[0]] in out.tell and "Leave first" in out.tell
        assert "~" not in out.tell and ":@" not in out.tell
        assert (s.clock_minutes, s.at, e.party_hex(g)) == (clock, at, to)


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


def test_a_hex_click_from_under_a_town_names_the_place_above(worlds):
    """Under a town (the cellars beneath a place inside the walls) the same refusal names
    the place over the way down, not the town's way out of the walls."""
    sid, host, founded = _town_site(worlds)
    s, e = _with_site(worlds, sid, founded, [host.id] + [f["id"] for f in founded])
    s.at = founded[-1]["id"]
    g = e.hex_world()
    assert g is not None and e.party_hex(g) is not None
    to = next(iter(e.hex_reach(g)))
    out = [o for o in e.run(e.validate([{"op": "hex_move", "actor": "pc", "params": {
        "hex": list(to)}}])).outcomes if o.op == "hex_move"][0]
    assert out.status == "refused" and host.name in out.tell and "the cellars" in out.tell


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
