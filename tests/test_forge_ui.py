"""The forge's page (docs/blacksmithing-ui-plan.md §5, §6, §12; lanes U2 and U7).

The forge is the second bench over the table, mounted on the bench core (29-bench-core.js)
and built FLAT FIRST: fully playable with no 3D stage, no forge games and no ledger. These
tests hold what the lane measured going wrong while it was built, live on scratch data at
1600x900 and 1280x720 (2026-10-04), and the rules the herb bench already keeps for itself
(no loop while idle, no dash, one layer scale, transform and opacity only). The behaviour
checks of the core load the real file into node with a small fake DOM, as
tests/test_bench_core.py does, and skip saying why where node is not installed.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from django.contrib.staticfiles import finders
from django.test import Client, override_settings

from play import campaign as cm
from play import forge_views
from rules import places
from rules.sheet import load_pc

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "play" / "static"
TABLE_JS = STATIC / "js" / "table"
CORE = TABLE_JS / "29-bench-core.js"
HERB_SHELL = TABLE_JS / "30-bench-shell.js"
FORGE_JS = [TABLE_JS / f for f in ("40-forge-shell.js", "41-forge-rack.js", "43-forge-order.js")]
FORGE_CSS = STATIC / "css" / "forge.css"
TABLE = ROOT / "play" / "templates" / "play" / "table.html"
CRAFT = ROOT / "play" / "templates" / "play" / "craft.html"

# Other lanes' files the table names only once they are in the build (contracts §10, §11).
GUARDED = (["css/forge-games.css", "js/table/42-forge-stage.js"]
           + [f"js/forge-games/{m}.js" for m in ("smelt", "alloy", "forge", "quench", "temper",
                                                   "fold", "hone", "assemble", "finish",
                                                   "strengthen")]
           + [f"js/forge-stage/{f}.js" for f in ("00-heat", "01-props", "02-families",
                                                   "03-smithy", "04-fx")])


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _code(text: str) -> str:
    out = []
    for line in text.splitlines():
        if line.lstrip().startswith("//"):
            continue
        out.append(re.sub(r"\s//\s.*$", "", line))
    return "\n".join(out)


@pytest.fixture(scope="module")
def table_html():
    return Client().get("/play/").content.decode("utf-8")


# --- the layer and the ways in ----------------------------------------------------------------

def test_the_table_serves_the_forge_layer_and_the_smithing_button(table_html):
    """UI plan §5.1: the forge opens over the table as its own dialog, served in the page
    so closing is instant, from a Smithing button beside Herbalism. A layer only built by
    script would leave the button's aria-controls pointing at nothing. It carries the
    bench's class too: bench.css's layer, panels, ladder and the perk picker's styles are
    all scoped to `.bench` (lane U5's report: the forge's perk picker came up unstyled)."""
    tag = re.search(r'<div id="forge"[^>]*>', table_html)
    assert tag, "the table has no #forge layer"
    tag = tag.group(0)
    for need in ('role="dialog"', 'aria-modal="true"', "hidden", 'aria-labelledby="forge-title"',
                 'class="bench forge"'):
        assert need in tag, need
    for part in ("forge-methods", "forge-rack-in", "forge-stage", "forge-tool", "forge-chips",
                 "forge-info", "forge-roll", "forge-why", "forge-game", "forge-order-in",
                 "forge-foot-in", "forge-pops", "forge-say", "forge-close"):
        assert f'id="{part}"' in table_html, part
    button = re.search(r'<button[^>]*id="open-forge"[^>]*>([^<]*)</button>', table_html)
    assert button and "data-forge-open" in button.group(0) and button.group(1) == "Smithing"
    assert 'aria-controls="forge"' in button.group(0)
    herb = table_html.index('id="open-bench"')
    assert herb < table_html.index('id="open-forge"') < table_html.index('href="/craft/">Crafting bench')


def test_the_forge_scripts_load_after_the_core_in_number_order(table_html):
    """40 reads `window.BenchCore` the moment it runs and 41 and 43 read `window.Forge`:
    loaded out of order the Smithing button does nothing at all. forge.css follows
    bench.css so its few rules win where they meet."""
    order = ["js/table/29-bench-core.js", "js/table/36-bench-perks.js", "js/table/40-forge-shell.js",
             "js/table/41-forge-rack.js", "js/table/43-forge-order.js", "js/table/44-forge-ledger.js"]
    at = [table_html.index(f"/static/{p}?v=") for p in order]
    assert at == sorted(at), "the forge's scripts are out of order"
    assert table_html.index("/static/css/bench.css?v=") < table_html.index("/static/css/forge.css?v=")
    for p in order[2:]:
        assert table_html.count(f"/static/{p}?v=") == 1


def test_another_lanes_forge_file_is_named_only_once_it_exists(table_html):
    """The stage (U4) and the games (U3) are optional providers (contracts §11). A tag for
    a file not in the build is a 404 in the console on every load and fails
    test_template_scripts; a file in the build with no tag is a lane's work that never
    runs. Each is emitted exactly when the file is in play/static."""
    for path in GUARDED:
        exists = bool(finders.find(path))
        named = f"/static/{path}?v=" in table_html
        assert named == exists, f"{path}: on disk {exists}, in the page {named}"


def test_every_forge_icon_the_page_names_is_a_stamped_file(table_html):
    """The forge's engraved icons (contracts §13, downloaded by the lead) are drawn from the
    table's FORGE_ICON_URLS. A name with no file would be a broken mask, so every entry
    must be stamped (the asset tag stamps only a file it found), and every name the shell
    asks for by method must be in it, or the strip shows lettered roundels."""
    block = table_html[table_html.index("window.FORGE_ICON_URLS = {"):]
    block = block[:block.index("};")]
    urls = dict(re.findall(r'"?([a-z-]+)"?: "([^"]+)"', block))
    assert len(urls) >= 35
    for name, url in urls.items():
        assert "?v=" in url, f"{name} is not in the build"
        assert url.split("?")[0].endswith(f"/img/icons/{name}.svg"), name
    for method in ("smelt", "alloy", "forge", "quench", "temper", "fold", "hone", "assemble",
                   "finish", "strengthen", "assay"):
        assert method in urls, method


# --- the standing rules: no loop, no dash, one layer scale, motion -------------------------------

def test_nothing_in_the_forge_loops_while_it_is_idle():
    """UI plan §7.4 and §10: an idle forge draws zero frames. No forge file calls
    setInterval or requestAnimationFrame; the flight is the core's one Web Animations run
    and the games' loop is the frame's (33), alive only while a game runs."""
    for path in FORGE_JS + [CORE]:
        calls = re.findall(r"\b(setInterval|requestAnimationFrame)\s*\(", _src(path))
        assert not calls, f"{path.name} calls {calls}"
    assert "infinite" not in _src(FORGE_CSS)


def test_no_forge_string_carries_an_em_or_en_dash():
    """UI plan §8 and the design skill's §9.G: zero em-dashes and en-dashes in the forge's
    files, comments included, and in the old tab's forge card."""
    craft = _src(CRAFT)
    card = craft[craft.index("function renderForgeMoved()"):craft.index("function renderLoading()")]
    html = _src(TABLE)
    layer = html[html.index('<div id="forge"'):html.index('<div id="veil">')]
    for name, text in [(p.name, _src(p)) for p in FORGE_JS + [FORGE_CSS]] + [
            ("craft.html forge card", card), ("table.html #forge", layer)]:
        assert "—" not in text and "–" not in text, name


