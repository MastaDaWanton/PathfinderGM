"""The trade window, after the owner's mockup (Phase 3 task I7, 2026-09-29).

"The player side isn't relevant other then sorted tabs on the side." Three columns in the
existing look: what you carry as a list with category tabs down its side, sorted within a
tab, the purse at the foot; the deal as a basket ("You buy" / "You sell" lines, each with
a quantity stepper), the total by a coin stack and ONE primary button, "Trade, pay 75 gp";
their wares as cards (icon, name, category mark, price) scrolling inside the column. Art
is game-icons.net under CC BY 3.0, stored in `play/static/icons/items/`.

The window is drawn here by running the trade section of 06-trade-and-page.js in node,
against a real `/api/trade` answer from a campaign standing in Pangrella's market, and
reading what it wrote. What node cannot hold (the redraw keeping focus, the sticky deal
at 375px, the icons painting) was driven in the browser against a live server; the task
report has the numbers.

Defects these record, each seen on the screen or measured before it was fixed:

  * "nothing the engine can run", in red, on the stables' tack: developer language, and
    an alarm for what is only the reason a price is low. Now "for show, no effect in
    play", in the dim ink, once, on the deal's line.
  * "common" under every row: said nothing, forty times. The rarity shows only when an
    item is not common.
  * "animal feed (1 days)": the tables write the unit plural. One is "1 day"; the buy
    tell said "1 days of animal feed" from the same unit, and says "1 day" now.
  * The rows could not be filed: a carried jar's id is "willow-bark-tea#1" and a bench
    material's is bare, so the page could not tell a potion from a lump of bismuth. The
    rows carry `shelf` (and `staple`, how many the counter can sell), the smallest
    addition the side tabs and the steppers needed.
  * At 375px the three columns stacked into one scroller; left to shrink, the deal came
    out 80px tall with its button 150px below the bottom of an 812px screen, and the
    carried list slid under the cards. The columns are `flex: none` and the deal is
    pinned to the bottom of the screen.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from html.parser import HTMLParser

import pytest

from pagesource import ROOT, TABLE, TABLE_SCRIPTS

ICONS = ROOT / "play" / "static" / "icons" / "items"
TRADE_JS = TABLE_SCRIPTS / "06-trade-and-page.js"
MANUAL = ROOT / "play" / "templates" / "play" / "manual.html"
WORK_HOUR = 10 * 60


def _trade_js() -> str:
    src = TRADE_JS.read_text(encoding="utf-8")
    return src[src.index("let TRADE = null;"):src.index("function busy(on)")]


def _code(js: str) -> str:
    """The script without its comments, which quote the old words on purpose."""
    js = "\n".join(ln for ln in js.splitlines() if not ln.lstrip().startswith("//"))
    return re.sub(r"/\*.*?\*/", "", js, flags=re.S)


def _panel_markup() -> str:
    src = TABLE.read_text(encoding="utf-8")
    start = src.index('<div id="tradepanel"')
    return src[start:src.index('<div id="sheetpanel"', start)]


def _css() -> str:
    src = TABLE.read_text(encoding="utf-8")
    css = src[src.index("<style>"):src.index("</style>")]
    return css[css.index("/* The trade window (I7"):css.index("#sheetpanel::after")]


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


def _cls(el) -> list[str]:
    return (el["attrs"].get("class") or "").split()


# --- a real counter ------------------------------------------------------------------------

@pytest.fixture(scope="module")
def market(tmp_path_factory):
    """`/api/trade` at Pangrella's general store and horse lines, for a character carrying
    a tea, bread, rope, a garnet, ore and an uncommon salve; and the buy tell for a day of
    animal feed."""
    from django.test import Client, override_settings

    from play import campaign as cm
    from rules.crafting import Stock
    from rules.sheet import load_pc

    tmp = tmp_path_factory.mktemp("i7")
    with override_settings(CAMPAIGN_DIR=str(tmp / "campaigns")):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        # The drawn opening's own cast out (on some seeds a robbery, which is a fight and
        # shuts every counter), and with them any keeper it stood up: `staffed` would
        # remember that counter as manned by somebody who is gone.
        me = c.scene.pc().ref
        for ref in [r for r in list(c.scene.people) if r != me]:
            c.scene.remove(ref)
        c.scene.initiative = []
        c.scene.staffed = []
        c.scene.location_id = "5bbd0c40345f"                 # Pangrella, a town
        c.scene.clock_minutes = WORK_HOUR
        c.engine().place_party("5bbd0c40345f~urban:the-market")
        pc = c.scene.pc()
        pc.purse = {"gp": 120}
        for base, kw, n in [("willow-bark tea", {"craft": "herbalist"}, 3),
                            ("loaf of bread", {"craft": ""}, 2),
                            ("hemp rope", {"craft": ""}, 50),
                            ("garnet", {"craft": ""}, 1),
                            ("Cold Iron", {"kind": "ore", "craft": "smithing"}, 4)]:
            pc.add_stock(Stock(base=base, tier="common", **kw), n)
        pc.add_stock(Stock(base="moonpetal salve", tier="uncommon", craft="herbalist"), 1)
        c.save()
        post = lambda url, body: Client().post(url, data=json.dumps(body),
                                               content_type="application/json").json()
        out = {"general": post("/api/trade", {"line": "general"}),
               "horses": post("/api/trade", {"line": "horses"}),
               "weaponsmith": post("/api/trade", {"line": "weaponsmith"}),
               "alchemist": post("/api/trade", {"line": "alchemist"})}
        for name in ("general", "horses", "weaponsmith", "alchemist"):
            assert "till" in out[name], (name, out[name])
        out["feed"] = post("/api/trade/do", {"op": "buy", "item": "tack:animal feed",
                                             "line": "horses"})
        cm._LIVE.clear()
    return out


# A browser's worth of globals for the trade section alone. `$` hands back one fake
# element per selector, which remembers what was written into it.
_STUBS = r"""
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g,
  c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const EL = {};
