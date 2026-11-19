"""The town tabletop's seats (play/town_seats.py) and the board that draws them.

Phase 2 of docs/place-map-v2-build-plan.md. The seats are dealt by rule over the whole town,
on this side, because the page never learns an unfound place (`places_found.chart()` sends
one only as an index); what crosses is the seat of each place found.

What these hold, each measured on the mock (`docs/mock/place-map-v2/`, 2026-11-18):
- the mock's first seat rule was `k % 8`, and its worst case (sixteen places on one street)
  stacked places 9-16 on 1-8: no two seats may meet, however long a street grows;
- a place never moves when more of the town is found;
- nothing of an unfound place crosses: not its seat, not the gate's.

World-agnostic (the standing instruction of 2026-09-28): `worlds` runs each test on
Aurvantis, Pangrella and the synthetic world.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

from play import places_found, town_seats
from rules import places
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "play" / "static"
BOARD = STATIC / "js" / "places-board.js"


def _party(world, town_id):
    s = Scene(location_id=town_id)
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    pc.hp = pc.hp_base = 60
    s.add(pc)
    e = Engine(s, Dice(seed=3), world=world)
    e.place_party("")
    return s, e


def _settlements(world):
    return [r["id"] for r in world.play.get("settlements") or [] if world.get(r["id"]) is not None]


def _closest(points):
    pts = list(points)
    return min((math.dist(a, b) for i, a in enumerate(pts) for b in pts[i + 1:]), default=math.inf)


def test_no_two_seats_meet_in_any_town(worlds):
    """Every settlement of the world, its whole town laid out: the closest two seats are a
    seat apart (60 units; a miniature is 30 across at the table's scale). Measured
    2026-11-18: 82 towns over the three worlds, the closest pair never under 60."""
    for sid in _settlements(worlds):
        s, e = _party(worlds, sid)
        L = town_seats.layout(e.places())
        assert _closest(L["pos"].values()) >= 60, worlds.get(sid).name


def _street_town(world):
    """The first settlement with crossings (a quartered city), else the first: and the place
    its street grows from (a crossing, else the square)."""
    for sid in _settlements(world):
        s, e = _party(world, sid)
        L = town_seats.layout(e.places())
        crossing = next((i for i, k in L["kind"].items() if k == "crossing"), None)
        if crossing:
            return sid, crossing
    sid = _settlements(world)[0]
    s, e = _party(world, sid)
    L = town_seats.layout(e.places())
    return sid, next(i for i, k in L["kind"].items() if k == "square")


def _founded(sid, host, n):
    """`n` houses founded off one street, as play founds them (a house called on)."""
    return [{"id": f"{sid}~urban:the-house-number-{k:02d}", "name": f"the house number {k}",
             "about": "", "terrain": "urban", "exits": [host], "parent": host, "origin": "found",
             "kind": ""} for k in range(n)]


def test_a_street_of_sixteen_never_stacks_and_the_wall_goes_round_it(worlds):
    """The mock's worst case: sixteen more places on one street. `k % 8` put places 9-16 on
    1-8; rows must keep going out instead, the wall round the last of them, and the paper
    as big as the town (the worst case's street ran to 920 units, past a 560 half-sheet)."""
    sid, host = _street_town(worlds)
    s, e = _party(worlds, sid)
    s.founded.extend(_founded(sid, host, 16))
    L = town_seats.layout(e.places())
    mine = [L["pos"][f"{sid}~urban:the-house-number-{k:02d}"] for k in range(16)]
    assert _closest(L["pos"].values()) >= 60
    far = max(math.hypot(*p) for p in mine)
    assert L["wall"] >= far + 50
    assert L["half"] >= max(max(abs(p[0]), abs(p[1])) for p in mine) + 130
    assert all(L["street"][f"{sid}~urban:the-house-number-{k:02d}"] == host for k in range(16))


def test_a_seat_never_moves_as_more_is_found(worlds):
    """Found from the start, and found again after walking every way out of where the party
    stands: each place keeps the seat it had."""
    sid = _settlements(worlds)[0]
    s, e = _party(worlds, sid)
    first = places_found.chart(e, worlds)["town"]["seats"]
    for n in places_found.chart(e, worlds)["nodes"]:
        s.been.append(n["id"])
    later = places_found.chart(e, worlds)["town"]["seats"]
    assert len(later) > len(first)
    for pid, seat in first.items():
        assert later[pid]["at"] == seat["at"], pid


def test_only_the_places_found_cross_to_the_page(worlds):
    """The seats are the found nodes' and no others; the gate is named only once found.
    The page cannot place what it was never told about."""
    for sid in _settlements(worlds)[:6]:
        s, e = _party(worlds, sid)
        c = places_found.chart(e, worlds)
        found = {n["id"] for n in c["nodes"]}
        assert set(c["town"]["seats"]) == found
        assert c["town"]["gate"] in found | {""}
        whole = town_seats.layout(e.places())
        if whole["gate"] and whole["gate"] not in found:
            assert c["town"]["gate"] == ""


def test_a_room_sits_on_the_street_its_place_says(worlds):
    """A quartered city's rooms say which crossing they hang off (`Place.within`,
    `places._districted`); the seat follows the engine's own shape, not a guess from links."""
    checked = 0
    for sid in _settlements(worlds):
        s, e = _party(worlds, sid)
        L = town_seats.layout(e.places())
        for p in e.places():
            if p.within and L["kind"].get(p.within) == "crossing" and p.id in L["pos"]:
                assert L["street"][p.id] == p.within
                checked += 1
    if not checked:
        pytest.skip("no quartered city in this world")


def test_storeys_are_a_badge_not_a_seat(worlds):
    """A building's floors (`^n`) take no seat of their own; the building counts them, and
    a party up a storey is drawn at its building."""
    sid = _settlements(worlds)[0]
    s, e = _party(worlds, sid)
    known = e.places()
    L = town_seats.layout(known)
    assert not [i for i in L["pos"] if re.search(r"\^-?\d+$", i)]
    floors = [p.id for p in known if re.search(r"\^[1-9]\d*$", p.id) and p.id.split("^")[0] in L["pos"]]
    if not floors:
        pytest.skip("no storeys here")
    f = floors[0]
    got = town_seats.seats(known, [f], f)["seats"][f]
    assert got["at"] == [round(v, 1) for v in L["pos"][f.split("^")[0]]] and not got["drawn"]


# --- the board ---------------------------------------------------------------------------

def test_the_board_imports_only_the_vendored_three():
    """Offline app: every import is a relative path to a vendored file that exists, in the
    version-named directory (a cached copy can never be stale under the same name), and the
    addons import Three.js by path, since an inline import map would need the CSP nonce."""
    src = BOARD.read_text(encoding="utf-8")
    imports = re.findall(r'^import .* from "([^"]+)";', src, flags=re.M)
    assert imports and all("vendor/three-r170/" in i for i in imports)
    for i in imports:
        assert (BOARD.parent / i).resolve().is_file(), i
    for addon in (STATIC / "js" / "vendor" / "three-r170" / "addons").rglob("*.js"):
        text = addon.read_text(encoding="utf-8")
        assert "from 'three'" not in text and 'from "three"' not in text, addon.name


def test_every_miniature_the_board_asks_for_is_shipped_and_licensed():
    """The models named in the board's KIT_FILES are on disk, beside each kit's licence, and
    Three.js and Kenney are in docs/asset-licences.md."""
    src = BOARD.read_text(encoding="utf-8")
    files = re.findall(r'"((?:hex|town)/[a-z-]+)"', src.split("KIT_FILES = [", 1)[1].split("];", 1)[0])
    assert len(files) >= 10
    for f in files:
        assert (STATIC / "models" / "kenney" / f"{f}.glb").is_file(), f
    for kit in ("hex", "town"):
        assert (STATIC / "models" / "kenney" / kit / "License.txt").is_file()
        assert (STATIC / "models" / "kenney" / kit / "Textures" / "colormap.png").is_file()
    assert (STATIC / "js" / "vendor" / "three-r170" / "THREE-LICENSE.txt").is_file()
    lic = (ROOT / "docs" / "asset-licences.md").read_text(encoding="utf-8")
    assert "Three.js r170" in lic and "Kenney" in lic and "CC0" in lic


def test_the_chart_is_the_fallback():
    """Owner decision 3 (2026-11-18): without WebGL, when the module will not load, or when
    the context is lost, Places draws the chart from the same state."""
    tab = (STATIC / "js" / "table" / "16-tab-map.js").read_text(encoding="utf-8")
    src = BOARD.read_text(encoding="utf-8")
    assert 'getContext("webgl2")' in tab and '.catch(err =>' in tab and 'BOARD.state = "chart"' in tab
    assert "webglcontextlost" in src and "api.lost()" in src
    page = (ROOT / "play" / "templates" / "play" / "table.html").read_text(encoding="utf-8")
    assert "placesBoard: \"{% asset 'js/places-board.js' %}\"" in page