def test_forge_css_keeps_the_bench_layer_scale_and_motion_rules():
    """bench.css's rules, owed by forge.css too (UI plan §10, §14): z-index only orders the
    layer's own children (1 to 9; the layer's 35 and the flight's 66 are bench.css's),
    transitions are transform and opacity at 200ms or less, and no new colour enters the
    chrome: every colour is a theme token or the bench's, except the swatch's `--sw`, which
    is the server's colour for a metal (content, like heat)."""
    css = _src(FORGE_CSS)
    for z in re.findall(r"z-index:\s*(\d+)", css):
        assert 1 <= int(z) <= 9, z
    for decl in re.findall(r"transition:\s*([^;]+);", css):
        for part in decl.split(","):
            assert part.split()[0] in ("opacity", "transform"), decl
            ms = re.search(r"(\.\d+|\d+(?:\.\d+)?)s", part)
            assert ms and float(ms.group(1)) <= 0.22, decl
    body = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    hexes = set(re.findall(r"#[0-9a-fA-F]{3,6}\b", body))
    # The bench's own panel and rim greys, already in bench.css (no new colour).
    bench = set(re.findall(r"#[0-9a-fA-F]{3,6}\b", _src(STATIC / "css" / "bench.css")))
    assert hexes <= bench, f"new colours in forge.css: {sorted(hexes - bench)}"


