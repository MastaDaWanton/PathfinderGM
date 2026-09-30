"""The play table rebuild, stage 3: the Map tab's Places chart and the Talk tray.

The owner's approved design (docs/mock/table-layout/, README "Map is a tab, Talk is a
tray") built into the real table: the board where the book was with Places beside Flat
and 3D, the fog-of-war chart drawn from the engine's `scene.places_found`
(play/places_found.py) by `16-places-chart.js`, Walk there going by the real movement
path (`16-tab-map.js`), and the conversation tray restyled in the numbers' column.

What each test holds, and the defect it is there for, is in its docstring. The chart and
the walk run in node on the shipped scripts themselves, fed a chart the engine really
built for each of the three fixture worlds (the standing instruction of 2026-09-28: fixes
are world-agnostic).
"""
from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from _exits_dom import PRELUDE
from pagesource import TABLE, TABLE_SCRIPTS
from play import exits as exits_mod
from play import places_found
from test_places_found import _party, _town, _travel, _want

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not on this machine")


def _js(name: str) -> str:
    return (TABLE_SCRIPTS / name).read_text(encoding="utf-8")


def _css() -> str:
    src = TABLE.read_text(encoding="utf-8")
    return src[src.index("<style>"):src.index("</style>")]


def _node(tmp_path: Path, code: str) -> dict:
    f = tmp_path / "probe.js"
    f.write_text(code, encoding="utf-8")
    done = subprocess.run(["node", str(f)], capture_output=True, text=True, encoding="utf-8",
                          timeout=60)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


def _onward(e, world, s):
    """A way next door, somewhere not yet stood in when there is one (a dead end, the
    well, has only the way back)."""
    row = [x for x in exits_mod.exits(e, world) if x["group"] == "next_door" and not x["blocked"]]
    fresh = [x for x in row if x["id"] not in set(s.places_been())]
    return (fresh or row)[0]["id"]


def _walked_chart(world, steps=2):
    """A chart the engine built after a few real walks in a real town, stopped short of
    the walk that would leave nothing under the fog (the synthetic world's town shows 12
    of its 13 places from the way in)."""
    loc = _town(world)
    s, e, pc = _party(world, loc.id)
    chart = places_found.chart(e, world)
    for _ in range(steps):
        _travel(e, pc, _onward(e, world, s))
        nxt = places_found.chart(e, world)
        if nxt["found"] >= nxt["layout"]["size"]:
            break
        chart = nxt
    return s, e, pc, chart


def _draw(tmp_path, pf, sel=None) -> dict:
    code = _js("16-places-chart.js") + f"""
const pf = {json.dumps(pf)};
console.log(JSON.stringify({{
  svg: PlacesChart.svg(pf, {{ sel: {json.dumps(sel)}, k: 1 }}),
  slip: PlacesChart.slip(pf, {{ sel: {json.dumps(sel)} }}),
  header: PlacesChart.header(pf),
  key: PlacesChart.key(pf),
}}));"""
    return _node(tmp_path, code)


# --- the chart -----------------------------------------------------------------------------

