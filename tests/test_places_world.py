"""The place map's world model (play/static/js/table/16-places-world.js), run in node on the
shipped script itself, fed each world's real atlas (play/atlas.py).

Phase 3 of docs/place-map-v2-build-plan.md: the Region, Continent and World maps. What these
hold, each measured on the chosen mock (`docs/mock/place-map-v2/`, 2026-11-18):
- the owner could not tell the nations apart until neighbours were coloured differently, so
  no two neighbouring nations may share a colour;
- names had to be forced inside their own borders (the owner's rule); the mock placed 16 of 16
  on Aurvantis, and every world must place every known nation's name, wholly on its own land;
- learning of a city must move nothing, so the layout never reads what is known;
- the World paper repainted on every press (740 ms) until it was painted once per state of
  knowledge;
- a comment pasted mid-line once hid every World label.

World-agnostic (the standing instruction of 2026-09-28): `worlds` runs each on Aurvantis,
Pangrella and the synthetic world.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from play import atlas
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene

ROOT = Path(__file__).resolve().parent.parent
WORLD_JS = ROOT / "play" / "static" / "js" / "table" / "16-places-world.js"
TAB_JS = ROOT / "play" / "static" / "js" / "table" / "16-tab-map.js"
BOARD_JS = ROOT / "play" / "static" / "js" / "places-board.js"

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not on this machine")


def _node(tmp_path: Path, world, body: str) -> dict:
    """Run `body` in node with `PlacesWorld` and `W` (this world's atlas) in scope; the last
    line printed is the answer."""
    data = tmp_path / "atlas.json"
    data.write_text(json.dumps(atlas.atlas(world)), encoding="utf-8")
    probe = tmp_path / "probe.js"
    probe.write_text(WORLD_JS.read_text(encoding="utf-8") + "\n"
                     + f"const W = JSON.parse(require('fs').readFileSync({json.dumps(str(data))}, 'utf8'));\n"
                     + body, encoding="utf-8")
    done = subprocess.run(["node", str(probe)], capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


# Cinzel capitals run wide: an estimate a little wider than the canvas measures, so a name the
# test places would fit the page's narrower one.
MEASURE = "(s, px, sp) => s.length * (px * .78 + sp)"


@needs_node
def test_neighbouring_nations_never_share_a_colour(worlds, tmp_path):
    """The owner could not tell the nations apart at one shared ink (2026-11-18). Nations whose
    land meets on the World, or that a land or river road joins, take different washes."""
    got = _node(tmp_path, worlds, """
const col = PlacesWorld.nationColours(W), adj = PlacesWorld.neighbours(W);
const clash = Object.entries(adj).flatMap(([a, s]) => [...s].filter(b => col[a] === col[b]).map(b => a + "/" + b));
console.log(JSON.stringify({ clash, nations: Object.keys(col).length, links: Object.values(adj).reduce((n, s) => n + s.size, 0) }));
""")
    assert got["clash"] == [] and got["nations"] == len(atlas.atlas(worlds)["nations"])


@needs_node
def test_every_known_nations_name_lies_inside_its_borders(worlds, tmp_path):
    """Every city known, every nation's name placed, and every cell under each name's box is
    that nation's land. The mock placed 16 of 16 on Aurvantis, Undertide Warrens' wedge only on
    two lines; a name that finds no room is reported, never dropped quietly."""
    got = _node(tmp_path, worlds, f"""
const K = PlacesWorld.worldKnown(W, {{ been: W.cities.map(c => c.id) }});
const names = PlacesWorld.placeNames(W, K, {MEASURE}), G = PlacesWorld.ownerGrid(W);
const cell = 2048 / G.N, bad = [];
Object.entries(names.placed).forEach(([n, p]) => {{
  const me = G.nations.indexOf(n);
  for (let y = p.y - p.h / 2; y <= p.y + p.h / 2; y += cell) for (let x = p.x - p.w / 2; x <= p.x + p.w / 2; x += cell) {{
    const i = Math.floor(x / cell), j = Math.floor(y / cell);
    if (G.owner[j * G.N + i] !== me) {{ bad.push(n); return; }} }}
}});
console.log(JSON.stringify({{ placed: Object.keys(names.placed).length, missed: names.missed, bad: [...new Set(bad)] }}));
""")
    assert got["missed"] == [] and got["bad"] == []
    assert got["placed"] == len(atlas.atlas(worlds)["nations"])


@needs_node
def test_learning_of_a_city_moves_nothing(worlds, tmp_path):
    """The layout is dealt over every city, known or not, and never reads what is known: two
    separate loads of the world lay every city in the same place, and knowing one town or all
    of them changes none of it."""
    got = _node(tmp_path, worlds, """
const a = PlacesWorld.worldLayout(W).pos, W2 = JSON.parse(JSON.stringify(W)), b = PlacesWorld.worldLayout(W2).pos;
PlacesWorld.worldKnown(W2, { been: W2.cities.map(c => c.id) });
const moved = Object.keys(a).filter(id => a[id][0] !== b[id][0] || a[id][1] !== b[id][1]);
console.log(JSON.stringify({ moved, laid: Object.keys(a).length }));
""")
    assert got["moved"] == [] and got["laid"] == len(atlas.atlas(worlds)["cities"])


@needs_node
def test_what_is_known_and_how(worlds, tmp_path):
    """Stood in one town: it is `been`, the towns a land or river road leads to are known from
    the road's sign, a heard town is `heard`, a read map makes its nation's towns `map`; a sea
    passage is drawn only from a port stood in, and knowing more never unknows anything."""
    got = _node(tmp_path, worlds, """
const home = W.cities[0].id, far = W.cities[W.cities.length - 1];
const K1 = PlacesWorld.worldKnown(W, { been: [home] });
const K2 = PlacesWorld.worldKnown(W, { been: [home], heard: { [far.id]: { who: "a carter", line: "word of it" } }, maps: [far.nation] });
const roadOut = W.routes.filter(r => r.by !== "sea" && (r.a === home || r.b === home)).map(r => (r.a === home ? r.b : r.a));
const seaLegal = K1.roads.every(r => r.by !== "sea" || K1.how[r.a].by === "been" || K1.how[r.b].by === "been");
console.log(JSON.stringify({
  home: K1.how[home].by, signed: roadOut.every(id => K1.how[id] && ["been", "road"].includes(K1.how[id].by)),
  far: (K2.how[far.id] || {}).by, kept: Object.keys(K1.how).every(id => K2.how[id]), seaLegal,
  mapped: W.cities.filter(c => c.nation === far.nation).every(c => K2.how[c.id]) }));
""")
    assert got["home"] == "been" and got["signed"] and got["kept"] and got["seaLegal"] and got["mapped"]
    assert got["far"] in ("heard", "road", "been")


@needs_node
def test_the_land_grid_is_quick_enough_to_open_the_world(worlds, tmp_path):
    """The territory grid is worked out once per world. Testing every cell against every land
    disc was 84 million steps on Aurvantis; marking the discs onto the grid took 228 ms there
    (2026-11-18). Held under two seconds so a slow machine still opens the World."""
    got = _node(tmp_path, worlds, """
const t = Date.now(); PlacesWorld.ownerGrid(W); const ms = Date.now() - t;
const again = Date.now(); PlacesWorld.ownerGrid(W); console.log(JSON.stringify({ ms, twice: Date.now() - again }));
""")
    assert got["ms"] < 2000 and got["twice"] < 5


def test_known_places_names_the_town_the_party_is_in(worlds):
    """The maps above the town start from the settlement the party is in."""
    sid = next(r["id"] for r in worlds.play["settlements"] if worlds.get(r["id"]) is not None)
    s = Scene(location_id=sid)
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    s.add(pc)
    e = Engine(s, Dice(seed=3), world=worlds)
    e.place_party("")
    assert atlas.known_places(e, worlds)["town"] == sid


def test_the_world_paper_is_painted_once_per_state_of_knowledge_and_labels_are_drawn():
    """The mock repainted the World on every press (740 ms, cut to 15 ms by keeping it per state
    of knowledge), and once a comment pasted mid-line hid every World label. The paper is keyed
    on what is known, and the line that draws the names is live code, not a comment's tail."""
    src = BOARD_JS.read_text(encoding="utf-8")
    assert "worldPaper.key !== key" in src and "Object.keys(v.K.how).sort().join()" in src
    live = [ln for ln in src.splitlines() if re.search(r"\blabels\(\);", ln)]
    assert live and all("//" not in ln.split("labels();")[0] for ln in live)
    assert "tags.innerHTML = html;" in src


def test_every_map_is_reachable_from_the_breadcrumb():
    """World, Continent, Region and Town, each a button on every map above the town."""
    tab = TAB_JS.read_text(encoding="utf-8")
    for level in ("world", "continent", "nation", "town"):
        assert f'["{level}",' in tab
    assert 'data-maplevel="${esc(lv)}"' in tab


def test_the_keyboard_list_is_hidden_the_way_the_hit_test_reads():
    """The board's keyboard list of places (16-tab-map.js, `.boardkeys`) was hidden by
    clip-path alone: its buttons kept their full size under the canvas, and the release hit
    test (tools/table_hit_test.js) reported every one covered on the packaged build, 5 to 9 a
    map (phase 6, 2026-11-19). Collapsed to the visually-hidden 1px box until a button takes
    the focus, it reads as unseen, and opens whole for the keyboard."""
    html = (ROOT / "play" / "templates" / "play" / "table.html").read_text(encoding="utf-8")
    rule = html[html.index(".board3d .boardkeys {"):html.index(".board3d .boardkeys .v2-btn")]
    shut, opened = rule.split(":focus-within", 1)
    assert "width: 1px; height: 1px; overflow: hidden" in shut
    assert "width: auto; height: auto" in opened and "overflow-y: auto" in opened