const fake = () => ({ innerHTML: "", textContent: "", hidden: false, disabled: false,
  className: "", dataset: {},
  classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
  setAttribute() {}, addEventListener() {}, querySelector() { return null; },
  querySelectorAll() { return []; }, contains() { return false; }, focus() {},
  scrollIntoView() {} });
const $ = s => (EL[s] = EL[s] || fake());
const document = { querySelector: () => null, querySelectorAll: () => [],
                   addEventListener: () => {}, activeElement: null };
const CSS = { escape: s => s };
const post = async () => ({});
const render = () => {}, getState = async () => ({});
"""


def _draw(payload: dict, tmp_path, steps: str = "") -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    src = (_STUBS + _trade_js() + f"\nTRADE = {json.dumps(payload)};\n" + steps
           + "\ndrawTrade();\n"
           + "console.log(JSON.stringify({ mine: $('#tradmine').innerHTML,"
           + " shelves: $('#tradeshelves').innerHTML, wares: $('#tradtheirs').innerHTML,"
           + " deal: $('#tradewhat').innerHTML, go: $('#tradego').textContent,"
           + " goDisabled: $('#tradego').disabled, sum: $('#tradesum').textContent,"
           + " lab: $('#tradetotlab').textContent, short: $('#tradeshort').textContent,"
           + " purse: $('#tradepurse').textContent, till: $('#tradetill').textContent }));\n")
    f = tmp_path / "trade.js"
    f.write_text(src, encoding="utf-8")
    done = subprocess.run([node, str(f)], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


# --- the three columns ---------------------------------------------------------------------

def test_the_window_is_three_columns_in_the_owners_order():
    """What you carry, the deal, their wares: left to right, as drawn. The carried list
    has its tabs down the side (a vertical tablist beside the list it controls)."""
    els = _tree(_panel_markup())
    body = next(e for e in els if "tradebody" in _cls(e))
    cols = [e for e in els if "tradecol" in _cls(e) and e["ancestors"][-1] is body]
    assert [c["attrs"].get("aria-labelledby") for c in cols] == \
        ["tr-carry-h", "tr-deal-h", "tr-wares-h"]
    heads = {e["attrs"]["id"]: e["text"].strip() for e in els if e["tag"] == "h2"}
    assert heads["tr-carry-h"] == "What you carry" and heads["tr-deal-h"] == "The deal"
    assert heads["tr-wares-h"].startswith("Their wares")
    shelves = next(e for e in els if e["attrs"].get("id") == "tradeshelves")
    assert shelves["attrs"]["role"] == "tablist"
    assert shelves["attrs"]["aria-orientation"] == "vertical"
    assert cols[0] in shelves["ancestors"]
    mine = next(e for e in els if e["attrs"].get("id") == "tradmine")
    assert mine["attrs"]["role"] == "tabpanel" and cols[0] in mine["ancestors"]
    purse = next(e for e in els if e["attrs"].get("id") == "tradepurse")
    assert cols[0] in purse["ancestors"], "the purse total sits at the foot of the left"
    till = next(e for e in els if e["attrs"].get("id") == "tradetill")
    assert cols[2] in till["ancestors"], "the till total sits in the wares header"


def test_the_deal_has_one_button_and_a_coin_stack():
    """"ONE primary button ... Nothing else competes with it." The deal column's own
    markup holds exactly one button; the steppers and Remove are drawn per line."""
    els = _tree(_panel_markup())
    deal = next(e for e in els if "tradedeal" in _cls(e))
    buttons = [e for e in els if e["tag"] == "button" and deal in e["ancestors"]]
    assert [b["attrs"]["id"] for b in buttons] == ["tradego"]
    coins = [e for e in els if "tr-coins" in _cls(e) and deal in e["ancestors"]]
    assert coins and coins[0]["attrs"]["data-icon"] == "delapouite-two-coins"


def test_a_basket_line_has_a_stepper_and_the_button_names_the_sum(market, tmp_path):
    """Two tents and a day's rations bought, a garnet sold: "You buy" and "You sell"
    lines, each with minus, the count and plus; the button says what the deal comes
    to. 2 x 10 gp + 5 sp - 1 sp 9 cp = 20 gp 3 sp 1 cp."""
    got = _draw(market["general"], tmp_path, """
      tradeAdd("buy", "gear:tent", false); tradeAdd("buy", "gear:tent", false);
      tradeAdd("buy", "gear:rations", false); tradeAdd("sell", "garnet#1", false);
    """)
    els = _tree(got["deal"])
    assert [e["text"] for e in els if e["tag"] == "h3"] == ["You buy", "You sell"]
    lines = [e for e in els if "tr-line" in _cls(e)]
    assert [(ln["attrs"]["data-side"], ln["attrs"]["data-id"]) for ln in lines] == \
        [("buy", "gear:tent"), ("buy", "gear:rations"), ("sell", "garnet#1")]
    for ln in lines:
        inside = [e for e in els if ln in e["ancestors"]]
        acts = [e["attrs"].get("data-act") for e in inside if e["tag"] == "button"]
        assert acts == ["dec", "inc", "drop"], acts
        assert any(e["tag"] == "output" for e in inside)
    counts = [e["text"] for e in els if e["tag"] == "output"]
    assert counts == ["2", "1", "1"]
    assert got["lab"] == "You pay" and got["sum"] == "20 gp 3 sp 1 cp"
    assert got["go"] == "Trade, pay 20 gp 3 sp 1 cp" and not got["goDisabled"]


def test_a_sale_alone_says_take_and_a_short_purse_disables_the_button(market, tmp_path):
    sold = _draw(market["general"], tmp_path, 'tradeAdd("sell", "garnet#1", false);')
    assert sold["go"].startswith("Trade, take ") and sold["lab"] == "You receive"
    broke = _draw(market["weaponsmith"], tmp_path, """
      const dear = TRADE.theirs.find(x => x.gp > TRADE.purse_gp);
      tradeAdd("buy", dear.id, false);
    """)
    assert broke["goDisabled"] and broke["short"].startswith("You are ")
    assert "short" in broke["short"]


def test_a_staple_steps_up_and_a_drawn_thing_stops_at_one(market, tmp_path):
    """The engine sells a thing drawn onto today's shelf once (`mark_sold`), and a staple
    without end: the stepper's plus says so rather than letting the basket ask for two
    of the one Frost-Forged Steel."""
    alc = market["alchemist"]
    drawn = next(x for x in alc["theirs"] if not x["staple"])
    got = _draw(alc, tmp_path, f"""
      tradeAdd("buy", {json.dumps(drawn["id"])}, false);
      tradeAdd("buy", {json.dumps(drawn["id"])}, false);
    """)
    els = _tree(got["deal"])
    assert [e["text"] for e in els if e["tag"] == "output"] == ["1"]
    inc = next(e for e in els if e["attrs"].get("data-act") == "inc")
    assert "disabled" in inc["attrs"]
    rope = _draw(market["general"], tmp_path, """
      for (let i = 0; i < 3; i++) tradeAdd("buy", "gear:rope", false);
    """)
    assert [e["text"] for e in _tree(rope["deal"]) if e["tag"] == "output"] == ["3"]


def test_the_keys_on_a_line_are_plus_minus_and_delete():
    """Keyboard: tab to a line, + and - change how many, Delete takes it out; Enter on a
    card or a row adds (they are buttons); Esc closes."""
    js = _trade_js()
    keys = js[js.index('$("#tradewhat").addEventListener("keydown"'):]
    assert '"+": 1' in keys and '"-": -1' in keys and '"Delete"' in keys
    assert 'e.key === "Escape"' in js
    assert '<li class="tr-line" tabindex="0"' in js


# --- the carried list ----------------------------------------------------------------------

def test_what_you_carry_is_filed_under_side_tabs_and_sorted_by_name(market, tmp_path):
    got = _draw(market["general"], tmp_path)
    tabs = [e for e in _tree(got["shelves"]) if e["tag"] == "button"]
    assert [t["attrs"]["data-shelf"] for t in tabs] == \
        ["all", "consumables", "gear", "valuables", "materials"]
    assert tabs[0]["attrs"]["aria-selected"] == "true"
    names = [e["text"] for e in _tree(got["mine"]) if e["tag"] == "b"]
    assert names == sorted(names, key=str.lower) and len(names) == 6
    food = _draw(market["general"], tmp_path, 'TRADE_SHELF = "consumables";')
    names = [e["text"] for e in _tree(food["mine"]) if e["tag"] == "b"]
    assert names == ["loaf of bread", "moonpetal salve", "willow-bark tea"]
    assert got["purse"] == market["general"]["purse"]
    assert got["till"].endswith(" in the till")


def test_every_row_is_filed_under_a_shelf_the_page_knows(market):
    """`shelf` on every row of both columns, from the server's own list."""
    from play.views import SHELVES

    for name in ("general", "horses", "weaponsmith", "alchemist"):
        for row in market[name]["theirs"] + market[name]["mine"]:
            assert row["shelf"] in SHELVES, row
    assert {r["shelf"] for r in market["weaponsmith"]["theirs"]} == {"weapons"}
    assert {r["shelf"] for r in market["horses"]["theirs"]} == {"animals"}
    mine = {r["name"]: r["shelf"] for r in market["general"]["mine"]}
    assert mine["loaf of bread"] == "consumables" and mine["garnet"] == "valuables"
    assert mine["Cold Iron"] == "materials" and mine["hemp rope"] == "gear"
    js = _trade_js()
    for shelf in SHELVES:
        assert f"  {shelf}:" in js[js.index("const TRADE_SHELVES"):], shelf