@needs_node
def test_the_chart_draws_the_places_found_and_nothing_under_the_fog(worlds, tmp_path):
    """The owner's fog: "only being able to see places conected to where you have been
    before". The mock drew from a data.js holding all 43 places of Zhilvarnia by name and
    hid the rest in its own script; the real page is sent only what is found, and the
    drawing may not add to it. After two walks in each fixture world the page draws
    exactly the found places, one node each, and no id or name of a place still under the
    fog is anywhere in what it writes: a hidden place leaking into the DOM would be the
    fog lifted for anyone who opens the inspector."""
    s, e, pc, pf = _walked_chart(worlds)
    out = _draw(tmp_path, pf, sel=next(n["id"] for n in pf["nodes"] if not n["current"]))
    drawn = out["svg"] + out["slip"]
    ids = re.findall(r'data-node="([^"]+)"', drawn)
    assert sorted(ids) == sorted(n["id"] for n in pf["nodes"]), "one node per place found"
    found = {n["id"] for n in pf["nodes"]}
    names = [n["name"].lower() for n in pf["nodes"]]
    text = drawn.lower()
    hidden = [p for p in e.places() if p.id not in found]
    assert hidden, "the test needs somewhere still under the fog"
    for p in hidden:
        assert p.id not in drawn, p.id
        # A hidden name that is part of a found one ("the stables" in "the upper floor of
        # the stables") cannot be told apart in text, so only the others are checked.
        if not any(p.name.lower() in n for n in names):
            assert p.name.lower() not in text, p.name
    # Each visited place and each seen one drawn as the design has them.
    for n in pf["nodes"]:
        cls = re.search(r'<g class="node([^"]*)" data-node="%s"' % re.escape(n["id"]), out["svg"]).group(1)
        assert (" been" in cls) == n["visited"] and (" seen" in cls) == (not n["visited"])
        assert (" here" in cls) == n["current"]
    # Lines only between places on the chart; a stroke into the paper for each stub.
    assert out["svg"].count('class="stub') == len(pf["stubs"]) + len(pf["roads"])


@needs_node
def test_the_header_counts_places_found_and_visited_never_the_places_the_rules_know(worlds, tmp_path):
    """The owner: "instead of displaying the number of places the rules know you display
    the number of places found by the user". `layout.size` is on the page (the chart is
    laid out over the whole town so nothing moves as more is found), and at the way into
    Kalimnar it said 18 against 2 found: shown, it would tell the player how much of the
    town is left to find. The header is found and visited, "all of them visited" when
    nothing seen is unwalked, and the size appears nowhere in what is drawn."""
    loc = _town(worlds)
    s, e, pc = _party(worlds, loc.id)
    pf = places_found.chart(e, worlds)
    out = _draw(tmp_path, pf)
    f, v, size = pf["found"], pf["visited"], pf["layout"]["size"]
    assert size > f, "the rules know more places than are found"
    assert out["header"].startswith(f"{f} places found, {v} of them visited. ")
    assert "Solid lines are next door; dashed lead outside the walls." in out["header"]
    assert not re.search(r"\b%d\b" % size, out["header"] + out["slip"] + out["key"])
    everywhere = dict(pf, visited=f)
    assert _draw(tmp_path, everywhere)["header"].startswith(f"{f} places found, all of them visited.")
    # The size is read in one place, to lay the chart out, and nowhere else.
    code = "\n".join(line.split("//", 1)[0] for line in
                     (_js("16-places-chart.js") + _js("16-tab-map.js")).splitlines())
    assert code.count(".size") == 1 and "Number(layout && layout.size)" in code


@needs_node
def test_a_place_never_moves_as_more_is_found(worlds, tmp_path):
    """"The layout is worked out once over the whole town, so a place never moves as more
    is found" (the mock README). Laid out over what was found, every walk would re-spring
    the chart and the market would jump across the sheet. Walked three times in each world,
    every place keeps the drawing position it had the first time it was drawn."""
    loc = _town(worlds)
    s, e, pc = _party(worlds, loc.id)
    charts = []
    for _ in range(3):
        charts.append(places_found.chart(e, worlds))
        _travel(e, pc, _onward(e, worlds, s))
    charts.append(places_found.chart(e, worlds))
    code = _js("16-places-chart.js") + f"""
const charts = {json.dumps(charts)};
console.log(JSON.stringify(charts.map(pf => {{
  const out = {{}};
  for (const m of PlacesChart.svg(pf).matchAll(/data-node="([^"]+)"[^>]*><circle cx="([^"]+)" cy="([^"]+)"/g))
    out[m[1]] = [+m[2], +m[3]];
  return out;
}})));"""
    seen = {}
    for drawn in _node(tmp_path, code):
        for pid, xy in drawn.items():
            assert seen.setdefault(pid, xy) == xy, pid
    # The frame changes with every walk, the drawing's coordinates never do. (The
    # synthetic town shows 12 of its 13 places from the way in, so there "more" is more
    # visited rather than more found.)
    assert charts[-1]["visited"] > charts[0]["visited"]


