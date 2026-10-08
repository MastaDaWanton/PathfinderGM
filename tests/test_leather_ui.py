"""The leather bench's page (docs/leatherworking-ui-plan.md §5, §6, §12; contracts §11 row U1
and §11.1; leatherworking lane U1).

The bench is the fifth over the table, mounted on the bench core (29-bench-core.js) and built
FLAT FIRST, as the forge, the circle and the alchemy bench were: fully playable with no 3D
stage (lane U4), no games (lane U3) and no ledger (lane U5), each looked up when needed and
named in the page only once it is in the build. The contracts' file numbers (45-48, 50) were
taken by the enchanting circle and the alchemy bench, so this lane's files are 55, 56 and 58,
with 57 left for lane U4's stage and 59 for lane U2's harvest sheet.

These tests hold what the lane measured going wrong while it was built, live on scratch data
at 1600x900, 1280x720 and 375x812 (2026-10-08: a green deer hide salted, fleshed and bark-
tanned in Zhilgoroth's tannery, waited for and collected; deer leather bought at the town's
leatherworker cut, hardened in the field kit's kettle, laced and assembled into leather
armour and worn; boots cut, stitched and assembled; keyboard only from the door to "Next:
Flense"), the rules every bench keeps (no loop while idle, no dash, one layer scale,
transform and opacity only, the page never computes a number), and the secrets that must not
be drawn.
"""
from __future__ import annotations

import json
import re
import sys
import types
from pathlib import Path

import pytest
from django.contrib.staticfiles import finders
from django.test import Client, override_settings

from play import campaign as cm
from play import leather_views
from rules import leatherworker as lw
from rules.sheet import load_pc

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "play" / "static"
TABLE_JS = STATIC / "js" / "table"
SHELL = TABLE_JS / "55-leather-shell.js"
RACK = TABLE_JS / "56-leather-rack.js"
ORDER = TABLE_JS / "58-leather-order.js"
FORGE_ORDER = TABLE_JS / "43-forge-order.js"
OURS = [SHELL, RACK, ORDER]
CSS = STATIC / "css" / "leather.css"
TABLE = ROOT / "play" / "templates" / "play" / "table.html"
ICONS = STATIC / "img" / "icons"
LICENCES = ROOT / "docs" / "asset-licences.md"

GAMES = ("00-kit", "flense", "salt", "tan", "curry", "cut", "stitch", "harden", "tool", "dye", "laminate",
         "assemble", "harvest", "cut-test")
STAGE = ("00-hide", "01-props", "02-pieces", "03-yard", "04-fx")
# Other lanes' files the table names only once they are in the build (contracts §11).
GUARDED = (["css/leather-games.css", "js/table/57-leather-stage.js", "js/table/59-harvest.js"]
           + [f"js/leather-games/{m}.js" for m in GAMES]
           + [f"js/tannery-stage/{f}.js" for f in STAGE])
