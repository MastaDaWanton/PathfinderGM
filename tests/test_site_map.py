"""The Site map: a dungeon's rooms as a dollhouse (phase 4 of docs/place-map-v2-build-plan.md).

The board (play/static/js/places-board.js, `siteMap`) draws a site from `scene.known_places`
(play/atlas.py) and walks to a room by the town chart's own legs (play/places_found.py). What
these hold, each a defect seen while building it:

- a room not yet seen is never drawn: it never crosses to the page (test_atlas.py holds the
  fog); here, the seat of every room sent is dealt over the whole site, because the mock laid
  the site out over the rooms found, so a room found beside another pushed it along its row;
- a room only seen is a chalk outline and has no `about`, `role` or `door` (the board builds
  the box only for a room stood in);
- the route to a room goes through rooms entered only: Walk there on the Site is the town's
  Walk there, and a walk through a room only seen would be a walk into the unknown.

World-agnostic (the standing instruction of 2026-09-28): each runs on Aurvantis, Pangrella and
the synthetic world.
"""
from __future__ import annotations

from pathlib import Path

from play import atlas, places_found
from tests.test_atlas import _site_town, _with_site

ROOT = Path(__file__).resolve().parent.parent
BOARD_JS = ROOT / "play" / "static" / "js" / "places-board.js"
TAB_JS = ROOT / "play" / "static" / "js" / "table" / "16-tab-map.js"


def _site(e, worlds, root):
    return next(x for x in atlas.known_places(e, worlds)["sites"] if x["id"] == root)


def test_finding_a_room_moves_none_already_drawn(worlds):
    """Stood in the way in, then one room deeper: every room drawn the first time keeps its
    seat when the next is found, and a room's column is its depth below the way in."""
    sid, host, founded = _site_town(worlds)
    root, vault, deep = (f["id"] for f in founded)
    s, e = _with_site(worlds, sid, founded, [host.id, root])
    first = {r["id"]: r["at"] for r in _site(e, worlds, root)["rooms"]}
    s.been.append(vault)
    later = {r["id"]: r["at"] for r in _site(e, worlds, root)["rooms"]}
    assert set(first) == {root, vault} and set(later) == {root, vault, deep}
    assert all(later[i] == at for i, at in first.items())
    assert [later[i][0] for i in (root, vault, deep)] == [0, 1, 2]


def test_a_room_only_seen_is_an_outline_with_nothing_of_its_inside(worlds):
    """The board builds a room's box, its altar and its torch only for a room stood in; one only
    seen is sent with its name and seat alone."""
    sid, host, founded = _site_town(worlds)
    root, vault, deep = (f["id"] for f in founded)
    s, e = _with_site(worlds, sid, founded, [host.id, root])
    seen = next(r for r in _site(e, worlds, root)["rooms"] if r["id"] == vault)
    assert seen["visited"] is False and (seen["about"], seen["role"], seen["door"]) == ("", "", "")
    src = BOARD_JS.read_text(encoding="utf-8")
    site = src[src.index("function siteMap("):src.index("function downArrow(")]
    assert "if (r.visited) {" in site and "LineDashedMaterial" in site


def test_the_way_to_a_room_goes_through_rooms_entered_only(worlds):
    """Stood at the site's host with the way in and the vault entered, the deep vault (seen, not
    entered) is walked to through those two; a room only seen is never a step on the way."""
    sid, host, founded = _site_town(worlds)
    root, vault, deep = (f["id"] for f in founded)
    s, e = _with_site(worlds, sid, founded, [host.id, root, vault])
    s.at = host.id
    pf = places_found.chart(e, worlds)
    node = next(n for n in pf["nodes"] if n["id"] == deep)
    legs = [leg["to"] for leg in node["walk"]["legs"]]
    assert legs[-1] == deep and set(legs[:-1]) <= set(s.places_been())
    assert root in legs and vault in legs
    # The Site's slip for a room pressed is this same chart slip, Walk there included.
    tab = TAB_JS.read_text(encoding="utf-8")
    assert ": site && !MAPV.sel ? siteSlip(site, pf)" in tab


def test_underground_ignores_the_hour():
    """The plan's rule: on the Site the light is one fixed setting and the torch, set after the
    hour's light so it wins at noon and at midnight alike."""
    src = BOARD_JS.read_text(encoding="utf-8")
    hour = src.index("const h = V.hour, L = light(h)")
    under = src.index('if (V.level === "site") { sun.color.setRGB(')
    assert hour < under
    line = src[under:src.index("\n", under)]
    assert "L." not in line and "h)" not in line