# --- the page never computes a number (UI plan §12) ---------------------------------------------

def test_the_work_order_draws_the_servers_card_and_never_sums_it():
    """The build card's every cell, its summary line and the "rounded toward zero" final
    are the server's (`preview.card`). A sum on the page is a second answer to what the
    sword does, and two answers drift. Nothing in the forge's files adds up `pieces`,
    `bonus`, `negative` or `final`, nor rounds a modifier."""
    for path in FORGE_JS:
        code = _code(_src(path))
        for banned in (r"\.final\s*[+\-*/]", r"\.bonus\s*[+\-*/]", r"\.negative\s*[+\-*/]",
                       r"\.pieces\[[^\]]+\]\s*[+\-*/]", r"\.dc\s*[-+]", r"\.need\s*[-+]",
                       r"Math\.trunc"):
            assert not re.search(banned, code), f"{path.name} computes: {banned}"
    order = _src(TABLE_JS / "43-forge-order.js")
    assert "card.summary" in order and "r.final" in order and "card.how" in order


# --- the core: the roll moved in, and lane F's two found bugs ------------------------------------

def test_the_d20_sequence_lives_in_the_core_and_the_herb_bench_throws_through_it():
    """UI plan §3: one Esc, one trap, one clock, and now one throw of the d20. The forge is
    the second bench to roll Craft; with the ask, land and verdict copied into it the two
    would drift, as two Esc handlers would. 30 keeps only what goes on the mat."""
    core = _code(_src(CORE))
    assert "C.rollD20 = function" in core
    for step in ("dice.ask(", "dice.land(", "showVerdict(", "dice.settled"):
        assert step in core, step
    herb = _code(_src(HERB_SHELL))
    assert "C.rollD20(" in herb and "dice.ask(" not in herb and "dice.land(" not in herb
    forge = _code(_src(TABLE_JS / "40-forge-shell.js"))
    assert "C.rollD20(" in forge and "Dice3D.ask" not in forge


