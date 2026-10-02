"""The table rebuild, stage 2: the Sheet, Equipment, Spells, Trade and Journal tabs.

The owner's approved design (docs/mock/table-layout/, README in full) asked for a Sheet
that opens on a Combat card, an Equipment page of shelves, a list and Worn and wielded, a
Spells page with red spent sockets, and the trade window's shelves shared by both. Every
number on them is the engine's: `/api/sheet` (rules/sheet.py `full_sheet`, and
play/views.py `_carried` for Equipment), never worked out in the page. These tests run the
page's own functions (05-sheet.js) in node against real sheets and hold them to that, and
drive the new doors (`/api/wear` with an engine `op`) through the Django client.

The defects each prevents are named in its docstring, measured before they were fixed.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from html.parser import HTMLParser

import pytest
from django.test import Client

from pagesource import ROOT, TABLE, TABLE_SCRIPTS

SHEET_JS = TABLE_SCRIPTS / "05-sheet.js"
TRADE_JS = TABLE_SCRIPTS / "06-trade-and-page.js"

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


# --- running the page's functions in node ------------------------------------------------

_STUBS = r"""
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g,
  c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const sign = n => (n >= 0 ? "+" : "") + n;
const title = s => s.replace(/\b\w/g, c => c.toUpperCase());
const glossify = s => esc(s);
const tradeGlyph = (name, cls = "") => `<i class="tgi" data-icon="${esc(name)}"></i>`;
const el = () => ({ addEventListener() {}, classList: { add() {}, remove() {}, toggle() {},
                    contains: () => false }, setAttribute() {}, innerHTML: "",
                    querySelector: () => null, querySelectorAll: () => [] });
const document = { querySelector: () => null, querySelectorAll: () => [],
                   getElementById: () => null, addEventListener() {}, contains: () => false };
const window = { addEventListener() {}, matchMedia: () => ({ matches: false }) };
const $ = () => el();
class MutationObserver { constructor() {} observe() {} }
const CSS = { escape: s => s };
let SHEET = null, STATE = { scene: {} }, SHEET_TAB = "sheet";
const Shell = { show() {}, sheetBacked: () => true };
"""


def _trade_shelves() -> str:
    """06's TRADE_SHELVES and its icon table, lifted from the file itself, so a test of
    the Equipment rail uses the trade window's own scheme and not a copy of it."""
    src = TRADE_JS.read_text(encoding="utf-8")
    shelves = src[src.index("const TRADE_SHELVES = {"):src.index("};", src.index("const TRADE_SHELVES = {")) + 2]
    icons = src[src.index("const TRADE_ITEM_ICONS = {"):src.index("const TRADE_INERT")]
    fns = src[src.index("const tradeShelf = x =>"):src.index("const tradeGlyph")]
    return shelves + "\n" + icons + "\n" + fns