ICON_NAMES = ("flense", "salt", "tan", "curry", "cut", "stitch", "harden", "stamp", "dye", "dye-pot",
              "laminate", "grade", "leather-armour", "hide", "leather-roll", "panel", "lacing",
              "thread", "cloak", "boots")


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _code(text: str) -> str:
    """JS with its comments taken out, so a rule is tested against what runs."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(re.sub(r"(^|\s)//.*$", "", line) for line in text.splitlines())


@pytest.fixture(scope="module")
def table_html():
    return Client().get("/play/").content.decode("utf-8")


# --- the layer and the ways in ---------------------------------------------------------------

def test_the_table_serves_the_leather_layer_and_its_door(table_html):
    """UI plan §5.1: the bench opens over the table as its own dialog, served in the page so
    closing is instant, from a Leatherwork door after Alchemy. 37 places In progress after
    the doors it knows and 50 moves it after Alchemy, which left it between Alchemy and
    Leatherwork until 55 moved it again (the left column measured live, 2026-10-08:
    Herbalism, Smithing, Enchanting, Alchemy, Leatherwork, In progress)."""
    tag = re.search(r'<div id="leather"[^>]*>', table_html)
    assert tag, "the table has no #leather layer"
    for need in ('role="dialog"', 'aria-modal="true"', "hidden", 'aria-labelledby="leather-title"',
                 'class="bench leather"'):
        assert need in tag.group(0), need
    for part in ("leather-methods", "leather-rack-in", "leather-stage", "leather-tool",
                 "leather-chips", "leather-info", "leather-roll", "leather-why", "leather-game",
                 "leather-order-in", "leather-foot-in", "leather-pops", "leather-say",
                 "leather-close"):
        assert f'id="{part}"' in table_html, part
    door = re.search(r'<button[^>]*id="open-leather"[^>]*>([^<]*)</button>', table_html)
    assert door and "data-leather-open" in door.group(0) and door.group(1) == "Leatherwork"
    assert 'aria-controls="leather"' in door.group(0) and "v2-btn door" in door.group(0)
    assert (table_html.index('id="open-alchemy"') < table_html.index('id="open-leather"')
            < table_html.index('href="/craft/">Crafting bench'))
    code = _code(_src(SHELL))
    assert '$id("open-works")' in code and "insertBefore(works, mine.nextSibling)" in code
    assert 'location.hash === "#leather"' in code


def test_the_bench_scripts_load_after_the_core_in_number_order(table_html):
    """55 reads `window.BenchCore` (and 43's `BuildCard`) the moment it runs, and 56 and 58
    read `window.Leather`: loaded out of order the Leatherwork door does nothing. leather.css
    follows bench.css, forge.css (whose slots, swatch and build card it reuses), enchant.css
    and alchemy.css."""
    order = ["js/table/29-bench-core.js", "js/table/37-works.js", "js/table/43-forge-order.js",
             "js/table/53-alchemy-card.js", "js/table/55-leather-shell.js",
             "js/table/56-leather-rack.js", "js/table/58-leather-order.js"]
    at = [table_html.index(f"/static/{p}?v=") for p in order]
    assert at == sorted(at), "the bench's scripts are out of order"
    for p in order[4:]:
        assert table_html.count(f"/static/{p}?v=") == 1
    css = [table_html.index(f"/static/css/{n}.css?v=") for n in ("bench", "forge", "enchant", "alchemy", "leather")]
    assert css == sorted(css)


def test_another_lanes_leather_file_is_named_only_once_it_exists(table_html):
    """The games (U3), the stage (U4) and the harvest sheet (U2) are optional providers
    (contracts §11.1). A tag for a file not in the build is a 404 on every load; a file in the
    build with no tag is a lane's work that never runs. Each is emitted exactly when the file
    is in play/static, so the lead's merge needs no edit here. The games load before 33 reads
    the registry, the stage parts before 55, the adapter 57 between 56 and 58."""
    for path in GUARDED:
        exists = bool(finders.find(path))
        named = f"/static/{path}?v=" in table_html
        assert named == exists, f"{path}: on disk {exists}, in the page {named}"
    html = _src(TABLE)
    assert (html.index("js/tannery-stage/00-hide.js") < html.index("js/table/55-leather-shell.js")
            < html.index("js/table/56-leather-rack.js") < html.index("js/table/57-leather-stage.js")
            < html.index("js/table/58-leather-order.js") < html.index("js/table/59-harvest.js"))
    assert (html.index("js/leather-games/00-kit.js") < html.index("js/leather-games/flense.js")
            < html.index("js/table/33-bench-games.js"))


# --- the icons (game-icons.net, CC BY 3.0, approved for these benches) -------------------------

def test_every_leather_icon_is_on_disk_credited_and_from_game_icons():
    """20 icons downloaded from game-icons.net (CC BY 3.0). Each name in the table's registry
    has its file (named as the registry names it), its source in _sources.json (the icon's own
    game-icons.net page) and a row in docs/asset-licences.md; the manual's credit line names
    the leather bench. All 20 are Lorc's and Delapouite's, artists already credited."""
    reg = re.search(r"window\.LEATHER_ICON_URLS = \{(.*?)\};", _src(TABLE), re.S).group(1)
    names = re.findall(r"\"?([\w-]+)\"?: \"\{% asset 'img/icons/([\w-]+)\.svg' %\}\"", reg)
    assert sorted(a for a, _ in names) == sorted(ICON_NAMES) and all(a == b for a, b in names)
    sources = json.loads(_src(ICONS / "_sources.json"))
    lic = _src(LICENCES)
    for name in ICON_NAMES:
        svg = _src(ICONS / f"{name}.svg")
        assert svg.startswith("<svg") and "<script" not in svg and "href" not in svg, name
        assert sources[name]["url"].startswith("https://game-icons.net/1x1/"), name
        assert sources[name]["author"] in ("lorc", "delapouite"), name
        assert f"`play/static/img/icons/{name}.svg`" in lic, name
    assert "leather bench icons" in _src(ROOT / "play" / "templates" / "play" / "manual.html")


# --- the providers ----------------------------------------------------------------------------

def test_a_game_runs_only_when_it_is_registered_for_this_craft():
    """BenchGameDefs is one registry keyed by method for every bench, and the forge already
    holds "assemble": a leather Assemble registered under the same key would have replaced the
    smith's. Lane U3 registers under "leather.<method>" (`LeatherGames.key`, the cut test
    `LeatherGames.cutTest`); the shell runs a game only with `track: "leather"`, hands it the
    server's band as `opts.band` (contracts §11.1) and the stage's view of it, and otherwise
    finishes the step flat at the middle of the range, saying so in words."""
    code = _code(_src(SHELL))
    assert 'def.track === "leather"' in code and "LG.key(method)" in code and "LG.cutTest" in code
    assert 'stageCall("game", method, { band:' in code
    assert "band: r.band || tuning.band" in code
    assert "score: 0.5" in code and "flat: true" in code
    assert "No game for this step in this build" in _src(ORDER)


def test_the_stage_is_asked_for_and_never_required():
    """Contracts §11.1: `window.TanneryStage`, `available()` false without WebGL. Mounted only
    when it says it is available; otherwise the method's icon at 160px beside a CSS gauge of
    the server's band, the target outlined and the failing band hatched, positioned by calc()
    over the server's own numbers."""
    code = _code(_src(SHELL))
    assert "window.TanneryStage" in code and "s.available()" in code
    assert "bench-flat leather-flat" in code and "size: 160" in code
    assert "L.check.band" in code and '"--max:"' in code
    for call in ("setScene", "setTool", "setWork", "game", "flourish", "productRect", "reducedMotion"):
        assert f'"{call}"' in code or f".{call}(" in code, call
    css = _src(CSS)
    assert "calc(var(--lo) / var(--max) * 100%)" in css and "repeating-linear-gradient" in css