@needs_node
def test_a_wanted_characters_shut_ways_are_barred_with_the_rules_reason(worlds, tmp_path):
    """The mock's Wanted drawing: a way the watch holds is rubric with a bar across it, a
    third of the way out from the place it is shut from, and its title is the rules' own
    sentence (the exits row's `blocked`), never a sentence the page made up."""
    loc = _town(worlds)
    s, e, pc = _party(worlds, loc.id)
    _want(pc, loc.id)
    pf = places_found.chart(e, worlds)
    shut = [x for x in pf["edges"] if x["shut"]]
    if not shut:
        pytest.skip("the way in of this town has no way out the watch holds")
    out = _draw(tmp_path, pf)
    bars = re.findall(r'<line class="bar"[^>]*><title>([^<]*)</title>', out["svg"])
    assert len(bars) == len(shut)
    assert out["svg"].count('class="edge shut"') + out["svg"].count('class="edge road shut"') >= 1
    for x in shut:
        assert html.escape(x["shut"], quote=True).replace("&#x27;", "'") in bars
    assert "Shut to you" in out["key"]


# --- Walk there ----------------------------------------------------------------------------

_MAP_STUBS = r"""
ELS.boardframe = el("boardframe"); ELS.boardframe.classList.toggle = () => {};
ELS.boardframe.dataset = {};
const Shell = { tab() {}, mode: () => "map" };
const CSS = { escape: s => s };
function MouseEvent() {}
window.addEventListener = () => {};
function attachSpellChipStub() {}
"""


def _walk_run(tmp_path, steps: str) -> dict:
    code = PRELUDE + _MAP_STUBS + "\n".join(
        _js(n) for n in ("10-spells.js", "11-exits.js", "16-places-chart.js", "16-tab-map.js"))
    return _node(tmp_path, code + "\n" + steps)


def _state(pf, exits, **scene):
    return {"awaiting": scene.pop("awaiting", None), "ended": False,
            "scene": dict({"in_encounter": False, "exits": exits, "places_found": pf}, **scene)}


def _leg(a, b):
    return {"from": a, "to": b, "name": b, "time_words": "a few minutes' walk", "minutes": 4}


def _ex(to, blocked=""):
    return {"id": to, "name": to, "group": "next_door", "time_words": "a few minutes' walk",
            "blocked": blocked, "journey": False}


def _pf(here, dest_legs):
    return {"here": here, "found": 3, "visited": 2, "edges": [], "stubs": [], "roads": [],
            "layout": {"size": 3, "links": [[0, 1], [1, 2]]},
            "nodes": [{"id": here, "name": here, "i": 0, "current": True, "visited": True,
                       "near": False, "setting": "in", "walk": None, "why": ""},
                      {"id": "stables", "name": "stables", "i": 2, "current": False,
                       "visited": False, "near": False, "setting": "in", "why": "",
                       "walk": {"legs": dest_legs, "minutes": 4 * len(dest_legs)}}]}