# --- the words -----------------------------------------------------------------------------

def test_no_developer_words_and_rarity_only_when_it_is_not_common(market, tmp_path):
    # The window's own words. The sheet's inventory (05-sheet.js) still prints the phrase
    # under a jar with no structured effects; that file is another task's, and the
    # phrase there is a separate call.
    assert "nothing the engine can run" not in _code(_trade_js()) + _panel_markup()
    got = _draw(market["horses"], tmp_path, """
      const tack = TRADE.theirs.find(x => !x.does_something);
      tradeAdd("buy", tack.id, false);
    """)
    assert "for show, no effect in play" in got["deal"]
    wares = _draw(market["alchemist"], tmp_path)
    cards = [e for e in _tree(wares["wares"]) if "tr-card" in _cls(e)]
    rare = [e for e in _tree(wares["wares"]) if "tr-rare" in _cls(e)]
    assert len(cards) == len(market["alchemist"]["theirs"])
    assert len(rare) == sum(1 for x in market["alchemist"]["theirs"]
                            if x["tier"] != "common")
    assert "Common" not in wares["wares"] and ">common<" not in wares["wares"]


def test_one_day_is_a_day():
    """"animal feed (1 days)" on the horse lines; the tell said "1 days of" too."""
    from rules import goods

    feed = goods.Good(id="tack:feed", name="animal feed", price_gp=.05, per=1, unit="days")
    assert feed.label == "animal feed (1 day)"
    two = goods.Good(id="tack:feed", name="animal feed", price_gp=.1, per=2, unit="days")
    assert two.label == "animal feed (2 days)"
    assert goods.measure(1, "hours") == "1 hour" and goods.measure(50, "ft") == "50 ft"