def test_the_ledger_and_card_are_lane_u5s_with_flat_stand_ins_without_them():
    """Contracts §11.1: `MaterialLedger.card(track, materialId, anchorEl)` and
    `.journal(host, track)`. Without lane U5's file the rack's "?" opens a flat card (what is
    known, Grade, Ask a tanner) and the footer's Ledger a flat list, so Grade is never out of
    reach; the forge's assay without its ledger had no way in at all."""
    code = _code(_src(SHELL))
    assert 'M.card("leatherworker", mid, el, {' in code and "M.journal" in code
    assert '$id("jr-hides")' in code
    assert '"/api/leather/ledger"' in code and '"/api/leather/material/"' in code
    assert '"/api/leather/grade"' in code and '"/api/leather/ask"' in code


def test_the_build_card_is_the_forges_one_card():
    """Contracts §11.1: the forge's card exported as `window.BuildCard.open(card, anchor)` and
    drawn by both benches, from the same server shape. Its masterwork line is the book's +1 to
    attack for a forged weapon; for the leather card (which carries `by_nature`) it says only
    that the book's masterwork applies, since leather is armour and worn goods."""
    forge = _code(_src(FORGE_ORDER))
    assert "window.BuildCard = {" in forge and "open: function (card, anchor)" in forge
    assert '"by_nature" in card' in forge
    order = _code(_src(ORDER))
    assert "BuildCard.open(got.card, b)" in order


def test_the_perk_picker_learns_the_leatherworkers_four():
    """36-bench-perks.js knows four tracks and is no lane's file this wave: the leatherworker's
    row (the forge's four with Yield at the harvest, owner Q6.3) is registered by 55 at load,
    posting to lane E's route."""
    code = _code(_src(SHELL))
    assert "BenchPerks.tracks.leatherworker = {" in code and '"/api/leather/perks"' in code
    for perk in ("potency", "hardening", "quality", "yield"):
        assert f'id: "{perk}"' in code, perk


