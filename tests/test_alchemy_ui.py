"""The alchemy bench's page (docs/alchemy-ui-plan.md §5, §6, §12; contracts §11 row U1, §12;
alchemy lane U1).

The bench is the fourth over the table, mounted on the bench core (29-bench-core.js) and
built FLAT FIRST, as the forge and the circle were: fully playable with no 3D stage (lane
U3), no games (lane U2) and no books (lane U4), each looked up when needed and named in the
page only once it is in the build. These tests hold what the lane measured going wrong
while it was built, live on scratch data at 1600x900 (2026-10-07: a cure light wounds
potion found by experiment, bottled, waited for, collected and drunk; alchemist's fire in
two steps; quicksilver assayed bare-handed; two hours of distilling paid for in Mirabalos's
laboratory), the rules every bench keeps (no loop while idle, no dash, one layer scale,
transform and opacity only, the page never computes a number), the secrets that must never
leave the server, and the old /craft/ tab's chain, retired so there is one way to brew.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from django.contrib.staticfiles import finders
from django.test import Client, override_settings

from play import alchemy_views
from play import campaign as cm
from rules.sheet import load_pc

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "play" / "static"
TABLE_JS = STATIC / "js" / "table"
SHELL = TABLE_JS / "50-alchemy-shell.js"
SHELF = TABLE_JS / "51-alchemy-shelf.js"
CARD = TABLE_JS / "53-alchemy-card.js"
OURS = [SHELL, SHELF, CARD]
CSS = STATIC / "css" / "alchemy.css"
TABLE = ROOT / "play" / "templates" / "play" / "table.html"
CRAFT = ROOT / "play" / "templates" / "play" / "craft.html"
ICONS = STATIC / "img" / "icons"
LICENCES = ROOT / "docs" / "asset-licences.md"

GAMES = ("dissolve", "calcine", "filter", "distill", "react", "sublime", "bottle", "transmute")
STAGE = ("00-glass", "01-apparatus", "02-liquid", "03-lab", "04-fx")
# Other lanes' files the table names only once they are in the build (contracts §11, §12).
GUARDED = (["css/alchemy-games.css", "js/table/52-alchemy-stage.js", "js/table/54-alchemy-books.js"]
           + [f"js/alchemy-games/{m}.js" for m in GAMES]
           + [f"js/alchemy-stage/{f}.js" for f in STAGE])


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

def test_the_table_serves_the_alchemy_layer_and_its_door(table_html):
    """UI plan §5.1: the bench opens over the table as its own dialog, served in the page so
    closing is instant, from an Alchemy door after Enchanting and before In progress. 37
    places its In progress door after the doors it knows (Herbalism, Smithing, Enchanting),
    which put it between Enchanting and Alchemy until 50 moved it (seen on the first load,
    2026-10-07: the left column read Enchanting, In progress, Alchemy)."""
    tag = re.search(r'<div id="alchemy"[^>]*>', table_html)
    assert tag, "the table has no #alchemy layer"
    for need in ('role="dialog"', 'aria-modal="true"', "hidden", 'aria-labelledby="alchemy-title"',
                 'class="bench alchemy"'):
        assert need in tag.group(0), need
    for part in ("alchemy-methods", "alchemy-shelf-in", "alchemy-stage", "alchemy-tool",
                 "alchemy-chips", "alchemy-info", "alchemy-lines", "alchemy-roll", "alchemy-why",
                 "alchemy-game", "alchemy-card-in", "alchemy-foot-in", "alchemy-pops",
                 "alchemy-say", "alchemy-close"):
        assert f'id="{part}"' in table_html, part
    door = re.search(r'<button[^>]*id="open-alchemy"[^>]*>([^<]*)</button>', table_html)
    assert door and "data-alchemy-open" in door.group(0) and door.group(1) == "Alchemy"
    assert 'aria-controls="alchemy"' in door.group(0) and "v2-btn door" in door.group(0)
    assert (table_html.index('id="open-enchant"') < table_html.index('id="open-alchemy"')
            < table_html.index('href="/craft/">Crafting bench'))
    code = _code(_src(SHELL))
    assert '$id("open-works")' in code and "insertBefore(works, mine.nextSibling)" in code


def test_the_bench_scripts_load_after_the_core_in_number_order(table_html):
    """50 reads `window.BenchCore` the moment it runs, and 51 and 53 read `window.Alchemy`:
    loaded out of order the Alchemy door does nothing. alchemy.css follows bench.css,
    forge.css (whose swatch rule it reuses) and enchant.css."""
    order = ["js/table/29-bench-core.js", "js/table/37-works.js", "js/table/44-forge-ledger.js",
             "js/table/48-enchant-working.js", "js/table/50-alchemy-shell.js",
             "js/table/51-alchemy-shelf.js", "js/table/53-alchemy-card.js"]
    at = [table_html.index(f"/static/{p}?v=") for p in order]
    assert at == sorted(at), "the bench's scripts are out of order"
    for p in order[4:]:
        assert table_html.count(f"/static/{p}?v=") == 1
    css = [table_html.index(f"/static/css/{n}.css?v=") for n in ("bench", "forge", "enchant", "alchemy")]
    assert css == sorted(css)


def test_another_lanes_alchemy_file_is_named_only_once_it_exists(table_html):
    """The games (U2), the stage (U3) and the books (U4) are optional providers (contracts
    §11, "flat fallback if absent"). A tag for a file not in the build is a 404 on every
    load; a file in the build with no tag is a lane's work that never runs. Each is emitted
    exactly when the file is in play/static, so the lead's merge needs no edit here."""
    for path in GUARDED:
        exists = bool(finders.find(path))
        named = f"/static/{path}?v=" in table_html
        assert named == exists, f"{path}: on disk {exists}, in the page {named}"
    html = _src(TABLE)
    assert (html.index("js/alchemy-stage/00-glass.js") < html.index("js/table/50-alchemy-shell.js")
            < html.index("js/table/52-alchemy-stage.js") < html.index("js/table/53-alchemy-card.js")
            < html.index("js/table/54-alchemy-books.js"))
    assert html.index("js/alchemy-games/dissolve.js") < html.index("js/table/33-bench-games.js")