def test_the_horse_lines_sell_a_day_of_feed(market):
    names = [r["name"] for r in market["horses"]["theirs"]]
    assert "animal feed (1 day)" in names, names
    assert not any("(1 days)" in n or "(1 hours)" in n for n in names)
    assert market["feed"].get("ok"), market["feed"]
    assert "1 day of animal feed" in market["feed"]["tell"]


def test_no_dash_or_arrow_in_the_windows_words():
    """Owner's standing rule: no em or en dashes, no arrows, in UI text. The old empty
    button read a lone em dash."""
    markup = _panel_markup()
    assert not re.search("[–—←-⇿]", markup)
    for literal in re.findall(r"`[^`]*`|\"[^\"\n]*\"", _code(_trade_js())):
        assert not re.search("[–—←-⇿]", literal), literal


# --- icons and credits ---------------------------------------------------------------------

def _icon_names() -> set[str]:
    js = _trade_js()
    names = set(re.findall(r'"((?:lorc|delapouite|skoll|sbed|willdabeast|carl-olsen|'
                           r'caro-asercion|lucasms)-[a-z0-9-]+)"', js))
    names |= set(re.findall(r'data-icon="([a-z0-9-]+)"', _panel_markup()))
    return names


def test_every_icon_the_window_names_is_on_disk_and_recoloured():
    names = _icon_names()
    assert len(names) >= 8 + 17, "one per shelf at least, and the weapons their own"
    for name in names:
        f = ICONS / f"{name}.svg"
        assert f.is_file(), name
        svg = f.read_text(encoding="utf-8")
        assert svg.startswith("<svg") and 'fill="currentColor"' in svg, name
        assert "M0 0h512v512H0z" not in svg, f"{name} still carries the black square"
    on_disk = {p.stem for p in ICONS.glob("*.svg")}
    assert on_disk == names, ("unused", on_disk - names)