_NODE = r"""
const fs = require('fs'), vm = require('vm');
const corePath = process.argv[2];
class El {
  constructor(id, opts) {
    opts = opts || {};
    this.id = id || ''; this.listeners = {}; this.cls = new Set(); this.hidden = !!opts.hidden;
    this.inert = false; this.parentNode = null; this.attrs = {}; this.dataset = {}; this.style = {};
    this.innerHTML = ''; this.textContent = ''; this.removed = false; this.disabled = !!opts.disabled;
    this.tagName = opts.tag || 'DIV'; this.rects = opts.rects === undefined ? 1 : opts.rects;
    const self = this;
    this.classList = { add: (c) => self.cls.add(c), remove: (c) => self.cls.delete(c),
      contains: (c) => self.cls.has(c),
      toggle: (c, on) => { if (on === undefined) on = !self.cls.has(c); on ? self.cls.add(c) : self.cls.delete(c); return on; } };
  }
  addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); }
  removeEventListener() {}
  fire(t, e) { e = e || {}; e.target = e.target || this; e.preventDefault = () => {};
    e.stopPropagation = () => { e.stopped = true; };
    (this.listeners[t] || []).slice().forEach((f) => f(e)); return e; }
  focus() { if (!this.disabled) doc.activeElement = this; }
  contains(x) { while (x) { if (x === this) return true; x = x.parentNode; } return false; }
  closest() { return null; }
  querySelector(sel) { return (this.q || {})[sel] || null; }
  querySelectorAll() { return []; }
  appendChild(c) { c.parentNode = this; (this.kids = this.kids || []).push(c); return c; }
  insertBefore(c) { c.parentNode = this; return c; }
  remove() { this.removed = true; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  getClientRects() { return new Array(this.rects); }
  get offsetWidth() { return 1; }
}
const ids = {};
const make = (id, opts) => (ids[id] = new El(id, opts));
const body = new El('body', { tag: 'BODY' });
const doc = {
  body, activeElement: body, cookie: '', readyState: 'complete', listeners: {},
  getElementById: (id) => ids[id] || null, querySelector: () => null, querySelectorAll: () => [],
  addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); },
  removeEventListener() {}, contains: (x) => !!x && !x.removed,
  createElement: () => { const e = new El(''); e.q = { '[data-no]': new El('no'), '[data-yes]': new El('yes'), '.bench-scrim': new El('scrim') }; return e; },
  fire(t, e) { e.preventDefault = () => {}; e.stopPropagation = () => { e.stopped = true; };
    (this.listeners[t] || []).slice().forEach((f) => f(e)); return e; },
};
const games = { paused: 0, pause() { this.paused++; }, resume() {}, stop() {} };
const sandbox = { document: doc, location: { hash: '', pathname: '/play/', search: '' }, console, Math, JSON,
  Object, Array, Promise, String, Number, Date, Error, setTimeout, clearTimeout,
  history: { replaceState() {} }, localStorage: { getItem: () => null, setItem() {} },
  matchMedia: () => ({ matches: false, addEventListener() {} }), addEventListener() {}, BenchGames: games,
  fetch: () => new Promise(() => {}) };
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(corePath, 'utf8'), sandbox);
const C = sandbox.BenchCore;
const out = {};
(async () => {
  for (const id of ['f', 'f-close', 'f-pops', 'f-say']) make(id, { hidden: id === 'f' });
  let live = false;
  const h = C.mount({ layer: 'f', close: 'f-close', pops: 'f-pops', say: 'f-say', live: () => live });
  h.openLayer(new El('opener'));
  // Lane F's first found bug: a game is live, focus has fallen to <body>, Esc is pressed.
  live = true;
  doc.activeElement = body;
  const e = doc.fire('keydown', { key: 'Escape', target: body });
  out.escOnBody = { asked: games.paused, stopped: !!e.stopped, stillOpen: h.open,
                    confirm: (ids['f-pops'].kids || []).length };
  // Lane F's second: the first candidate is disabled (Roll Craft while the check answers).
  const roll = make('roll', { disabled: true });
  const next = make('next');
  const hidden = make('gone', { rects: 0 });
  doc.activeElement = body;
  h.refocus(['roll', 'gone', 'next']);
  out.refocus = doc.activeElement.id;
  doc.activeElement = body;
  h.refocus(['roll']);
  out.fallback = doc.activeElement.id;
  process.stdout.write(JSON.stringify(out));
})().catch((err) => { console.error(err && err.stack || err); process.exit(1); });
"""


@pytest.fixture(scope="module")
def core_run():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed; the behaviour checks need a JS engine")
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "forge-core.js"
        script.write_text(_NODE, encoding="utf-8")
        done = subprocess.run([node, str(script), str(CORE)], capture_output=True, text=True,
                              timeout=60)
    assert done.returncode == 0, done.stderr[:2000]
    return json.loads(done.stdout)


