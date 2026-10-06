"""The enchanting circle's page (docs/enchanting-ui-plan.md §5, §6, §12; contracts §12 row U1,
§13; enchanting lane U1).

The circle is the third bench over the table, mounted on the bench core (29-bench-core.js)
and built FLAT FIRST, as the forge was: fully playable with no 3D stage (lane U3), no games
(lane U2) and no ledger (lane U5), each looked up when needed and named in the page only once
it is in the build. These tests hold what the lane measured going wrong while it was built,
live on scratch data at 1600x900 (2026-10-06: an Enchanter 4 prepared, attuned, waited for
noon and bound a +1 flaming longsword through the real clicks), the rules both earlier
benches keep (no loop while idle, no dash, one layer scale, transform and opacity only, the
page never computes a number), and the old /craft/ tab's mode row, retired so there is one
way to enchant.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from django.contrib.staticfiles import finders
from django.test import Client, override_settings

from play import campaign as cm
from play import enchant_views
from rules import forge_items
from rules.sheet import load_pc

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "play" / "static"
TABLE_JS = STATIC / "js" / "table"
SHELL = TABLE_JS / "45-enchant-shell.js"
SHELF = TABLE_JS / "46-enchant-shelf.js"
WORKING = TABLE_JS / "48-enchant-working.js"
OURS = [SHELL, SHELF, WORKING]
CSS = STATIC / "css" / "enchant.css"
TABLE = ROOT / "play" / "templates" / "play" / "table.html"
CRAFT = ROOT / "play" / "templates" / "play" / "craft.html"

# Other lanes' files the table names only once they are in the build (contracts §12, §13).
GUARDED = (["css/enchant-games.css", "js/table/47-enchant-stage.js", "js/table/49-enchant-ledger.js"]
           + [f"js/enchant-games/{m}.js" for m in ("prepare", "attune", "bind", "refine",
                                                     "unbind", "cleanse")]
           + [f"js/enchant-stage/{f}.js" for f in ("00-circle", "01-props", "02-vessels",
                                                     "03-room", "04-fx")])


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

def test_the_table_serves_the_circle_layer_and_the_enchanting_door(table_html):
    """UI plan §5.1: the circle opens over the table as its own dialog, served in the page
    so closing is instant, from an Enchanting door after Smithing. It carries the bench's
    class, so bench.css's layer, panels, ladder and perk picker reach it (the forge's perk
    picker came up unstyled before it did, lane U5's report). The door sits after Smithing
    and before the Crafting bench link, so 37-works.js's In progress door, which it places
    after the last `[data-*-open].door`, lands right after Enchanting."""
    tag = re.search(r'<div id="enchant"[^>]*>', table_html)
    assert tag, "the table has no #enchant layer"
    tag = tag.group(0)
    for need in ('role="dialog"', 'aria-modal="true"', "hidden", 'aria-labelledby="enchant-title"',
                 'class="bench enchant"'):
        assert need in tag, need
    for part in ("enchant-methods", "enchant-shelf-in", "enchant-stage", "enchant-tool",
                 "enchant-chips", "enchant-info", "enchant-lines", "enchant-hour",
                 "enchant-roll", "enchant-why", "enchant-game", "enchant-working-in",
                 "enchant-foot-in", "enchant-pops", "enchant-say", "enchant-close"):
        assert f'id="{part}"' in table_html, part
    door = re.search(r'<button[^>]*id="open-enchant"[^>]*>([^<]*)</button>', table_html)
    assert door and "data-enchant-open" in door.group(0) and door.group(1) == "Enchanting"
    assert 'aria-controls="enchant"' in door.group(0) and "v2-btn door" in door.group(0)
    assert (table_html.index('id="open-forge"') < table_html.index('id="open-enchant"')
            < table_html.index('href="/craft/">Crafting bench'))
    works = _src(TABLE_JS / "37-works.js")
    assert "[data-enchant-open].door" in works


def test_the_circle_scripts_load_after_the_core_in_number_order(table_html):
    """45 reads `window.BenchCore` the moment it runs, and 46 and 48 read `window.Enchant`:
    loaded out of order the Enchanting door does nothing. They follow 37 (In progress) and
    44 (the forge, whose BenchIcons patch 45's icons use). enchant.css follows bench.css and
    forge.css: it reuses the forge's swatch rule and its own rules must win where they meet."""
    order = ["js/table/29-bench-core.js", "js/table/36-bench-perks.js", "js/table/37-works.js",
             "js/table/44-forge-ledger.js", "js/table/45-enchant-shell.js",
             "js/table/46-enchant-shelf.js", "js/table/48-enchant-working.js"]
    at = [table_html.index(f"/static/{p}?v=") for p in order]
    assert at == sorted(at), "the circle's scripts are out of order"
    for p in order[4:]:
        assert table_html.count(f"/static/{p}?v=") == 1
    css = [table_html.index(f"/static/css/{n}.css?v=") for n in ("bench", "forge", "works", "enchant")]
    assert css == sorted(css)


def test_another_lanes_circle_file_is_named_only_once_it_exists(table_html):
    """The games (U2), the stage (U3) and the ledger (U5) are optional providers (contracts
    §13, "flat fallback if absent"). A tag for a file not in the build is a 404 in the
    console on every load and fails test_template_scripts; a file in the build with no tag
    is a lane's work that never runs. Each is emitted exactly when the file is in
    play/static, so the lead's merge needs no edit to this template."""
    for path in GUARDED:
        exists = bool(finders.find(path))
        named = f"/static/{path}?v=" in table_html
        assert named == exists, f"{path}: on disk {exists}, in the page {named}"
    # And the providers load where they must: the stage parts before the adapter, the
    # adapter between 46 and 48, the ledger after 48 (the template's own order).
    html = _src(TABLE)
    assert (html.index("js/enchant-stage/00-circle.js") < html.index("js/table/45-enchant-shell.js")
            < html.index("js/table/47-enchant-stage.js") < html.index("js/table/48-enchant-working.js")
            < html.index("js/table/49-enchant-ledger.js"))


def test_a_game_runs_only_when_it_is_registered_for_this_craft():
    """BenchGameDefs is one registry keyed by method name for every bench. Refine is a
    method name a future herb or alchemy game could take; the circle must not run another
    craft's game for its own step. The shell asks for `track: "enchant"` and otherwise
    finishes the step flat, at the middle of the range, and says so in the result."""
    code = _code(_src(SHELL))
    assert 'def.track !== "enchant"' in code
    assert "score: 0.5" in code and "flat: true" in code
    assert "No game for this step in this build" in _src(WORKING)
    # The phase of the day reaches the game in lane E's own shape, never recomputed.
    assert "hour: tuning.hour" in code and "seq: tuning.seq" in code and "seats: tuning.seats" in code


def test_the_stage_is_asked_for_and_never_required():
    """Contracts §13: `window.EnchantStage`, a no-op without WebGL, `available()` false. The
    shell looks it up when it needs it, mounts it only when it says it is available, and
    otherwise draws the method's roundel at 160px on the ground (the flat stand-in)."""
    code = _code(_src(SHELL))
    assert "window.EnchantStage" in code and 's.available()' in code
    assert "bench-flat enchant-flat" in code and "size: 160" in code
    for call in ("setScene", "setTool", "setVessel", "setSeats", "hour", "game", "flourish",
                 "productRect", "reducedMotion"):
        assert f'"{call}"' in code or f".{call}(" in code, call


# --- the standing rules: no loop, no dash, one layer scale, motion ---------------------------

def test_nothing_in_the_circle_loops_while_it_is_idle():
    """UI plan §7.3 and §10: an idle bench draws zero frames. None of this lane's files calls
    setInterval or requestAnimationFrame; the games' loop is the frame's (33), alive only
    while a game runs, and the stage's is lane U3's own `wake`."""
    for path in OURS:
        calls = re.findall(r"\b(setInterval|requestAnimationFrame)\s*\(", _src(path))
        assert not calls, f"{path.name} calls {calls}"
    assert "infinite" not in _src(CSS)


def test_no_circle_string_carries_an_em_or_en_dash():
    """UI plan §8 and the design skill's §9.G: zero em-dashes and en-dashes in this lane's
    files, comments included, in the #enchant layer's markup and in the old tab's card."""
    craft = _src(CRAFT)
    card = craft[craft.index("function renderEnchantMoved()"):craft.index("function renderLoading()")]
    html = _src(TABLE)
    layer = html[html.index('<div id="enchant"'):html.index('<div id="veil">')]
    for name, text in [(p.name, _src(p)) for p in OURS + [CSS]] + [
            ("craft.html enchanting card", card), ("table.html #enchant", layer)]:
        assert "—" not in text and "–" not in text, name


def test_enchant_css_keeps_the_bench_layer_scale_and_motion_rules():
    """bench.css's rules, owed by enchant.css too (UI plan §10, §14): z-index only orders the
    layer's own children (1 to 9), transitions are transform and opacity at 200ms or less,
    and no new colour enters the chrome: every literal colour is one bench.css already has.
    An essence's colour is content and reaches the page only as `--sw` from the server."""
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
    assert hexes <= bench, f"new colours in enchant.css: {sorted(hexes - bench)}"
    assert "rgb(" not in body.replace("rgba(", "")


def test_the_holds_are_pips_and_wrap_past_ten():
    """UI plan §6.5 drew ten pips "for the book's +10"; the owner's round 4 took the +10
    away (capacity is half the Enchanter level, no ceiling: Enchanter 30 holds +15). The
    server sends as many pips as the larger of ten and the capacity (`_holds_view`), so the
    row is a grid of ten that wraps, never a filled track, and the page draws every pip it
    is sent rather than a fixed ten."""
    css = _src(CSS)
    assert "grid-template-columns: repeat(10, 14px)" in css
    code = _code(_src(WORKING))
    assert "(h.pips || []).map(" in code
    assert not re.search(r"for \(var \w+ = 0; \w+ < 10;", code)


# --- the page never computes a number (UI plan §12) -------------------------------------------

def test_the_working_draws_the_servers_numbers_and_never_sums_them():
    """Every figure on the circle is lane E's: the DC and its terms, the face needed, the
    holds, the motes and their parts, the days, the countdowns. A sum on the page is a
    second answer to what the binding costs, and two answers drift. Nothing in this lane's
    files does arithmetic on them."""
    # A "+" followed by a string literal is the words being joined, not a sum.
    op = r"\s*(?:[-*/]|\+(?!\s*[\"']))"
    for path in OURS:
        code = _code(_src(path))
        for field in ("dc", "need", "bonus", "motes", "days", "hours", "used", "until",
                      "minutes_until", "minute"):
            assert not re.search(r"\." + field + r"\b" + op, code), f"{path.name} computes with .{field}"
        assert not re.search(r"Math\.(floor|ceil|trunc)", code), path.name
    # Whether a wait outlasts the attunement was first worked out on the page from the clock,
    # the countdown and the attunement's end (a sum); it is the server's `hour.lapses` now.
    assert "h.lapses" in _code(_src(SHELL))
    work = _src(WORKING)
    for field in ("c.costs.words", "c.costs.time_words", "h.words", "c.dc_terms"):
        assert field in work, field


def test_flawed_is_a_word_and_never_the_curse():
    """Owner round 4 point 2: the d20 and the margin are shown and the verdict says FLAWED;
    which curse stays hidden. The table's verdict knows only success and failure, so the
    shell casts FLAWED itself in the failing cast, and no file of this lane reads a curse
    record's fields: only the card's words, sent by the server once the curse is known."""
    code = _code(_src(SHELL))
    assert 'word: "Flawed"' in code and "good: false" in code
    for path in OURS:
        c = _code(_src(path))
        for field in ("d100", "curse.row", "curse.detail", "curse.tags", "curse_id"):
            assert field not in c, f"{path.name} reads {field}"
    # A skill check has no naturals (CRB p.180): a 20 on the face is never "natural 20".
    assert "natural: null" in code


# --- what was measured live, 2026-10-06 --------------------------------------------------------

def test_a_redraw_after_a_finish_keeps_the_keyboard_on_next():
    """Seen live on the first Prepare: the finish drew "Next: Attune" and focused it, then the
    check that follows every finish answered a beat later and redrew the column, and the
    keyboard fell to <body> (document.activeElement was the body). The column finds the
    focused control again by its id after every redraw."""
    code = _code(_src(WORKING))
    block = code[code.index("function drawAll()"):]
    block = block[:block.index("}\n  [")] if "}\n  [" in block else block[:600]
    assert "document.activeElement" in block and "document.getElementById(id)" in block


def test_the_phase_line_names_only_the_essence_it_favours():
    """Seen live: with flaming (noon) and bane (dusk) seated, the line read "Noon favours
    Flaming Essence, Bane Essence". The phase belongs to the essence whose family names it,
    read from its shelf row's `phase`, never every seated name."""
    code = _code(_src(SHELL))
    assert "it.phase === phase" in code


def test_a_forge_icon_is_drawn_as_art_not_a_letter():
    """Seen live: the forged longsword's row drew a lettered S, because BenchIcons.has knows
    only the herb registry while 40 taught BenchIcons.el the forge's stamped names. The
    circle asks the forge's registry too."""
    assert "FORGE_ICON_URLS[name]" in _code(_src(SHELL))


# --- the old tab (UI plan §15 U7, in this lane's row) ----------------------------------------

def test_the_old_enchanting_tab_is_a_card_that_opens_the_circle():
    """UI plan §2: /craft/'s Enchanting tab drew the old chain bench, whose preview sent the
    free-text Shaping field as the item, so every essence binding came back "not
    masterwork": no enchantment could be made from the page at all. It becomes one card
    with one way to the circle over the table."""
    src = _src(CRAFT)
    sel = src[src.index("async function selectCraft("):src.index("function renderHerbalismMoved()")]
    assert 'if (CRAFT === "enchanting") { renderEnchantMoved(); return; }' in sel
    card = src[src.index("function renderEnchantMoved()"):src.index("function renderLoading()")]
    assert 'href="/play/#enchant"' in card and "Open the circle" in card
    # The circle opens itself from that hash on load.
    assert 'location.hash === "#enchant"' in _src(SHELL)


def test_the_mode_row_is_gone_so_there_is_one_way_to_enchant():
    """UI plan §2, "retire the mode row (one craft now)": a second row of modes, "the circle"
    and "By the book", made two crafts on one track. Its markup, its renderer, its click
    handler and the MODE it sent are all gone, and no request from the page carries a mode."""
    src = _src(CRAFT)
    for gone in ('id="modes"', "renderModes", "MODE", "data-mode", "&mode=", "mode: MODE"):
        assert gone not in src, gone


# --- the server's side: fields the page needs ------------------------------------------------

@pytest.fixture
def circle(tmp_path):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        enchant_views._PENDING.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"), start_id="quiet-the-bread-stall")
        pc = c.scene.pc()
        pc.inventory.clear()
        pc.stock.clear()
        pc.track("enchanter").level = 4
        c.save()
        yield Client()
        cm._LIVE.clear()
        enchant_views._PENDING.clear()


def test_state_gives_the_mat_its_terms_for_read_and_identify(circle):
    """Read and Identify have no check request, so the dice mat had no terms to show before
    the throw (the d20 came up with nothing beside it). The state now carries them, the
    server's own: the Enchanter check for a Read, and for Identify the better of it and
    Spellcraft, exactly as `enchant_identify` takes it. And the biome underfoot, for lane
    U3's stage to draw a camp circle on its ground."""
    d = circle.get("/api/enchant/state").json()
    read, ident = d["rolls"]["read"], d["rolls"]["identify"]
    assert read["bonus"] == sum(t["value"] for t in read["terms"])
    assert read["terms"][0]["label"].startswith("Enchanter")
    assert ident["bonus"] >= read["bonus"]
    sc = enchant_views._spellcraft(cm.current().scene.pc())
    if sc is not None and sc > read["bonus"]:
        assert ident["terms"] == [{"label": "Spellcraft", "value": sc}]
    assert "biome" in d["where"]


def test_a_forged_vessel_reaches_the_shelf_with_every_field_the_rows_draw(circle):
    """The shelf row draws the vessel's quality word, what it holds in the server's words,
    its seats for the working, and its gear for the icon; an essence row draws its grant,
    motes, phase and colour. All present on the state the page loads."""
    rec = {"id": "iron-longsword", "name": "Superior Iron Longsword", "kind": "crafted",
           "craft": "blacksmith", "count": 1, "gear": "weapon", "base": "longsword",
           "slot": "hands", "quality_index": 3, "masterwork": True,
           "pieces": {"head": {"material": "iron", "passes": 1},
                      "haft": {"material": "ash-haft", "passes": 0},
                      "fittings": {"material": "brass-guard", "passes": 0}},
           "quench": None, "finish": [], "flaws": [], "smith": {"level": 3, "perks": {}},
           "schema": 3}
    pc = cm.current().scene.pc()
    pc.add_stock(forge_items.stock_item(rec), 1)
    pc.carry("flaming-essence", 1)
    cm.current().save()
    d = circle.get("/api/enchant/state").json()
    v = d["shelf"]["vessels"][0]
    for k in ("key", "name", "quality_name", "holds", "seats", "gear", "state", "badges"):
        assert k in v, k
    assert v["holds"]["words"] == "+0 of +2" and len(v["holds"]["pips"]) == 10
    e = d["shelf"]["essences"][0]
    for k in ("key", "id", "name", "grants", "motes", "phase", "color", "count", "unknown"):
        assert k in e, k


def _layered(item_id="flame-sword"):
    from rules import magic_layer

    rec = forge_items.record_for_base("longsword", gear="weapon", quality_index=3,
                                      item_id=item_id, name="Flame Sword")
    return magic_layer.write(rec, {"enhancement": 1, "properties": [{"id": "flaming"}]},
                             binding={"quality_index": 3, "level": 4, "perks": {}})


def test_unknown_essence_traits_never_leave_the_server(circle):
    """Lane U5's report (2026-10-06): the state sent every essence's raw phase, polarity,
    grant and working traits whatever the player had learned, so only the page stood
    between the player and what a Read, a seating or a binding is meant to teach. Each is
    sent empty until it is known, and the ledger card's phase words likewise."""
    from rules import enchanter as en

    pc = cm.current().scene.pc()
    pc.herb_known.clear()
    pc.carry("flaming-essence", 1)
    cm.current().save()
    e = circle.get("/api/enchant/state").json()["shelf"]["essences"][0]
    assert e["grants"] == "" and e["phase"] == "" and e["polarity"] == "" and e["traits"] == []
    assert e["unknown"] > 0
    assert "phase_words" not in circle.get("/api/enchant/essence/flaming-essence").json()
    en.reveal_traits(pc, "flaming-essence", ["phase", "grants"], "read, day 1")
    cm.current().save()
    e = circle.get("/api/enchant/state").json()["shelf"]["essences"][0]
    assert e["phase"] == "noon" and e["grants"] == "Flaming" and e["polarity"] == ""
    card = circle.get("/api/enchant/essence/flaming-essence").json()
    assert card["phase_words"].startswith("Noon")


def test_the_items_route_lists_magic_items_and_keeps_a_pending_step(circle):
    """Lane U5's ask: the ledger needs the magic items' cards while the bench is open, and
    a fresh GET of the state lets a pending roll go (`enchant_state` clears `_PENDING`),
    so a card fetched mid-step would have cost the player the step. GET api/enchant/items
    is read only: it lists every layered item with its card and leaves the step waiting."""
    pc = cm.current().scene.pc()
    pc.add_stock(forge_items.stock_item(_layered()), 1)
    cm.current().save()
    c = cm.current()
    enchant_views._PENDING[c.id] = {"token": "waiting"}
    d = circle.get("/api/enchant/items").json()
    assert [i["key"] for i in d["items"]] == ["stock:flame-sword"]
    assert d["items"][0]["card"] is not None
    assert enchant_views._PENDING.get(c.id) == {"token": "waiting"}


def test_whether_a_wait_outlasts_the_attunement_is_the_servers_answer(circle):
    """The page first worked it out itself (the clock plus the countdown against the
    attunement's end: a sum on the page, UI plan §12). The check's `hour` carries `lapses`:
    true when waiting for the phase would let the attunement run out first."""
    from rules import enchanter as en

    pc = cm.current().scene.pc()
    pc.add_stock(forge_items.stock_item(dict(forge_items.record_for_base(
        "longsword", gear="weapon", quality_index=3, item_id="plain-sword",
        name="Plain Sword"))), 1)
    pc.carry("flaming-essence", 1)
    pc.carry("arcane-essence-i", 1)
    c = cm.current()
    c.scene.clock_minutes = 9 * 60 + 10           # morning: noon is 110 minutes off
    st = pc.stock["plain-sword"]
    m = en._magic_of_stock(st)
    m["circle"] = {"prepared": {"quality": 2, "holds_rank": 4},
                   "attuned": {"quality": 2, "until": 9 * 60 + 70,
                               "seats": {"point": {"key": "inv:flaming-essence",
                                                   "name": "Flaming Essence"},
                                         "edge": {"key": "inv:arcane-essence-i",
                                                  "name": "Arcane Essence I"}}}}
    en._store_magic(st, m)
    c.save()
    chk = circle.post("/api/enchant/check", data=json.dumps({"method": "bind",
                                                             "vessel": "stock:plain-sword"}),
                      content_type="application/json").json()
    assert chk["hour"]["phase"] == "noon" and chk["hour"]["lapses"] is True
    m["circle"]["attuned"]["until"] = 9 * 60 + 10 + 1440
    en._store_magic(st, m)
    c.save()
    chk = circle.post("/api/enchant/check", data=json.dumps({"method": "bind",
                                                             "vessel": "stock:plain-sword"}),
                      content_type="application/json").json()
    assert chk["hour"]["lapses"] is False


def test_the_equipment_tab_wields_a_forged_weapon_and_reads_its_magic(circle):
    """Seen live on the end-to-end check (2026-10-06): the collected +1 flaming longsword's
    Equipment row offered Wear, which wrote it into the gloves' slot ("puts on +1 Flaming
    Superior Iron Longsword (hands)") and left the rapier in hand; nothing on the tab could
    draw it, and lane U5 found its line read "for show, no effect in play". The row offers
    Wield through the engine's own `wear` op, and Put away once it is in hand, and its line
    is the item card's."""
    from play import views

    pc = cm.current().scene.pc()
    pc.add_stock(forge_items.stock_item(_layered()), 1)
    row = next(r for r in views._carried(pc) if r["key"] == "flame-sword")
    assert [a["label"] for a in row["acts"]] == ["Wield"]
    assert row["acts"][0]["body"] == {"item": "flame-sword", "op": "wield"}
    assert row["known"] and "fire" in row["line"]
    pc.equipped = "flame-sword"
    row = next(r for r in views._carried(pc) if r["key"] == "flame-sword")
    assert [a["label"] for a in row["acts"]] == ["Put away"]