def _run(tmp_path, body: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    src = _STUBS + _trade_shelves() + "\n" + SHEET_JS.read_text(encoding="utf-8") + "\n" + body
    f = tmp_path / "page.js"
    f.write_text(src, encoding="utf-8")
    done = subprocess.run([node, str(f)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


class _Tree(HTMLParser):
    VOID = {"input", "br", "img", "meta", "link", "hr"}

    def __init__(self):
        super().__init__()
        self.elements, self.stack = [], []

    def handle_starttag(self, tag, attrs):
        el = {"tag": tag, "attrs": dict(attrs), "text": "", "ancestors": list(self.stack)}
        self.elements.append(el)
        if tag not in self.VOID:
            self.stack.append(el)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        for el in self.stack:
            el["text"] += data


def _tree(html: str) -> list[dict]:
    t = _Tree()
    t.feed(html)
    return t.elements


def _text(el) -> str:
    return " ".join(el["text"].split())


def _sheet(fixture: str, level: int | None = None, weapons=None) -> dict:
    """A real `/api/sheet` payload, built the way the view builds it."""
    from play.views import _sheet_payload
    from rules.sheet import load_pc

    pc = load_pc(f"fixtures/{fixture}.json")
    if level:
        pc.level = level
    if weapons is not None:
        pc.weapons = list(weapons)
    return _sheet_payload(pc)


# --- the Combat card: the engine's numbers, and only them ---------------------------------

@needs_node
def test_the_combat_card_writes_the_engines_numbers_and_every_swing(tmp_path):
    """The owner's second-pass verdict: "the sheet is missing a ton of information from
    the available combat maneuvers and weapon attacks." The old Offense page showed one
    to-hit per weapon and a pill saying "2 attacks on a full attack", so a level 6
    fighter's second swing at +1 was nowhere. Every swing is the engine's
    `attack_modifiers` at that iteration now, and the page writes what it is sent."""
    s = _sheet("pc-borin", level=6, weapons=["longsword", "dagger", "shortbow", "light crossbow"])
    out = _run(tmp_path, f"const S = {json.dumps(s)};\n"
               "console.log(JSON.stringify({ html: combatCard(S) + defenceCard(S) }));")
    els = _tree(out["html"])
    o, d = s["offense"], s["defense"]
    plaques = [e for e in els if e["tag"] == "div" and "stat" in e["attrs"].get("class", "").split()]
    shown = {}
    for p in plaques:
        dt = next(e for e in els if e["tag"] == "dt" and p in e["ancestors"])
        dd = next(e for e in els if e["tag"] == "dd" and p in e["ancestors"])
        shown[_text(dt)] = _text(dd)
    sign = lambda n: f"+{n}" if n >= 0 else str(n)
    assert shown["Initiative"] == sign(o["initiative"]["total"])
    assert shown["Base attack"] == sign(o["bab"]) == "+6"
    assert shown["CMB"] == sign(o["cmb"]["total"])
    assert shown["CMD"] == f"{d['cmd']['total']} flat-footed {d['cmd_flat_footed']['total']}"
    assert shown["Speed"] == f"{d['speed']['current']} ft"
    assert shown["AC"] == str(d["ac"]["total"])
    assert shown["Touch"] == str(d["ac_touch"]["total"])
    assert shown["Flat-footed"] == str(d["ac_flat_footed"]["total"])
    for sv in d["saves"]:
        assert shown[sv["name"]] == sign(sv["total"])
    rows = [e for e in els if e["tag"] == "tr" and any(
        c["tag"] == "td" and c["attrs"].get("data-label") == "To hit" for c in els if e in c["ancestors"])]
    by_name = {_text(next(c for c in els if e in c["ancestors"] and c["tag"] == "b")).lower(): e for e in rows}
    for a in o["attacks"]:
        row = by_name[a["name"].lower()]
        hit = next(c for c in els if row in c["ancestors"] and c["attrs"].get("data-label") == "To hit")
        assert _text(hit).startswith(" / ".join(sign(x) for x in a["swings"])), a["name"]
        assert _text(next(c for c in els if row in c["ancestors"]
                          and c["attrs"].get("data-label") == "Critical")) == a["crit"]
    longsword = next(a for a in o["attacks"] if a["key"] == "longsword")
    assert len(longsword["swings"]) == 2, "a BAB 6 fighter swings twice on a full attack"
    assert f"two swings, at {sign(longsword['swings'][0])} then {sign(longsword['swings'][1])}" in out["html"]
    # The light crossbow's range was None in the curated table and the page said "not
    # known". Since 2026-09-30 the curated row is merged into the weapon file's
    # (tests/test_gear_usable.py), which prints 80 ft; "not known" is kept for a real
    # launcher the table has no range for.
    xbow = by_name["light crossbow"]
    rng = next(c for c in els if xbow in c["ancestors"] and c["attrs"].get("data-label") == "Range")
    assert _text(rng).startswith("80 ft")


@needs_node
def test_the_page_shows_what_it_is_sent_even_when_it_does_not_add_up(tmp_path):
    """The rule is that no number is worked out in the page. A sheet whose numbers are
    deliberately inconsistent with their own terms (a CMD of 1234 made of base 10 and Dex
    +2; swings of +7 then +99; a flat-footed AC above the AC) comes out exactly as sent:
    a page that summed the terms, or counted iteratives down in fives, would show
    something else."""
    s = _sheet("pc-kesst")
    s["defense"]["cmd"]["total"] = 1234
    s["defense"]["cmd_flat_footed"]["total"] = 777
    s["defense"]["ac_flat_footed"]["total"] = 55
    s["offense"]["attacks"][0]["swings"] = [7, 99]
    s["offense"]["initiative"]["total"] = 42
    out = _run(tmp_path, f"const S = {json.dumps(s)};\n"
               "console.log(JSON.stringify({ html: combatCard(S) + defenceCard(S) }));")
    html = out["html"]
    assert "1234" in html and "flat-footed 777" in html
    assert ">55<" in html.replace("\n", "").replace(" ", "")
    assert "+7 / +99" in html and "at +7 then +99" in html
    assert "+42" in html


@needs_node
def test_all_ten_manoeuvres_and_feint_are_rows_with_bonus_provokes_effect_and_limits(tmp_path):
    """The mock README, point 4: "all ten combat manoeuvres plus feint, each with its
    bonus, whether it provokes, what success does and its limits". Foundry's PF1 sheet
    lists none of them one by one; the owner asked for every one. Provokes is the
    manoeuvre table's own word; feint is a Bluff check in the engine, so its bonus is the
    Bluff total and the rest is "not known", and a character who cannot try Bluff gets
    "not known" for the bonus too, never a zero."""
    from rules.tables import MANEUVERS

    s = _sheet("pc-kesst")
    out = _run(tmp_path, f"const S = {json.dumps(s)};\n"
               "const T = JSON.parse(JSON.stringify(S)); T.offense.feint = { skill: 'bluff', total: null, usable: false };\n"
               "console.log(JSON.stringify({ html: combatCard(S), none: combatCard(T) }));")
    els = _tree(out["html"])
    rows = [e for e in els if e["tag"] == "tr" and any(
        c["attrs"].get("data-label") == "Provokes" for c in els if e in c["ancestors"])]
    names = [_text(next(c for c in els if r in c["ancestors"] and c["tag"] == "b")) for r in rows]
    assert len(MANEUVERS) == 10
    assert sorted(names[:-1]) == sorted(m["name"] for m in MANEUVERS.values())
    assert names[-1] == "feint"
    cell = lambda r, label: _text(next(c for c in els if r in c["ancestors"]
                                       and c["attrs"].get("data-label") == label))
    for r, m in zip(rows, s["offense"]["maneuvers"]):
        assert cell(r, "Bonus") == (f"+{m['cmb']['total']}" if m["cmb"]["total"] >= 0 else str(m["cmb"]["total"]))
        assert cell(r, "Provokes") == ("Yes" if MANEUVERS[m["key"]]["provokes"] else "No")
        assert cell(r, "On success") == m["effect"]
        if MANEUVERS[m["key"]].get("size_limit") is not None:
            assert "no more than one size larger" in cell(r, "Limits")
        if MANEUVERS[m["key"]].get("needs_two_hands"):
            assert "needs both hands free" in cell(r, "Limits")
    bluff = next(k for k in s["skills"] if k["name"] == "bluff")["total"]
    feint = rows[-1]
    assert cell(feint, "Bonus").startswith(f"+{bluff}" if bluff >= 0 else str(bluff))
    assert "not known" in cell(feint, "Provokes")
    assert "No attack of opportunity" in out["html"]
    none = _tree(out["none"])
    frow = [e for e in none if e["tag"] == "tr"][-1]
    assert "not known" in _text(next(c for c in none if frow in c["ancestors"]
                                      and c["attrs"].get("data-label") == "Bonus"))


def test_the_api_carries_each_swing_and_the_manoeuvre_tables_words():
    """`/api/sheet` did not carry a full attack's swings, a weapon's range, weight,
    finesse or traits, or whether a manoeuvre provokes: the mock read them straight off
    the engine in build_data.py, and the real page had nothing to read. Each is the
    engine's own answer, asked the same way."""
    from rules import weapons as weapons_mod
    from rules.sheet import load_pc
    from rules.tables import MANEUVERS
    from play.views import _sheet_payload

    pc = load_pc("fixtures/pc-borin.json")
    pc.level = 11
    s = _sheet_payload(pc)
    for a in s["offense"]["attacks"]:
        want = [sum(m.value for m in pc.attack_modifiers(a["key"], iteration=i))
                for i in pc.attack_sequence(a["key"], full_attack=True)]
        assert a["swings"] == want and len(want) == 3
        w = weapons_mod.get(a["key"])
        assert a["range_ft"] == w.get("range_ft") and a["weight_lb"] == w.get("weight_lb")
        assert a["finessable"] == bool(w.get("finessable")) and a["traits"] == list(w.get("traits") or [])
    for m in s["offense"]["maneuvers"]:
        assert m["provokes"] == bool(MANEUVERS[m["key"]].get("provokes"))
        assert m["two_hands"] == bool(MANEUVERS[m["key"]].get("needs_two_hands"))
    bluff = next(k for k in s["skills"] if k["name"] == "bluff")
    assert s["offense"]["feint"] == {"skill": "bluff", "total": bluff["total"], "usable": bluff["usable"]}


# --- Equipment -----------------------------------------------------------------------------

def _carried_sheet() -> dict:
    """Kesst carrying a bit of everything the five stores hold: a weapon in hand and one
    not, worn armour and a shield in the pack, a bought wondrous ring, a jar, a lantern."""
    from rules import crafting, goods
    from rules.sheet import load_pc
    from play.views import _sheet_payload

    pc = load_pc("fixtures/pc-kesst.json")
    pc.goods["buckler"] = 1
    pc.goods["studded leather"] = 1
    pc.goods["silver brooch"] = 1
    for name in ("Ring of Protection +1", "hooded lantern", "antitoxin"):
        found = type("F", (), {"kind": "gear", "key": name, "name": name, "tier": "common",
                               "per": 1, "track": ""})()
        goods.deliver(None, pc, found)
    return _sheet_payload(pc)


def test_every_carried_thing_is_one_row_on_the_trade_windows_shelves():
    """The owner: "without permanently displayed text telling me what they are it will be
    painfull when i have more gear", and the shelves are "the trade window's own, in its
    order". Every row is on one of the server's `SHELVES` (the trade window's), and the
    Equipment rail and the trade window's side tabs name the same shelves in the same
    order, so a potion is a consumable in the pack and at the counter alike."""
    from play.views import SHELVES

    s = _carried_sheet()
    rows = s["equipment"]["carried"]
    assert {r["shelf"] for r in rows} <= set(SHELVES)
    names = {r["name"].lower(): r for r in rows}
    assert names["rapier"]["state"] == "in hand" and names["rapier"]["shelf"] == "weapons"
    assert names["leather armour"]["state"] == "worn" and names["leather armour"]["shelf"] == "armour"
    assert names["buckler"]["shelf"] == "armour" and names["buckler"]["fits"] == "shield"
    assert names["ring of protection +1"]["shelf"] == "magic" and names["ring of protection +1"]["fits"] == "ring"
    assert names["antitoxin"]["shelf"] == "consumables"
    assert names["silver brooch"]["shelf"] == "valuables"
    js = TRADE_JS.read_text(encoding="utf-8")
    block = js[js.index("const TRADE_SHELVES = {"):js.index("};", js.index("const TRADE_SHELVES = {"))]
    assert re.findall(r"^\s+(\w+):\s+\{ label", block, re.M) == list(SHELVES)


def test_every_act_is_a_real_door_and_there_is_no_drop():
    """Wield, Wear and Use answer to the engine's own doors (the `wear` op, `/api/slots`,
    `/api/use`), and there is no op to drop a thing, so no row offers it. Take off and
    Put away arrived 2026-09-30 (the `take_off` op, and a wield of the fists;
    tests/test_gear_usable.py). Measured 2026-09-30 on the Equipment tab: a bought hooded
    lantern offered Drink, because the consumables planner answers "ok" for any jar with
    nothing harmful in it; drinking is offered only for a thing that is for drinking now."""
    s = _carried_sheet()
    rows = {r["name"].lower(): r for r in s["equipment"]["carried"]}
    doors = {a["api"] for r in rows.values() for a in r["acts"]}
    assert doors <= {"/api/wear", "/api/slots", "/api/use"}
    labels = {a["label"] for r in rows.values() for a in r["acts"]}
    # "Use" since 2026-10-02: a jar that works in more than one place, or anywhere but
    # swallowed, opens a menu of where it goes (tests/test_use_by_route.py).
    assert labels <= {"Wield", "Wear", "Drink", "Use", "Throw", "Coat", "Take off",
                      "Put away"}
    assert [a["label"] for a in rows["dagger"]["acts"]] == ["Wield"]
    assert rows["dagger"]["acts"][0]["body"] == {"item": "dagger", "op": "wield"}
    assert [a["label"] for a in rows["rapier"]["acts"]] == ["Put away"]
    assert rows["rapier"]["acts"][0]["body"] == {"item": "unarmed", "op": "wield"}
    assert [a["label"] for a in rows["leather armour"]["acts"]] == ["Take off"]
    assert rows["leather armour"]["acts"][0]["body"] == {"item": "leather", "op": "take_off"}
    assert rows["buckler"]["acts"][0]["body"] == {"item": "buckler", "op": "wear"}
    ring = rows["ring of protection +1"]["acts"][0]
    assert ring["api"] == "/api/slots" and ring["body"]["slot"] == "ring" and ring["body"]["index"] == 0
    assert "Drink" not in {a["label"] for a in rows["hooded lantern"]["acts"]}
    assert "Drink" in {a["label"] for a in rows["antitoxin"]["acts"]}


@needs_node
def test_a_slot_filters_the_list_to_what_fits_and_the_gap_is_said_in_words(tmp_path):
    """"Choosing a slot shows only what fits it" (the mock README, point 1). The hand shows
    the weapons, the shield slot the buckler, the ring slot the ring; the list is A to Z;
    and the page says in words what the rules cannot do, with no button for it."""
    s = _carried_sheet()
    out = _run(tmp_path, f"SHEET = {json.dumps(s)}; SHEET_TAB = 'equipment';\n"
               "const out = {};\n"
               "for (const fit of [null, 'hand', 'shield', 'ring', 'armor', 'head']) {\n"
               "  EQ_FIT = fit; out[String(fit)] = pageEquipment(SHEET); }\n"
               "console.log(JSON.stringify(out));")
    def rows(html):
        els = _tree(html)
        return [_text(next(c for c in els if r in c["ancestors"] and c["tag"] == "b"))
                for r in els if "eqrow" in r["attrs"].get("class", "").split()]
    everything = rows(out["null"])
    assert everything == sorted(everything, key=str.lower), "not A to Z"
    assert len(everything) == len(s["equipment"]["carried"])
    assert {n.lower() for n in rows(out["hand"])} == {"rapier", "dagger"}
    assert [n.lower() for n in rows(out["shield"])] == ["buckler"]
    assert [n.lower() for n in rows(out["ring"])] == ["ring of protection +1"]
    assert {n.lower() for n in rows(out["armor"])} == {"leather armour", "studded leather"}
    assert rows(out["head"]) == [] and "Nothing you carry goes there" in out["head"]
    assert "Fits the rings" in out["ring"] and "Showing what fits the rings" in out["ring"]
    for html in out.values():
        for bad in (">Drop<", ">drop<"):
            assert bad not in html
    page = TABLE.read_text(encoding="utf-8")
    assert "There is no drop yet." in page
    assert "Wield and wear from what you carry. New things are bought at a counter." in page
    assert 'id="eq-trade"' in page and ">Go to Trade<" in page


@needs_node
def test_the_equipment_rail_is_the_trade_windows_shelves_with_counts(tmp_path):
    """The shelves down the side are the trade window's (06's TRADE_SHELVES), in its
    order, each with its count, and a shelf with nothing on it is not offered."""
    s = _carried_sheet()
    out = _run(tmp_path, f"SHEET = {json.dumps(s)}; SHEET_TAB = 'equipment'; EQ_FIT = null;\n"
               "console.log(JSON.stringify({ html: pageEquipment(SHEET), order: Object.keys(TRADE_SHELVES) }));")
    els = _tree(out["html"])
    tabs = [e for e in els if e["attrs"].get("data-eqshelf")]
    got = [t["attrs"]["data-eqshelf"] for t in tabs]
    assert got[0] == "all"
    assert got[1:] == [k for k in out["order"] if k in got[1:]], "shelves out of the trade window's order"
    counts = {}
    for r in s["equipment"]["carried"]:
        counts[r["shelf"]] = counts.get(r["shelf"], 0) + 1
    for t in tabs[1:]:
        assert t["attrs"]["aria-label"].endswith(f", {counts[t['attrs']['data-eqshelf']]}")
    assert set(got[1:]) == set(counts)


def test_wield_and_wear_run_the_engines_own_op(tmp_path, settings):
    """The Equipment tab's Wield and Wear had no door: `_op_wear` was reached only through
    the GM, in words. `/api/wear` with an `op` runs it, answers with the op's own tell
    ("draws the dagger", "puts on the buckler. Armour class 14 to 15."), and a refusal is
    the op's own sentence, sent back as a 400 the page prints beside the button."""
    from play import campaign as cm
    from rules.sheet import load_pc

    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    cm._LIVE.clear()
    c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
    pc = c.scene.pc()
    pc.goods["buckler"] = 1
    c.save()
    client = Client()
    before = pc.ac()
    r = client.post("/api/wear", data=json.dumps({"item": "dagger", "op": "wield"}),
                    content_type="application/json")
    assert r.status_code == 200, r.content
    assert r.json()["wear_tell"] == f"{pc.name} draws the dagger."
    assert cm.current().scene.pc().equipped == "dagger"
    r = client.post("/api/wear", data=json.dumps({"item": "buckler", "op": "wear"}),
                    content_type="application/json")
    assert r.status_code == 200, r.content
    after = cm.current().scene.pc().ac()
    assert after == before + 1
    # A shield is a move action (CRB Table 6-8), said since 2026-09-30.
    assert r.json()["wear_tell"] == (f"{pc.name} puts on the buckler (a move action). "
                                     f"Armour class {before} to {after}.")
    r = client.post("/api/wear", data=json.dumps({"item": "full plate", "op": "wear"}),
                    content_type="application/json")
    assert r.status_code == 400 and "is not carrying full plate" in r.json()["error"]
    sheet = client.get("/api/sheet").json()
    rows = {x["name"].lower(): x for x in sheet["equipment"]["carried"]}
    assert rows["buckler"]["state"] == "worn" and rows["dagger"]["state"] == "in hand"


# --- Spells ----------------------------------------------------------------------------------

@needs_node
def test_a_spent_socket_is_red_and_an_unspent_one_is_lit(tmp_path):
    """The owner, 2026-09-29: "perhaps a red bubble instead of a bronze one to indicate a
    spent slot". A level with three slots, one cast today and one prepared spell waiting,
    draws one lit, one open and one red socket, each named in words; the red is the
    page's own blood tokens, and the open and lit ones are bronze, never red."""
    out = _run(tmp_path, "const SP = { kind: 'prepared' };\n"
               "console.log(JSON.stringify({ html: slotSockets(SP, { level: 1, max: 3, left: 2, held: 1, dc: 14 }) }));")
    els = _tree(out["html"])
    gems = [e for e in els if e["tag"] == "i" and "gem" in e["attrs"].get("class", "").split()]
    assert [g["attrs"]["class"] for g in gems] == ["gem lit", "gem", "gem spent"]
    assert [g["attrs"]["aria-label"] for g in gems] == [
        "Level 1 slot: prepared, ready", "Level 1 slot: open", "Level 1 slot: spent today"]
    assert "1 ready, 1 spent, 1 open" in out["html"]
    css = TABLE.read_text(encoding="utf-8")
    spent = css[css.index("  .gem.spent {"):]
    spent = spent[:spent.index("}")]
    assert "var(--alarm)" in spent and "var(--blood)" in spent
    lit = css[css.index("  .gem.lit {"):]
    lit = lit[:lit.index("}")]
    assert "--alarm" not in lit and "--blood" not in lit
    # The house rule, said beside the sockets: prepare whenever, a spent slot stays spent.
    js = SHEET_JS.read_text(encoding="utf-8")
    assert "Prepare whenever you like. A slot\n      spent today stays spent" in js


# --- the tabs' pages are the design's ---------------------------------------------------------

def test_each_tab_draws_its_own_page_into_the_one_sheet_panel():
    """The old sheet was twelve pages behind a strip of tabs, scoped per table tab by a
    list of page names; the design gives each table tab one page. `TABS` names the four,
    17 carries the one panel into each tab's own container, and the Trade tab's window
    sits in the design's framed card with the owner's sentence and a door to Equipment."""
    js = SHEET_JS.read_text(encoding="utf-8")
    tabs = js[js.index("const TABS = ["):js.index("];", js.index("const TABS = ["))]
    assert re.findall(r'\["(\w+)"', tabs) == ["sheet", "equipment", "spells", "journal"]
    seventeen = (TABLE_SCRIPTS / "17-tab-sheet.js").read_text(encoding="utf-8")
    assert 'const SHEET_HOMES = { sheet: "sheetmore", equipment: "mode-equipment",' in seventeen
    page = TABLE.read_text(encoding="utf-8")
    assert '<div id="tradepanel" class="v2-framed v2-card-leather"' in page
    assert "Buy and sell here. What you buy goes into your pack, and you put it" in page
    assert "data-open-equipment" in page