# --- what was measured live -------------------------------------------------------------------

def test_a_long_wait_is_asked_first():
    """Seen live, 2026-10-08: one press of Wait for it over a three-week bark tannage passed 21
    days in a breath; the scratch character died of thirst in it twice (the second time with
    forty waterskins, which a wait does not drink from), and the result read only "You waited
    21 days. You take the leather out of the vat". A wait of a day or more now asks first, and
    the question promises nothing the server does not do."""
    code = _code(_src(SHELL))
    assert "Number(minutes) >= 1440" in code and "L.confirm({" in code
    assert "Hunger, thirst and sleep run their course while you wait." in code
    assert "data-wait-min" in _src(ORDER)


def test_the_strip_and_the_footer_never_push_the_layer_off_the_window():
    """Two layout defects measured live (2026-10-08). With no kit and no tannery all twelve
    methods were locked with the same reason under each name, and the strip wrapped into a
    second row that hung over the rack and the work order; at 1280x720 the footer's place
    line ("At the field kit: common and uncommon hides, and its small kettle") was the
    footer's min-content and made the layer 1354px wide, Close and the work order 74px off the
    window (1286 with the footer hidden, the bench clasps' own 6px). The strip does not wrap, a
    lock every method shares is said once, and the footer may be narrower than its line."""
    css = re.sub(r"/\*.*?\*/", "", _src(CSS), flags=re.S)
    methods = " ".join(re.findall(r"\.bench-methods\s*\{([^}]*)\}", css))
    assert "flex-wrap: wrap" not in methods and "flex-wrap: nowrap" in methods
    assert ".leather .bench-foot { min-width: 0; }" in css
    code = _code(_src(SHELL))
    assert "L.sharedLock = function" in code and "!shared" in code


def test_cut_names_the_hide_a_pattern_takes_and_not_assembles_dc():
    """Seen live: "Leather Armour, 2 units, DC 12" in What to cut above Cut's own "DC 10, you
    need 7 or better": the book DC is Assemble's, and the picker said two DCs for one step."""
    order = _code(_src(ORDER))
    picker = order[order.index("function patternHtml"):order.index("function hairHtml")]
    assert "p.body_words" in picker and "p.dc" not in picker


def test_a_card_opens_from_the_question_mark_only():
    """The owner's emergency fix of 2026-10-08: a card opened by hovering or focusing a whole
    row covered the rows under it and made the list unusable. The rack opens a material's card
    from its "?" button and from nothing else."""
    code = _code(_src(RACK))
    assert 'e.target.closest(".bt-info")' in code and "L.openCard(info.dataset.material, info)" in code
    for ev in ("mouseover", "mouseenter", "pointerenter"):
        assert f'"{ev}"' not in code, ev
    assert "peek" not in code


# --- the secrets --------------------------------------------------------------------------------

def test_an_unknown_property_is_a_count_and_the_creature_lines_are_not_drawn():
    """A hidden secret never reaches the page through this lane's files: the flat card draws
    the KNOWN properties and only a count of the rest (lane E's unknown rows carried a
    `group`, "armour" or "working", which said what Grade had not found; lane U5 blanked them
    on build/leatherworking, and this page never read it either way), and the build card's
    "from the creature" lines (a generic hide's inherited resistance, learned by Grade) are
    never drawn."""
    shell, order = _code(_src(SHELL)), _code(_src(ORDER))
    assert "filter(function (p) { return p.known; })" in shell
    assert ".group" not in shell.replace("it.group", "").replace("s.group", "")
    assert "from_creature" not in shell + order + _code(_src(FORGE_ORDER))


# --- the standing rules -----------------------------------------------------------------------

def test_nothing_in_the_bench_loops_while_it_is_idle():
    """UI plan §7.4: an idle bench draws zero frames. None of this lane's files calls
    setInterval or requestAnimationFrame; the games' loop is the frame's (33) and the stage's
    is lane U4's own."""
    for path in OURS:
        calls = re.findall(r"\b(setInterval|requestAnimationFrame)\s*\(", _src(path))
        assert not calls, f"{path.name} calls {calls}"
    assert "infinite" not in _src(CSS)