@needs_node
def test_walk_there_attaches_each_leg_as_the_exits_row_does_and_sends_nothing(tmp_path):
    """The owner ruled that a way on "should attach like a spell does and then apply when
    you send", and the chip is the exits row's own (11's `exitChip` into 10's
    `attachPlace`), so Say posts `/api/say` with the place chip the server checks at the
    door (play/views.py `_read_place`) and moves by `_take_the_exit`. A walk of two legs is
    two turns: pressing Walk there attaches the first leg and sends nothing; arriving
    attaches the next once 04 has cleared the spent chip (it draws the state first and
    clears after, so a chip attached during the draw was wiped); arriving at the end
    finishes the walk. A fight on the way stops it with the reason said, and attaches
    nothing: the next leg would be a withdraw the player never chose."""
    got = _walk_run(tmp_path, f"""
const s1 = {json.dumps(_state(_pf("well", [_leg("well", "market"), _leg("market", "stables")]),
                              [_ex("market")]))};
const s2 = {json.dumps(_state(_pf("market", [_leg("market", "stables")]), [_ex("well"), _ex("stables")]))};
const s3 = {json.dumps(_state(dict(_pf("stables", []), here="stables"), [_ex("market")]))};
const fight = {json.dumps(_state(_pf("market", [_leg("market", "stables")]),
                                 [_ex("well"), _ex("stables")], in_encounter=True))};
const out = {{}};
renderAll(s1);
walkThere("stables");
out.first = sayBody(); out.sentOnPress = SENT.length; out.said1 = MAPV.said;
renderAll(s2); clearAttachments();
setTimeout(() => {{
  out.second = sayBody(); out.said2 = MAPV.said;
  renderAll(s3); clearAttachments();
  out.done = MAPV.walk; out.said3 = MAPV.said;
  // The same walk, with a fight met at the market.
  renderAll(s1); walkThere("stables"); renderAll(fight); clearAttachments();
  setTimeout(() => {{ out.fightChip = sayBody(); out.fightSaid = MAPV.said; out.fightWalk = MAPV.walk;
    out.sent = SENT.length; done(out); }}, 5);
}}, 5);""")
    assert got["first"] == {"text": "", "attachments": [{"kind": "place", "id": "market"}]}
    assert got["sentOnPress"] == 0 and got["sent"] == 0, "the page sent a turn by itself"
    assert "first of 2 legs" in got["said1"] and "Press Say" in got["said1"]
    assert got["second"] == {"text": "", "attachments": [{"kind": "place", "id": "stables"}]}
    assert "the last leg" in got["said2"]
    assert got["done"] is None and got["said3"] == "You are at stables."
    assert got["fightChip"] == {"text": ""} and got["fightWalk"] is None
    assert "there is a fight" in got["fightSaid"]


def test_the_first_leg_of_every_walk_is_a_way_the_server_takes(worlds):
    """Walk there attaches `walk.legs[0]`, so that leg has to be a way the say door takes:
    one of `scene.exits` as the engine builds them this moment, open, not a journey
    (`_read_place` refuses anything else with "There is no way from here to ..."). Checked
    for every place found, after a few walks, in each world."""
    from play.views import _read_place

    s, e, pc, pf = _walked_chart(worlds, steps=3)

    class _C:
        world = worlds

        def engine(self):
            return e

    row = {x["id"]: x for x in exits_mod.exits(e, worlds)}
    walks = [n for n in pf["nodes"] if n["walk"]]
    assert walks
    for n in walks:
        first = n["walk"]["legs"][0]
        assert first["from"] == s.at and first["to"] in row and not row[first["to"]]["blocked"]
        chip, err = _read_place(_C(), {"kind": "place", "id": first["to"]}, "", False)
        assert not err and chip[0]["id"] == first["to"], (n["id"], err)


def test_walk_there_uses_the_exits_rows_own_chip_and_the_one_say_door():
    """One path for a move: the chart holds no copy of the chip or of the post. It calls
    11's `exitChip` and 10's `attachPlace`, and never posts; the turn goes out through
    04's Say like any other."""
    code = "\n".join(line.split("//", 1)[0] for line in _js("16-tab-map.js").splitlines())
    body = code[code.index("function mapAttachLeg("):code.index("onRender(function walkOn")]
    assert "attachPlace(exitChip(way, !!scene.in_encounter))" in body
    for sender in ("post(", "fetch(", "takeTurn(", "/api/"):
        assert sender not in code, sender


# --- the Map tab's head row ------------------------------------------------------------------