# --- the icons (owner's approval 2026-10-06, open point 11) -----------------------------------

def test_every_alchemy_icon_is_on_disk_credited_and_from_game_icons():
    """22 icons downloaded from game-icons.net (CC BY 3.0). Each name in the table's
    registry has its file, its source in _sources.json (game-icons.net's own page) and a
    row in docs/asset-licences.md; its one new artist is credited in the manual too."""
    reg = re.search(r"window\.ALCHEMY_ICON_URLS = \{(.*?)\};", _src(TABLE), re.S).group(1)
    names = re.findall(r"(\w+): \"\{% asset 'img/icons/(\w+)\.svg' %\}\"", reg)
    assert len(names) == 22 and all(a == b for a, b in names)
    sources = json.loads(_src(ICONS / "_sources.json"))
    lic = _src(LICENCES)
    for name, _ in names:
        svg = _src(ICONS / f"{name}.svg")
        assert svg.startswith("<svg") and "<script" not in svg and "href" not in svg, name
        assert sources[name]["url"].startswith("https://game-icons.net/1x1/"), name
        assert f"`play/static/img/icons/{name}.svg`" in lic, name
    assert "DarkZaitzev" in lic and "DarkZaitzev" in _src(ROOT / "play" / "templates" / "play" / "manual.html")


# --- the providers ----------------------------------------------------------------------------

def test_a_game_runs_only_when_it_is_registered_for_this_craft():
    """BenchGameDefs is one registry keyed by method name for every bench; the bench must
    not run another craft's game for its own step. The shell asks for `track: "alchemy"`,
    hands the game the server's gauges exactly as sent (heat, reaction, stages), and
    otherwise finishes the step flat at the middle of the range, saying so in words."""
    code = _code(_src(SHELL))
    assert 'def.track !== "alchemy"' in code
    assert "score: 0.5" in code and "flat: true" in code
    for g in ("heat: tuning.heat", "reaction: tuning.reaction", "stages: tuning.stages"):
        assert g in code, g
    assert "No game for this step in this build" in _src(CARD)


def test_the_stage_is_asked_for_and_never_required():
    """Contracts §12: `window.AlchemyStage`, `available()` false without WebGL. Mounted only
    when it says it is available; otherwise the method's icon at 160px with a level bar in
    the server's colour, level and words (UI plan §6.3)."""
    code = _code(_src(SHELL))
    assert "window.AlchemyStage" in code and "s.available()" in code
    assert "bench-flat alchemy-flat" in code and "size: 160" in code
    assert "liq.css" in code and "liq.words" in code and '"--lv"' in code
    for call in ("setScene", "setTool", "setVessel", "liquid", "game", "flourish", "productRect",
                 "reducedMotion"):
        assert f'"{call}"' in code or f".{call}(" in code, call