def test_no_leather_string_carries_an_em_or_en_dash():
    """UI plan §8 and §15: zero em-dashes and en-dashes in this lane's files, comments included,
    and in the #leather layer's markup."""
    html = _src(TABLE)
    layer = html[html.index('<div id="leather"'):html.index('<div id="veil">')]
    for name, text in [(p.name, _src(p)) for p in OURS + [CSS]] + [("table.html #leather", layer)]:
        assert "—" not in text and "–" not in text, name


def test_leather_css_keeps_the_bench_layer_scale_and_motion_rules():
    """bench.css's rules (UI plan §10, §15): z-index 1 to 9 inside the layer, transitions
    transform and opacity at 200ms or less, and no new colour in the chrome. A hide's colour is
    content and reaches the page only as `--sw` from the server."""
    css = _src(CSS)
    for z in re.findall(r"z-index:\s*(\d+)", css):
        assert 1 <= int(z) <= 9, z
    for decl in re.findall(r"transition:\s*([^;]+);", css):
        for part in decl.split(","):
            assert part.split()[0] in ("opacity", "transform"), decl
            ms = re.search(r"(\.\d+|\d+(?:\.\d+)?)s", part)
            assert ms and float(ms.group(1)) <= 0.22, decl
    body = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    hexes = set(re.findall(r"#[0-9a-fA-F]{3,6}\b", body))
    bench = set(re.findall(r"#[0-9a-fA-F]{3,6}\b", _src(STATIC / "css" / "bench.css")))
    assert hexes <= bench, f"new colours in leather.css: {sorted(hexes - bench)}"
    assert "rgb(" not in body.replace("rgba(", "")


def test_the_page_draws_the_servers_numbers_and_never_sums_them():
    """Every figure on the bench is the server's: the DC and its terms, the face needed, hide
    units, grades and caps, the clock, the wait, the rents, the band and the build. Nothing in
    this lane's files does arithmetic on them (the grade notches are a lookup, the band gauge
    is laid out by CSS calc() over the server's numbers)."""
    op = r"\s*(?:[-*/]|\+(?!\s*[\"']))"
    for path in OURS:
        code = _code(_src(path))
        for field in ("dc", "need", "bonus", "grade", "grade_cap", "hours_left", "waits", "minute",
                      "rent_cp", "vat_rent_cp", "units", "quarters", "mp", "ready_day", "unknown"):
            assert not re.search(r"\." + field + r"\b" + op, code), f"{path.name} computes with .{field}"
        assert not re.search(r"Math\.(floor|ceil|trunc|round)\([^)]*\.(dc|grade|units|hours_left)", code), path.name
        assert "255" not in code and "rgb(" not in code, path.name


# --- the server's side: what the page reads ---------------------------------------------------

@pytest.fixture
def bench(tmp_path, monkeypatch):
    from rules import places

    monkeypatch.setattr(places, "leather_bench_here", lambda scene, actor, known=(): {
        "at": "field", "tannery": None, "field_kit": True, "tiers": ("common", "uncommon"),
        "vats": False})
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        leather_views._PENDING.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"), start_id="quiet-the-bread-stall")
        pc = c.scene.pc()
        pc.inventory.clear()
        pc.stock.clear()
        pc.herb_known.clear()
        lw.put_hide(pc, lw.make_hide("deer-hide", form="green", harvested_at=c.scene.clock_minutes))
        pc.carry("curing-salt", 2)
        c.save()
        yield Client()
        cm._LIVE.clear()
        leather_views._PENDING.clear()


def post(client, url, body):
    return client.post(url, data=json.dumps(body), content_type="application/json")


def test_the_state_carries_what_the_rack_and_the_order_draw(bench):
    """Every word and number the page draws is in the state: a green hide's clock in words and
    hours (the eight-segment strip is lit from `hours_left`), its units and grade in words, its
    swatch as a colour string, each method's lock in words, each method's slots with what goes
    in them, the patterns with the hide their body and lining take, and `conversions`."""
    st = bench.get("/api/leather/state").json()
    green = next(r for r in st["rack"] if r["form"] == "green")
    assert green["clock"]["clock"] is True and green["clock"]["hours_left"] == 48
    assert green["clock"]["why"].startswith("spoils in") and green["units_words"] == "1 unit"
    assert green["grade_words"] == "grade 2" and re.fullmatch(r"#[0-9a-f]{6}", green["color"])
    assert [m["id"] for m in st["methods"]][:3] == ["flense", "salt", "tan"]
    assert all("lock_reason" in m for m in st["methods"])
    assert [s["id"] for s in st["slots"]["salt"]] == ["hide", "salt"]
    cloak = next(p for p in st["products"] if p["id"] == "cloak")
    assert cloak["body_words"] and "lining_units" in cloak
    assert st["conversions"] == [] or isinstance(st["conversions"], list)