def test_places_is_its_own_button_left_of_flat_and_3d():
    """"add another button" in the space the owner circled in the head row: its own
    button, apart from Flat and 3D, because it is a different map. The ground's controls
    keep their room while the chart is shown (visibility, not removal), so nothing moves
    under the pointer that pressed Places."""
    src = TABLE.read_text(encoding="utf-8")
    head = src[src.index('<div class="boardhead">'):src.index('<div id="mapwrap">')]
    assert head.index('id="placesbtn"') < head.index('id="groundctl"')
    assert 'aria-pressed="false"' in head and 'aria-controls="placeswrap"' in head
    tab = _js("16-tab-map.js")
    assert 'ground.style.visibility = places ? "hidden" : ""' in tab
    assert "ground.inert = places" in tab
    ground = _js("03-offers-and-map.js")
    assert '$("#groundctl").innerHTML = view + picker' in ground
    # A clicked square still queues the move, on either board (04, unchanged).
    turns = _js("04-combat-and-turns.js")
    assert 'const sq = t.closest("[data-sq]");' in turns and "COMBAT.move = sq.dataset.sq" in turns


def test_the_chart_is_on_chart_paper_in_gilt_with_names_at_thirteen_and_a_half_pixels():
    """The approved drawing: the parchment in the panels' gilt (the theme's
    .v2-chart-paper), the ink sized in screen pixels by --k so the names stay 13.5px at
    any scale (the mock measured 8.5px names at a fixed size), the seen in italic with a
    paler ring, the stubs fading, a shut way in rubric."""
    tab = _js("16-tab-map.js")
    assert 'class="chart v2-chart-paper"' in tab
    css = _css()
    assert "font: 600 calc(13.5px * var(--k))/1 var(--body)" in css
    assert ".chart .node.seen text { font-style: italic;" in css
    assert ".chart .node.seen circle { fill: rgba(243, 234, 214, .5); stroke: #7d6b55; }" in css
    assert ".chart .edge.shut { stroke: #8e2317; }" in css
    chart = _js("16-places-chart.js")
    assert 'stop-opacity=".9"' in chart and 'stop-opacity="0"' in chart


# --- the Talk tray -------------------------------------------------------------------------

def _rule(css, selector):
    at = css.index(selector + " {")
    return css[at:css.index("}", at)]


def test_the_talk_tray_never_covers_the_book_or_the_pen():
    """Measured in the old app: the slide-over tray covered the beat about to be read
    (the story's left margin 273px against a 400px tray at 1440x900) and, with the column
    hidden, lay over the first 350px of the say box. The design's tray takes the numbers'
    column; with the sheet hidden a column of its own beside the book; below 1180px the
    sheet's column; on a phone the whole stage, with the book and the desk put out of
    sight. Measured live 2026-09-30 (the stage 3 report): 0px of overlap with the book or
    the desk at 1792, 1440 and 1024, sheet shown or hidden."""
    css = _css()
    assert "grid-area: numbers" in _rule(css, "  #talktray")
    assert "position: fixed" not in _rule(css, "  #talktray")
    assert ('body.sheet-hidden.talkopen:is(.mode-table, .mode-map) .stage {\n'
            '    grid-template-columns: minmax(0, 1fr) 340px; grid-template-areas: "book talk" "desk talk"; }') in css
    assert "body.sheet-hidden:is(.mode-table, .mode-map) #talktray { grid-area: talk; }" in css
    narrow = css[css.index("@media (max-width: 1180px) {\n    /* The book is shorter"):]
    assert "#talktray { grid-area: sheet; }" in narrow[:narrow.index("\n  }\n")]
    phone = css[css.index("/* --- Phone: the story is the page"):]
    assert "grid-row: 1 / -1" in phone
    assert "body.talkopen:is(.mode-table, .mode-map) :is(.book, .board, .desk) { visibility: hidden; }" in phone


def test_the_tray_never_opens_by_itself_and_counts_new_lines():
    """A conversation starting never opens the tray (owner G0 Q7; on a desktop it covered
    the beat being read). Talk counts the new lines instead, in the design's words, "2 new",
    where a bare "2" beside Talk read as two people."""
    code = _js("08-conversation.js")
    hook = code[code.index("onRender(function conversationTray"):code.index("// --- controls")]
    assert "openTalk(" not in hook
    assert "count.textContent = n ? `${n} new` : \"\"" in code
    opens = [m.start() for m in re.finditer(r"openTalk\(\)", code)]
    assert len(opens) == 1 and "#talktab" in code[opens[0] - 120:opens[0]]