def test_the_books_are_lane_u4s_with_a_flat_list_without_them():
    """Contracts §12: `AlchemyBooks.card / .formulary / .codex`, with lane U4's options (the
    row's hazards, where you stand, the popover host, `after`); without the file the footer's
    Formulary and Codex open plain lists from the server's routes."""
    code = _code(_src(SHELL))
    assert "window.AlchemyBooks" in code and "B.card(materialId, el," in code
    assert "hazards:" in code and "after: afterBook" in code
    assert '"/api/alchemy/formulary"' in code and '"/api/alchemy/codex"' in code


# --- the standing rules -----------------------------------------------------------------------

def test_nothing_in_the_bench_loops_while_it_is_idle():
    """UI plan §7.6: an idle bench draws zero frames. None of this lane's files calls
    setInterval or requestAnimationFrame; the games' loop is the frame's (33) and the
    stage's is lane U3's own."""
    for path in OURS:
        calls = re.findall(r"\b(setInterval|requestAnimationFrame)\s*\(", _src(path))
        assert not calls, f"{path.name} calls {calls}"
    assert "infinite" not in _src(CSS)


def test_no_alchemy_string_carries_an_em_or_en_dash():
    """UI plan §8 and §14: zero em-dashes and en-dashes in this lane's files, comments
    included, in the #alchemy layer's markup and in the old tab's card."""
    craft = _src(CRAFT)
    card = craft[craft.index("function renderAlchemyMoved()"):craft.index("function renderBench()")]
    html = _src(TABLE)
    layer = html[html.index('<div id="alchemy"'):html.index('<div id="veil">')]
    for name, text in [(p.name, _src(p)) for p in OURS + [CSS]] + [
            ("craft.html alchemy card", card), ("table.html #alchemy", layer)]:
        assert "—" not in text and "–" not in text, name


def test_alchemy_css_keeps_the_bench_layer_scale_and_motion_rules():
    """bench.css's rules (UI plan §10, §14): z-index 1 to 9 inside the layer, transitions
    transform and opacity at 200ms or less, and no new colour in the chrome. A mix's colour
    is content and reaches the page only as `--sw` from the server."""
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
    assert hexes <= bench, f"new colours in alchemy.css: {sorted(hexes - bench)}"
    assert "rgb(" not in body.replace("rgba(", "")


def test_the_page_draws_the_servers_numbers_and_never_sums_them():
    """Every figure on the bench is the server's: the DC and its terms, the face needed, the
    count of formulae, grades and caps, the colour and level, the rent, the ladder's caster
    levels and prices. Nothing in this lane's files does arithmetic on them, and no colour
    is made on the page from the server's three fractions (`swatch`/`css` are sent)."""
    op = r"\s*(?:[-*/]|\+(?!\s*[\"']))"
    for path in OURS:
        code = _code(_src(path))
        for field in ("dc", "need", "bonus", "level", "turbidity", "price_gp", "caster_level",
                      "grade", "count_formulae", "rent_cp", "waits", "minute", "mp"):
            assert not re.search(r"\." + field + r"\b" + op, code), f"{path.name} computes with .{field}"
        assert not re.search(r"Math\.(floor|ceil|trunc)", code), path.name
        assert "255" not in code and "rgb(" not in code, path.name


def test_a_hidden_formula_never_reaches_the_page():
    """Owner Q5.3: an experiment that would find an unknown formula is a count, never a name.
    The server withholds it (`match.secret`, no product, no DC label); the page reads only
    the server's `could.line` and calls the step "an experiment" on the mat and the tag."""
    shell, card = _code(_src(SHELL)), _code(_src(CARD))
    assert 'c.match.secret ? "an experiment"' in shell
    assert '"An experiment"' in card and "c.could.line" in card


# --- the old tab (UI plan §5.1, U1's row) -------------------------------------------------------

def test_the_old_alchemy_tab_is_a_card_that_opens_the_bench():
    """UI plan §2: /craft/'s Alchemy tab drew the old chain bench (every material an emoji
    tile into a cauldron, a die per dose, the preview's DC terms and mishap never shown). It
    becomes one card with one way to the bench over the table, which opens itself from the
    hash."""
    src = _src(CRAFT)
    sel = src[src.index("async function selectCraft("):src.index("function renderHerbalismMoved()")]
    assert 'if (CRAFT === "alchemy") { renderAlchemyMoved(); return; }' in sel
    assert 'CRAFT === "alchemy";' in sel.replace("\n", " ").replace("    ", " ") or 'CRAFT === "alchemy"' in sel
    card = src[src.index("function renderAlchemyMoved()"):src.index("function renderBench()")]
    assert 'href="/play/#alchemy"' in card and "Open the alchemy bench" in card
    assert 'location.hash === "#alchemy"' in _src(SHELL)