def test_esc_with_focus_on_the_body_still_asks_to_stop_a_game(core_run):
    """Lane F's first found bug: the core heard Esc only on the layer, so with a game live
    and the keyboard fallen to <body> (the Roll button that held it went disabled) Esc
    did nothing at all and "Stop and keep what you have?" was never asked. The document
    now hears it for the open bench: the game pauses and the confirm comes up."""
    r = core_run["escOnBody"]
    assert r["asked"] == 1 and r["stopped"] and r["stillOpen"] and r["confirm"] == 1


def test_focus_after_a_step_never_falls_to_the_body(core_run):
    """Lane F's second found bug: a finish asked the disabled Roll button to take focus,
    a disabled button refuses it, and the keyboard fell to <body>, so the next Tab began
    at the top of the page. `refocus` skips what cannot hold focus (disabled, not drawn)
    and falls back to the bench's own Close rather than to nothing."""
    assert core_run["refocus"] == "next"
    assert core_run["fallback"] == "f-close"


# --- the server's side of the page ---------------------------------------------------------------

@pytest.fixture
def forge(tmp_path, monkeypatch):
    monkeypatch.setattr(places, "has_field_kit", lambda actor: True)
    monkeypatch.setattr(places, "smithy_here", lambda scene, known=(): None)
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        forge_views._PENDING.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"), start_id="quiet-the-bread-stall")
        pc = c.scene.pc()
        pc.inventory.clear()
        pc.stock.clear()
        pc.herb_known.clear()
        pc.track("blacksmith").level = 2
        pc.purse = {"gp": 5}
        for iid in ("iron", "charcoal", "water", "ash-haft", "brass-guard"):
            pc.carry(iid, 1)
        c.save()
        yield Client()
        cm._LIVE.clear()
        forge_views._PENDING.clear()


def _post(client, url, body):
    return client.post(url, data=json.dumps(body), content_type="application/json")


def _step(client, body):
    rolled = _post(client, "/api/forge/roll", {**body, "face": 20}).json()
    assert rolled["roll"]["success"], rolled
    return _post(client, "/api/forge/finish", {"token": rolled["token"], "score": 1.0}).json()


def test_state_gives_the_page_its_swatches_place_line_and_slots(forge):
    """The page never invents a colour or a sentence about where it is: the swatch beside
    every rack row (UI plan §4), the footer's place line ("At the field kit", §5.2), each
    method's slots with Assemble's armour set beside its weapon set, and the masterwork
    rung by index for the ladder's "Superior · masterwork"."""
    s = forge.get("/api/forge/state").json()
    assert all(re.fullmatch(r"#[0-9a-f]{6}", it["color"]) for it in s["rack"])
    assert s["colors"]["iron"] == it_color(s, "iron")
    assert s["where"]["line"] == "At the field kit"
    assert [x["id"] for x in s["slots"]["forge"]] == ["metal", "fuel"]
    assert [x["id"] for x in s["slots"]["assemble"]] == ["head", "haft", "fittings"]
    assert [x["id"] for x in s["slots"]["assemble:armour"]] == ["body", "fastenings", "lining"]
    assert s["slots"]["assemble"][2]["optional"] is True
    assert s["track"]["masterwork_index"] == 3


def it_color(s, mid):
    return next(it["color"] for it in s["rack"] if it["material"] == mid)


def test_a_fitting_named_for_its_metal_takes_that_metals_swatch():
    """Seen live: the brass guard's swatch came out iron grey, because its document names
    no parent metal and the table only matched whole ids. A fitting named for its metal
    takes the longest metal id it starts with, so cold iron is not read as iron."""
    assert forge_views.material_color("brass-guard") == forge_views._COLOUR["brass"]
    assert forge_views.material_color("cold-iron-studs") == forge_views._COLOUR["cold-iron"]
    assert forge_views.material_color("iron-ore") == forge_views._COLOUR["iron"]
    assert forge_views.material_color("ash-haft") != forge_views._DEFAULT_COLOUR