def test_the_icons_are_credited_where_they_are_used():
    credits = (ICONS / "CREDITS.txt").read_text(encoding="utf-8")
    assert "game-icons.net" in credits and "creativecommons.org/licenses/by/3.0" in credits
    for f in ICONS.glob("*.svg"):
        assert f.name in credits, f.name
    manual = MANUAL.read_text(encoding="utf-8")
    assert "icons/items/CREDITS.txt" in manual and "Trade window item icons" in manual
    assert "icons/items/CREDITS.txt" in _panel_markup()


# --- the look ------------------------------------------------------------------------------

def test_the_phone_pins_the_deal_and_nothing_loops():
    """At 1000px and under the columns stack in one scroller, wares first, and the deal
    sticks to the bottom of the screen. Nothing in the window loops: the heading's
    candle glow is stopped here, and the window's CSS has no animation of its own."""
    css = _css()
    phone = css[css.index("@media (max-width: 1000px)"):]
    assert ".tradecol, .tradelist { flex: none; }" in phone
    deal = phone[phone.index(".tradedeal {"):]
    assert "position: sticky; bottom: 0;" in deal[:deal.index("}")]
    assert "#tradepanel .sheethead h1 { animation: none; }" in css
    assert "@keyframes" not in css and "animation:" not in css.replace(
        "#tradepanel .sheethead h1 { animation: none; }", "")
    assert "focus-visible" in css