# --- the server's side: what the page needs, and what it must never be sent -------------------

@pytest.fixture
def bench(tmp_path):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        alchemy_views._PENDING.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"), start_id="quiet-the-bread-stall")
        pc = c.scene.pc()
        pc.inventory.clear()
        pc.stock.clear()
        pc.herb_known.clear()
        pc.purse = {"gp": 200}
        from rules import goods

        goods.deliver(c.scene, pc, goods.good("alchemist's field kit"))
        c.save()
        yield Client()
        cm._LIVE.clear()
        alchemy_views._PENDING.clear()


def _pc():
    return cm.current().scene.pc()


def post(client, url, body):
    return client.post(url, data=json.dumps(body), content_type="application/json")


def test_the_state_carries_identify_learn_the_potions_and_swatches(bench):
    """The strip is the whole of what the bench does: lane F's nine, then Identify and Learn,
    each lock the server's. A bought potion is no material, so Identify had nothing to pick
    from until the state listed the potions carried. Every row's colour is a swatch string,
    so the page never turns fractions into a colour."""
    from rules import alchemy_items

    _pc().carry("brimstone", 1)
    alchemy_items.put(_pc(), alchemy_items.record_for_formula(
        "potion-of-cure-light-wounds", bought=True), 1)
    cm.current().save()
    st = bench.get("/api/alchemy/state").json()
    ids = [m["id"] for m in st["methods"]]
    assert ids[-2:] == ["identify", "learn"] and "dissolve" in ids
    assert [p["name"] for p in st["potions"]] == ["Potion of Cure Light Wounds"]
    assert st["potions"][0]["known"] is False and st["potions"][0]["caster_level"] is None
    row = next(r for r in st["shelf"] if r["key"] == "inv:brimstone")
    assert re.fullmatch(r"#[0-9a-f]{6}", row["swatch"])


def test_the_check_says_the_rent_and_the_liquid_in_words(bench):
    """The flat stage's level bar draws the server's colour, level and words ("44% full,
    cloudy"); the rent before a step is a sentence of the server's (none at a field kit)."""
    _pc().carry("brimstone", 1)
    _pc().carry("lamp-oil", 1)
    cm.current().save()
    ch = post(bench, "/api/alchemy/check", {"method": "dissolve", "inputs": ["inv:brimstone"],
                                            "solvent": "inv:lamp-oil"}).json()
    start = ch["liquid"]["start"]
    assert re.fullmatch(r"#[0-9a-f]{6}", start["css"]) and start["words"].endswith(("cloudy", "hazy", "clear"))
    assert "% full" in start["words"] and ch["rent_line"] == ""


def test_an_unknown_property_row_says_nothing_at_all(bench):
    """Lane U4's report (2026-10-07): the material card's unknown rows carried `group`
    ("toxic", "mishap") and a key whose first letter said the same, so the card told the
    page what an assay had not found. An unknown row is only that it exists; a known one
    carries its essence, and the card names the hazards the shelf always names."""
    _pc().carry("quicksilver", 1)
    cm.current().save()
    card = bench.get("/api/alchemy/material/quicksilver").json()
    unknown = [p for p in card["properties"] if not p["known"]]
    assert unknown and all(set(p) == {"key", "known", "text", "drawback", "how"} for p in unknown)
    assert all(p["key"].startswith("unknown-") for p in unknown)
    assert "toxic to handle" in card["hazards"]


def test_an_unidentified_potions_formula_is_never_sent(bench):
    """Lane U4's report: the formulary sent a carried potion's formula before it was
    identified, and a FAILED take-apart named it in its response and its transcript line.
    Until it is identified or learned, the potion is offered by its own name only."""
    from rules import alchemy_items

    key = alchemy_items.put(_pc(), alchemy_items.record_for_formula(
        "potion-of-cure-light-wounds", bought=True), 1)
    _pc().name = "Kesst"
    cm.current().save()
    book = bench.get("/api/alchemy/formulary").json()
    w = next(x for x in book["writings"] if x["item"] == f"stock:{key}")
    assert w["fid"] == "" and w["formula"] is None
    r = post(bench, "/api/alchemy/learn", {"from": "potion", "item": f"stock:{key}", "face": 1}).json()
    assert not r["result"]["learned"]
    # The potion's own name is the player's to see (it is on the vial); the formula, its id
    # and its row are not.
    assert r["fid"] == "" and r["name"] is None and r["formula"] is None
    text = (json.dumps(r).lower() + cm.current().transcript[-1]["text"].lower()).replace(
        "potion of cure light wounds", "")
    assert "cure light" not in text and "potion-of-cure" not in text.replace(key.lower(), "")
    assert isinstance(r["bonus"], int)