def test_an_empty_assemble_answers_for_both_gears(forge):
    """Seen live: lane D's plan reads an empty Assemble as armour, so the check answered
    only Body, Fastenings and Lining, and a finished blade could not be put on the anvil
    at all ("Put a plate in the body slot." under a sword). Before a main piece the check
    answers both sets, names neither gear, and says either will do."""
    c = _post(forge, "/api/forge/check", {"method": "assemble", "slots": {}}).json()
    assert {"head", "haft", "fittings", "body", "fastenings", "lining"} <= set(c["fits"])
    assert c["gear"] == ""
    assert c["problems"][0] == "Put a blank in the head slot, or a plate in the body slot."
    assert [x["id"] for x in c["slots"]] == ["head", "haft", "fittings"]


def test_the_whole_chain_and_what_the_work_order_is_sent(forge):
    """Bars to sword through the page's own calls (forge, quench, temper, hone, assemble),
    and at each the fields the work order draws: the heat for lane U3's gauge, the build
    card at the step's ceiling, the product's name, the next step. Seen live: before the
    roll the tag read "Crude Iron Longsword" over a ladder whose ceiling was Superior,
    because an item with no quality yet was named as quality 0."""
    body = {"method": "forge", "shape": "longsword", "slots": {"metal": "inv:iron", "fuel": "inv:charcoal"}}
    c = _post(forge, "/api/forge/check", body).json()
    assert c["heat"]["band"] == [815, 1092] and c["heat"]["band_name"] == "forging"
    card = c["preview"]["card"]
    assert c["preview"]["as"] == "As the head of a longsword, at Superior"
    finals = {r["target"]: r["final"] for r in card["rows"]}
    build = {s["target"]: s["final"] for s in c["preview"]["build"]["sum"]}
    for target, final in build.items():
        assert finals[target] == forge_views._num(final, 0)
    assert "rounded toward zero" in card["how"]
    f = _step(forge, body)
    blank = f["products"][0]
    assert blank["next"] == "quench" and blank["color"]
    blank = _step(forge, {"method": "quench", "slots": {"piece": blank["key"], "quenchant": "inv:water"}})["products"][0]
    assert blank["next"] == "temper"
    blank = _step(forge, {"method": "temper", "slots": {"piece": blank["key"]}})["products"][0]
    assert blank["next"] == "hone"
    blank = _step(forge, {"method": "hone", "slots": {"piece": blank["key"]}})["products"][0]
    assert blank["next"] == "assemble"
    order = {"method": "assemble", "slots": {"head": blank["key"], "haft": "inv:ash-haft",
                                             "fittings": "inv:brass-guard"}}
    c = _post(forge, "/api/forge/check", order).json()
    assert c["gear"] == "weapon"
    assert c["product"][0]["name"] == "Iron Longsword", c["product"][0]["name"]
    assert c["heat"] is None
    done = _step(forge, order)
    sword = done["products"][0]
    assert sword["card"]["rows"] and sword["next"] == "finish"
    assert [k["slot"] for k in sword["card"]["columns"]] == ["head", "haft", "fittings"]


def test_the_place_line_names_the_smith_and_the_rate_in_coins():
    """UI plan §5.2: "At Brannoc's smithy, 1 sp an hour". The rate is the server's copper,
    said in the largest coin that says it exactly; the owner's own smithy is free."""
    class Who:
        name = "Brannoc"

    class Scene:
        people = {"n1": Who()}
        actors = {}

    class Camp:
        scene = Scene()

    town = {"smithy": {"kind": "town", "keeper": "n1", "rate_cp_per_hour": 10}, "kit": False,
            "place": "the forge"}
    assert forge_views._place_line(Camp(), town) == "At Brannoc's smithy, 1 sp an hour"
    owned = {"smithy": {"kind": "owned", "keeper": None, "rate_cp_per_hour": 0}, "kit": True}
    assert forge_views._place_line(Camp(), owned) == "At your smithy"
    assert forge_views._place_line(Camp(), {"smithy": None, "kit": False}).startswith("No forge here")
    assert forge_views._coins(3) == "3 cp" and forge_views._coins(200) == "2 gp"