@needs_node
def test_a_seen_mark_from_an_earlier_game_does_not_hide_new_lines(tmp_path):
    """The badge counts lines past the newest one this viewer has seen, kept per world and
    character name. A character begun again keeps that name, and the old game's mark came
    with it: measured live 2026-09-30, a mark of 10 left the new game's lines 2 to 5
    uncounted, and Talk said nothing new while the fishmonger was talking. A mark past the
    log's own counter (`seq`) cannot be this log's, and is dropped."""
    code = """
const store = { "pgm.table.convo.v1": JSON.stringify({ seen: { "W|K": 10 } }) };
const localStorage = { getItem: k => store[k] || null, setItem: (k, v) => { store[k] = v; } };
const document = { addEventListener() {}, getElementById() { return null; } };
const HOOKS = [];
function onRender(fn) { HOOKS.push(fn); }
const esc = s => String(s);
""" + _js("08-conversation.js") + """
const line = (n, who) => ({ n, who, name: who, text: "x", beat: n, t: 0 });
const state = (seq, recent) => ({ world: "W", pc: { name: "K" },
  scene: { talk: [{ ref: "c3" }], conversation: { people: [], seq, recent } } });
HOOKS[0](state(5, [1, 2, 3, 4, 5].map(n => line(n, n === 1 ? "you" : "c3"))), null);
const first = convoUnread();
HOOKS[0](state(6, [1, 2, 3, 4, 5, 6].map(n => line(n, n === 1 ? "you" : "c3"))), null);
console.log(JSON.stringify({ first, next: convoUnread() }));"""
    assert _node(tmp_path, code) == {"first": 0, "next": 1}


@needs_node
def test_ignore_and_take_your_leave_are_below_the_log_with_their_answer_line(tmp_path):
    """The two ways out of a conversation (owner Q42), drawn by 02's `renderTalk` into
    #talk, which follows the log and is never inside its scroll (Disco Elysium's log held
    its live choices, and scrolling back left players unable to reach them). Each person
    has their own Ignore, posting `/api/talk` do=ignore with their ref; Take your leave
    posts do=leave; the regard bar is drawn only when the state carries a regard; and a
    line is held open above the buttons for the answer (`flash`), because on a phone the
    tray covers the desk and #err with it, where a refused Ignore said nothing visible."""
    state = _js("02-state.js")
    render = state[state.index("function renderTalk(s)"):state.index('document.addEventListener("click", async e => {\n  // Cast')]
    code = """
const EL = { hidden: true, innerHTML: "" };
const $ = () => EL;
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g,
  c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
""" + render + """
renderTalk({ scene: { talk: [
  { ref: "c9", name: "Aethorin Thoric", attitude: "friendly", regard: 62, regard_max: 100 },
  { ref: "c4", name: "Namarie", attitude: "indifferent" } ] } });
const one = EL.innerHTML, shown = !EL.hidden;
renderTalk({ scene: { talk: [] } });
console.log(JSON.stringify({ one, shown, gone: EL.hidden, empty: EL.innerHTML }));"""
    got = _node(tmp_path, code)
    markup = got["one"]
    assert got["shown"] and got["gone"] and got["empty"] == ""
    assert markup.index('id="talksay"') < markup.index("data-ignore") < markup.index('id="takeleave"')
    assert markup.count("data-ignore=") == 2 and 'data-ignore="c9"' in markup
    assert "In conversation with <b>Aethorin Thoric</b>" in markup
    assert markup.count('class="regard"') == 1 and "width:62%" in markup
    assert 'aria-label="Regard 62 of 100"' in markup
    click = state[state.index('const ignore = e.target.closest("[data-ignore]");'):]
    assert 'post("/api/talk", { do: "ignore", who: ignore.dataset.ignore })' in click
    assert 'post("/api/talk", { do: "leave" })' in click
    flash = _js("08-conversation.js")
    flash = flash[flash.index("function flash("):flash.index("function convoGame(")]
    assert 'getElementById("talksay")' in flash
    assert "min-height: 3em" in _rule(_css(), "  .talksay")