def test_the_check_sends_the_band_the_flat_gauge_draws(bench):
    """The flat stage's gauge reads `check.band` (unit, start, target, failing band): Salt's
    is percent coverage, 25 to 100, with no failing band."""
    st = bench.get("/api/leather/state").json()
    hide = next(r["key"] for r in st["rack"] if r["form"] == "green")
    salt = next(r["key"] for r in st["rack"] if r["form"] == "salt")
    ch = post(bench, "/api/leather/check", {"method": "salt", "slots": {"hide": hide, "salt": salt}}).json()
    assert ch["can_roll"] and ch["band"]["unit"] == "percent" and ch["band"]["target"] == [25, 100]


def test_a_carried_manual_has_a_door_on_the_bench(bench):
    """Lane E's POST api/leather/manual read a leatherworking manual, and nothing on any page
    called it: a manual bought at the leatherworker's counter could not be read at all. The
    state lists the leatherworking manuals carried and the footer's Manuals button reads one."""
    pc = cm.current().scene.pc()
    pc.goods["The Tanner's Yard Book"] = 1          # as a handover leaves it (`holds_manual`)
    cm.current().save()
    st = bench.get("/api/leather/state").json()
    if not st["manuals"]:
        pytest.skip("no leatherworking manual rows in this build")
    book = st["manuals"][0]
    assert book["read"] is False and book["hours"] >= 1
    r = post(bench, "/api/leather/manual", {"item": book["id"]})
    assert r.status_code == 200, r.content[:300]
    assert bench.get("/api/leather/state").json()["manuals"][0]["read"] is True
    code = _code(_src(SHELL))
    assert "data-leather-manuals" in code and '"/api/leather/manual"' in code


def test_the_conversion_notice_is_shown_once_through_the_bench(bench, monkeypatch):
    """Lanes I and W convert old leatherwork (owner Q9.1) and the bench says what they did,
    once: the state carries `conversions` and POST api/leather/seen marks a line seen through
    `leather_migration.conversion_seen`. On a tree without the conversion the route says so
    (501) rather than pretending to have marked it."""
    import importlib.util

    from django.urls import resolve

    assert resolve("/api/leather/seen").func is leather_views.leather_seen
    if importlib.util.find_spec("rules.leather_migration") is None:
        assert bench.get("/api/leather/state").json()["conversions"] == []
        assert post(bench, "/api/leather/seen", {"key": "x"}).status_code == 501
    seen = []
    fake = types.ModuleType("rules.leather_migration")
    # The rest of the real module stays: lanes I+W hook it into every save
    # (`sheet.to_dict` -> `stamp_save`), so a fake with only the two notice functions made
    # the seen POST answer 500 once they were merged (measured 2026-10-08).
    if importlib.util.find_spec("rules.leather_migration") is not None:
        import importlib as _il

        fake.__dict__.update({k: v for k, v in vars(_il.import_module(
            "rules.leather_migration")).items() if not k.startswith("__")})
    fake.conversions = lambda pc: [{"key": "note", "name": "Your leatherwork, on the new bench",
                                    "seen": "note" in seen, "changes": ["Now Leatherworker 2"]}]
    fake.conversion_seen = lambda pc, key=None: seen.append(key)
    monkeypatch.setitem(sys.modules, "rules.leather_migration", fake)
    import rules

    monkeypatch.setattr(rules, "leather_migration", fake, raising=False)
    assert bench.get("/api/leather/state").json()["conversions"][0]["seen"] is False
    r = post(bench, "/api/leather/seen", {"key": "note"})
    assert r.status_code == 200 and seen == ["note"] and r.json()["conversions"][0]["seen"] is True
    code = _code(_src(SHELL))
    assert '"/api/leather/seen"' in code and "showConversions" in code