def test_the_quality_perk_names_the_rung_it_reaches_once():
    """Lane U5's report: at the top of the ladder the Quality perk read "+1 to your quality
    ceiling: Flawless +1", two "+1"s for one step. It names the rung it reaches."""
    from rules import worldclass as wc

    pc = load_pc("fixtures/pc-kesst.json")
    p = pc.track("blacksmith")
    p.level = 3
    out = forge_views._track(wc.get("blacksmith"), p)
    assert out["perk_info"]["quality"]["next"] == "Your quality ceiling rises one step, to Flawless +1"


def test_an_assay_of_abysium_sickens_the_assayer_for_real(forge):
    """Lane U5's report: the view showed an assay's danger and applied nothing, so
    assaying abysium never sickened anyone, though lane E's `assay` leaves the applying to
    its caller in so many words. The danger goes through the engine as an effect, and the
    response carries the DC and the verdict the ledger card shows."""
    pc = cm.current().scene.pc()
    pc.carry("abysium-ore", 1)
    cm.current().save()
    card = forge.get("/api/forge/material/abysium-ore").json()
    assert card["assay_danger"] and card["color"] and "smiths_here" in card
    r = _post(forge, "/api/forge/assay", {"material": "abysium-ore", "face": 10}).json()
    assert r["danger"] and r["danger_applied"] is True, r
    assert "dc" in r and isinstance(r["success"], bool)
    pc = cm.current().scene.pc()
    assert pc.has_state("condition.sickened") or any(
        "sickened" in str(getattr(e, "tags", "")) or "sickened" in str(getattr(e, "name", ""))
        for e in getattr(pc, "effects", []) or []), "the assayer was not sickened"


def test_a_friendly_smith_teaches_a_metal_for_a_fee(forge):
    """UI plan §6.7, "Ask a smith": the herb bench's Ask for metals, through lane E's
    lesson path. Somebody here whose words say smith is named on the card; asked, a
    friendly one tells properties, dangers first, for the lore's fee."""
    from rules.bestiary import instantiate

    c = cm.current()
    smith = instantiate("guildhand", scene=c.scene, name="the blacksmith")
    c.scene.add(smith)
    c.engine().settle_attitude(smith, "friendly")
    c.save()
    card = forge.get("/api/forge/material/iron").json()
    assert [t["ref"] for t in card["smiths_here"]] == [smith.ref]
    d = _post(forge, "/api/forge/ask", {"material": "iron", "ref": smith.ref}).json()
    assert d["refused"] == "" and d["revealed"] and d["paid"] == "2 sp", d
    nobody = _post(forge, "/api/forge/ask", {"material": "iron", "ref": "nobody"})
    assert nobody.status_code == 400


# --- the old tab (lane U7) -----------------------------------------------------------------------

def test_the_old_blacksmithing_tab_is_a_card_that_opens_the_forge():
    """UI plan §15 U7: /craft/'s Blacksmithing tab stops drawing the old shelf, chain and
    cauldron and becomes one card with one way to the forge over the table."""
    src = _src(CRAFT)
    sel = src[src.index("async function selectCraft("):src.index("function renderHerbalismMoved()")]
    assert 'if (CRAFT === "blacksmithing") { renderForgeMoved(); return; }' in sel
    card = src[src.index("function renderForgeMoved()"):src.index("function renderLoading()")]
    assert 'href="/play/#forge"' in card and "Open the forge" in card


def test_choosing_a_tab_never_shows_the_last_tabs_card_while_it_loads():
    """The audit's defect (UI plan §2): choosing Blacksmithing showed "Herbalism is at the
    table now" for about two seconds, because #main kept the last tab's card while the
    shelf was fetched. The tab draws its own loading panel BEFORE it awaits, and an answer
    for a tab no longer in front is dropped rather than drawn over the newer one."""
    src = _src(CRAFT)
    sel = src[src.index("async function selectCraft("):src.index("function renderHerbalismMoved()")]
    assert sel.index("renderLoading();") < sel.index("await Promise.all(")
    assert "const seq = ++CRAFT_SEQ;" in sel and "if (seq !== CRAFT_SEQ) return;" in sel