def test_an_opened_pinch_stays_with_its_raw_material(bench):
    """Lane U4's report: after an assay the opened unit (a stock record of family "raw")
    read as a finished product and sat under "Finished work". It is the reagent still."""
    _pc().carry("brimstone", 2)
    cm.current().save()
    post(bench, "/api/alchemy/assay", {"material": "brimstone", "face": 20})
    rows = [r for r in bench.get("/api/alchemy/state").json()["shelf"] if r["material"] == "brimstone"]
    assert rows and all(r["group"] == "Reagents" for r in rows)


def test_wait_for_it_passes_the_hours_then_collects(bench):
    """Seen live (2026-10-07): a potion sets two hours after it is bottled and the bench had
    no way to let them pass; the player closed it and found "Not ready yet". Wait for it
    moves the clock through `Scene.advance` and collects. The "ready to collect" line the
    engine queued for it is dropped: left queued, it surfaced inside the NEXT step's flare
    ("It flares: ...; Kesst Vayr's Potion of Cure Light Wounds is ready to collect.; ...")."""
    _pc().carry("wintergreen-essence", 1)
    _pc().carry("glass-vial", 1)
    cm.current().save()
    body = {"method": "bottle", "inputs": ["inv:wintergreen-essence"], "vessel": "inv:glass-vial"}
    r = post(bench, "/api/alchemy/roll", dict(body, face=20)).json()
    f = post(bench, "/api/alchemy/finish", {"token": r["token"], "score": 0.5}).json()
    key = f["products"][0]["key"]
    before = cm.current().scene.clock_minutes
    got = post(bench, "/api/alchemy/collect", {"key": key, "wait": True})
    assert got.status_code == 200, got.content[:300]
    got = got.json()
    assert got["waited"] == 120 and cm.current().scene.clock_minutes == before + 120
    assert not any("ready to collect" in str(x.get("said")) for x in cm.current().scene._works_said)
    assert not got["works"]


def test_a_flare_line_carries_only_the_mishaps_once_stopped(bench):
    """Seen live: "It flares: Kesst Vayr takes 2 fire damage from Brimstone.; ...", a doubled
    stop after each tell. Each tell is joined without its own stop."""
    _pc().carry("brimstone", 2)
    _pc().carry("lamp-oil", 2)
    cm.current().save()
    r = post(bench, "/api/alchemy/roll", {"method": "dissolve", "inputs": ["inv:brimstone"],
                                          "solvent": "inv:lamp-oil", "face": 1}).json()
    assert r["flare"] and ".;" not in r["said"] and ".." not in r["said"]


def test_the_conversion_notice_is_lane_is_and_marked_seen_through_the_bench(bench, monkeypatch):
    """Lane I converts old alchemy (owner Q10.1) and the bench says what it did once: the
    state carries `conversions` ([] with no conversion in the build) and POST
    api/alchemy/seen marks a line seen through lane I's own `conversion_seen`. On a tree
    without lane I the route says so (501) rather than pretending to have marked it."""
    import importlib.util
    import sys
    import types

    from django.urls import resolve

    assert resolve("/api/alchemy/seen").func is alchemy_views.alchemy_seen
    if importlib.util.find_spec("rules.alchemy_migration") is None:
        assert bench.get("/api/alchemy/state").json()["conversions"] == []
        assert post(bench, "/api/alchemy/seen", {"key": "x"}).status_code == 501
    seen = []
    fake = types.ModuleType("rules.alchemy_migration")
    fake.conversions = lambda pc: [{"key": "k1", "name": "Old fire", "seen": "k1" in seen,
                                    "changes": ["Now called Alchemist's fire (it was Fire Flask)"]}]
    fake.conversion_seen = lambda pc, key: seen.append(key)
    monkeypatch.setitem(sys.modules, "rules.alchemy_migration", fake)
    import rules

    monkeypatch.setattr(rules, "alchemy_migration", fake, raising=False)
    st = bench.get("/api/alchemy/state").json()
    assert st["conversions"][0]["seen"] is False
    r = post(bench, "/api/alchemy/seen", {"key": "k1"})
    assert r.status_code == 200 and seen == ["k1"] and r.json()["conversions"][0]["seen"] is True
    assert '"/api/alchemy/seen"' in _code(_src(SHELL)) and "showConversions" in _src(SHELL)
