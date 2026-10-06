"""The enchanter's essence card, recipes, Journal section, the item card's magic section with
Identify, and the enchanter's row in the perk picker (docs/enchanting-ui-plan.md §6.6 to
§6.9; contracts §12 and §13). Lane U5.

The card, recipes, Journal and item section are play/static/js/table/49-enchant-ledger.js
(`window.EnchantLedger`); the item section is placed on the Equipment and Sheet tabs by
18-tab-equipment.js and 17-tab-sheet.js; the Journal mounts the section from
21-tab-journal.js; the picker is 36-bench-perks.js with an `enchanter` track. The behaviour
checks load the real files into node with a small fake DOM, as tests/test_forge_ledger_ui.py
does, and feed them the REAL server's answers: a campaign is begun, essences, a found ring
and a flawed sword are carried, one essence trait is learned through the real knowledge
store, and the enchant routes are read through the Django test client. They skip, saying
why, where node is not installed. Each test names the defect it prevents.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from django.test import Client, override_settings

from play import campaign as cm
from play import enchant_views
from rules import curses, forge_items, knowledge, magic_layer
from rules.crafting import Stock
from rules.sheet import load_pc

ROOT = Path(__file__).resolve().parent.parent
TABLE_JS = ROOT / "play" / "static" / "js" / "table"
LEDGER = TABLE_JS / "49-enchant-ledger.js"
PERKS = TABLE_JS / "36-bench-perks.js"
JOURNAL = TABLE_JS / "21-tab-journal.js"
SHEET_TAB = TABLE_JS / "17-tab-sheet.js"
EQUIP_TAB = TABLE_JS / "18-tab-equipment.js"

# A lane F curse record (tests/test_enchant_api.py's HIDDEN): the page must never see any of
# these while the curse is not known.
CURSE = {"schema": 1, "id": "curse:opposite", "d100": 27, "row": "opposite",
         "detail": {"rolls": []}, "tags": ["curse.opposite"], "cl": 3, "gear": "weapon",
         "origin": "item:flawed-sword", "state": {}}
SECRETS = ("curse:opposite", "curse.opposite", "opposite", "d100")


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _forged(rid: str) -> dict:
    return {"id": rid, "name": "Superior Iron Longsword", "kind": "crafted",
            "craft": "blacksmith", "count": 1, "gear": "weapon", "base": "longsword",
            "slot": "hands", "quality_index": 3, "masterwork": True,
            "pieces": {"head": {"material": "iron", "passes": 1},
                       "haft": {"material": "ash-haft", "passes": 0},
                       "fittings": {"material": "brass-guard", "passes": 0}},
            "quench": None, "finish": [], "flaws": [], "smith": {"level": 3, "perks": {}},
            "schema": 3}


def _post(client, url, body):
    return client.post(url, data=json.dumps(body), content_type="application/json")


# --- the server's answers, from a real campaign -----------------------------------------------

@pytest.fixture(scope="module")
def served(tmp_path_factory):
    """What the page is given: the real views over the real knowledge, materials, layer and
    curse modules (no fakes), on a scratch campaign dir."""
    tmp = tmp_path_factory.mktemp("enchant-ledger")
    with override_settings(CAMPAIGN_DIR=tmp / "campaigns"):
        cm._LIVE.clear()
        enchant_views._PENDING.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"), start_id="quiet-the-bread-stall")
        pc = c.scene.pc()
        pc.inventory.clear()
        pc.stock.clear()
        pc.herb_known.clear()
        pc.track("enchanter").level = 4
        c.scene.clock_minutes = 12 * 60
        client = Client()
        out = {"empty_ledger": client.get("/api/enchant/ledger").json()}
        pc.carry("flaming-essence", 2)
        pc.carry("vorpal-essence", 1)
        # A found ring: a layer nobody here made, nothing known of it.
        ring = Stock(base="Plain silver ring", count=1, craft="", kind="crafted", slot="ring",
                     wearable=True, masterwork=True, tier="common")
        rec = {"id": "ring", "name": "Plain silver ring", "kind": "crafted", "slot": "ring",
               "gear": "ring", "masterwork": True, "quality_index": 3}
        rec = magic_layer.write(rec, {"powers": [{"recipe": "mi-ring-protection-1"}]},
                                binding={"quality_index": 3, "level": 6, "perks": {}}, day=1)
        rec["magic"]["known"] = {"intent": False, "curse": False, "how": "found"}
        ring.magic = rec["magic"]
        pc.add_stock(ring, 1)
        # A flawed binding: the maker knows it took flawed and what it was meant to do,
        # never which curse (rules/enchanter._collect_binding writes `known.flawed`).
        srec = magic_layer.write(_forged("flawed-sword"), {"enhancement": 1},
                                 binding={"quality_index": 3, "level": 4, "perks": {}},
                                 curse=dict(CURSE), day=1)
        srec["magic"]["known"] = {"intent": True, "curse": False, "flawed": True, "how": "made"}
        pc.add_stock(forge_items.stock_item(srec), 1)
        # The same curse, identified by 10: its words may now be said.
        krec = magic_layer.write(_forged("known-cursed"), {"enhancement": 1},
                                 binding={"quality_index": 3, "level": 4, "perks": {}},
                                 curse=dict(CURSE, origin="item:known-cursed"), day=1)
        krec["magic"]["known"] = {"intent": True, "curse": True, "flawed": True, "how": "made"}
        pc.add_stock(forge_items.stock_item(krec), 1)
        # One trait of the flaming essence learned: its phase of the day (Attune's lesson).
        knowledge.reveal(pc, "flaming-essence", ["phase"], "attuned it, day 1")
        c.save()
        out["flaming"] = client.get("/api/enchant/essence/flaming-essence").json()
        out["vorpal"] = client.get("/api/enchant/essence/vorpal-essence").json()
        out["ledger"] = client.get("/api/enchant/ledger").json()
        state = client.get("/api/enchant/state").json()
        out["track"] = state["track"]
        shelf = state["shelf"]
        out["cards"] = {v["key"]: v["card"] for g in ("vessels", "intermediates", "cant_use")
                        for v in shelf[g] if v.get("card")}
        out["state_text"] = json.dumps(state)
        out["ring_key"] = next(k for k in out["cards"] if "ring" in k)
        out["identify"] = _post(client, "/api/enchant/identify",
                                {"item": out["ring_key"], "face": 20}).json()
        out["identify_again"] = _post(client, "/api/enchant/identify",
                                      {"item": out["ring_key"], "face": 1}).json()
        out["recipes"] = client.get("/api/enchant/recipes").json()
        out["curse_words"] = curses.describe(CURSE)
        cm._LIVE.clear()
        enchant_views._PENDING.clear()
    return out


# --- the node harness --------------------------------------------------------------------------

_NODE = r"""
const fs = require('fs'), vm = require('vm');
const args = JSON.parse(process.argv[2]);
const data = JSON.parse(fs.readFileSync(args.data, 'utf8'));

class El {
  constructor() { this.listeners = {}; this.kids = []; this.attrs = {}; this.dataset = {}; this.style = {};
    this.innerHTML = ''; this.removed = false; this.parentNode = null; this.cls = new Set();
    const self = this;
    this.classList = { add: (c) => self.cls.add(c), remove: (c) => self.cls.delete(c),
      contains: (c) => self.cls.has(c), toggle: (c, on) => { on ? self.cls.add(c) : self.cls.delete(c); } }; }
  addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); }
  appendChild(c) { c.parentNode = this; this.kids.push(c); return c; }
  remove() { this.removed = true; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  querySelector() { return null; }
  contains(x) { return x === this; }
  focus() {}
}
const ids = {};
const doc = { activeElement: null, cookie: '', head: new El(), body: new El(),
  getElementById: (id) => ids[id] || null, createElement: () => new El(), querySelector: () => null,
  addEventListener() {}, dispatchEvent() {}, contains: (x) => !!x && !x.removed };
const sandbox = { document: doc, console, setTimeout, clearTimeout, Promise, JSON, Object, Array,
  String, Number, Math, Error, RegExp, addEventListener() {}, innerWidth: 1600, innerHeight: 900,
  CustomEvent: function (n, o) { this.type = n; this.detail = o && o.detail; } };
sandbox.window = sandbox;
vm.createContext(sandbox);
const tick = () => new Promise((r) => setTimeout(r, 0));
const target = (map) => ({ closest: (sel) => map[sel] || null });
const out = {};

(async () => {
  if (args.mode === 'perks') {
    vm.runInContext(fs.readFileSync(args.perks, 'utf8'), sandbox);
    const P = sandbox.BenchPerks;
    const pops = new El(); const posts = []; const saved = [];
    const wrap = P.open({ track: 'enchanter', state: data.track, pops,
      api: (p, b) => { posts.push([p, b]); return Promise.resolve(Object.assign({}, data.track, { picks_banked: 0 })); },
      saved: (t, picks) => saved.push(picks) });
    out.html = wrap.innerHTML;
    const click = (map) => wrap.listeners.click.forEach((f) => f({ target: target(map) }));
    click({ '[data-perk]': { dataset: { perk: 'capacity' } } });
    click({ '[data-perk]': { dataset: { perk: 'potency' } } });
    click({ '[data-pk]': { dataset: { pk: 'ok' }, disabled: false } });
    await tick(); await tick();
    out.posts = posts; out.saved = saved; out.closed = wrap.removed;
    out.row = P.tracks.enchanter;
  }
  if (args.mode === 'ledger') {
    vm.runInContext(fs.readFileSync(args.ledger, 'utf8'), sandbox);
    const L = sandbox.EnchantLedger, R = L.render;
    out.api = ['card', 'peek', 'unpeek', 'close', 'forget', 'recipes', 'journal', 'items', 'itemFor',
               'itemSection', 'canIdentify', 'identify'].filter((n) => typeof L[n] !== 'function');
    out.flaming = R.card(data.flaming, { actions: true, pinned: true });
    out.vorpal = R.card(data.vorpal, { actions: true });
    out.vorpalConfirm = R.needsConfirm(data.vorpal);
    out.vorpalKnown = R.needsConfirm(Object.assign({}, data.vorpal, {
      known: (data.vorpal.known || []).concat([{ key: 'working:volatile', text: 'volatile', how: 'read, day 2' }]) }));
    out.confirm = R.confirm(data.vorpal);
    out.none = R.card(Object.assign({}, data.flaming, { carried: 0 }), { actions: true });
    out.phaseWords = R.card(Object.assign({}, data.flaming, { phase_words: 'Noon, 42 minutes left' }), {});
    out.swatchBad = R.card(Object.assign({}, data.flaming, { color: 'red;background:url(x)' }), {});
    out.rows = R.rows({ ledger: data.ledger.ledger, open: '', unknownFirst: false });
    out.rowsFirst = R.rows({ ledger: data.ledger.ledger, open: '', unknownFirst: true });
    out.rowsOpen = R.rows({ ledger: data.ledger.ledger, open: 'flaming-essence', unknownFirst: false });
    out.rowsEmpty = R.rows({ ledger: data.empty_ledger.ledger, open: '' });
    out.rowsReading = R.rows({ ledger: null, open: '' });
    out.recipes = R.recipes(data.recipes.recipes, { load: true });
    out.recipesCant = R.recipes(data.recipes.recipes.map((r) => Object.assign({}, r, { can_make: false })), { load: true });
    out.recipesNone = R.recipes([], {});
    out.items = {};
    out.can = {};
    for (const k of Object.keys(data.cards)) {
      out.items[k] = L.itemSection(data.cards[k], { key: k, name: k, button: true });
      out.can[k] = L.canIdentify(data.cards[k]);
    }
    out.identified = L.itemSection(data.identify.card, { key: 'r', name: 'ring', button: true });
    out.identifyLine = R.identifyLine(data.identify, 'Plain silver ring');
    out.identifyAgain = R.identifyLine(data.identify_again, 'Plain silver ring');
    out.identifyFail = R.identifyLine(Object.assign({}, data.identify, { result: 'fail', repeat: false,
      words: 'Nothing yet. You can try again tomorrow.' }), 'Plain silver ring');
    out.byName = L.itemFor({ 'stock:x': { key: 'stock:x', name: 'Plain Silver Ring', card: {} } }, 'stock:renamed', 'plain silver ring');
  }
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""


def _node(mode: str, data: dict) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed; the behaviour checks need a JS engine")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "ledger.js"
        script.write_text(_NODE, encoding="utf-8")
        blob = Path(tmp) / "data.json"
        blob.write_text(json.dumps(data), encoding="utf-8")
        done = subprocess.run([node, str(script), json.dumps({
            "mode": mode, "data": str(blob), "perks": str(PERKS), "ledger": str(LEDGER)})],
            capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert done.returncode == 0, done.stderr[:2000]
    return json.loads(done.stdout)


@pytest.fixture(scope="module")
def drawn(served):
    return _node("ledger", served)


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip().replace("&#39;", "'")


# --- the essence card -----------------------------------------------------------------------

def test_the_essence_card_shows_only_what_is_known_and_a_line_per_unknown(served, drawn):
    """Lane F's knowledge: an essence's traits are revealed one by one. With only its phase
    learned, the flaming essence's card must say that one trait, how it was learned, and
    one "unknown" line for each of the other six, and must NOT say what it grants (the
    server sends no unknown text, and the card fills nothing in from data of its own: the
    first thing a careless card would print is the essence's name-sake property)."""
    card = served["flaming"]
    assert [t["key"] for t in card["known"]] == ["phase"] and card["unknown"] == 6
    html = drawn["flaming"]
    assert html.count(">unknown</span>") == 6
    assert "Binds best at noon" in html and "attuned it, day 1" in html
    assert "Grants" not in _text(html) and "1d6" not in html


def test_the_phase_is_a_phase_of_the_day_never_a_planet(served, drawn):
    """Owner round 4 point 10: "this is not earth" and named planets are not
    world-agnostic, so the essence card says its phase of the day in words ("binds best at
    noon"; the server's "Noon, 42 minutes left" when it sends `phase_words`) and no planet
    or planet sign appears anywhere in the new files."""
    assert '<p class="el-phase">Noon, 42 minutes left</p>' in drawn["phaseWords"]
    planets = r"\b(mars|venus|jupiter|saturn|mercury|planet|planetary)\b|[☉☽♂☿♃♀♄]"
    for path in (LEDGER, PERKS, SHEET_TAB, EQUIP_TAB):
        code = re.sub(r"//.*", "", _src(path)).lower()
        assert not re.search(planets, code), path.name
    for html in (drawn["flaming"], drawn["vorpal"]):
        assert not re.search(planets, html.lower())


def test_every_number_on_the_essence_card_is_one_the_server_sent(served, drawn):
    """UI plan §12, "the page never computes a number": the forge ledger's first cut printed
    a count it had made by counting rows. Every run of digits on the drawn card must be in
    the server's own answer."""
    sent = json.dumps(served["flaming"])
    for html in (drawn["flaming"], drawn["none"]):
        for n in re.findall(r"\d+", _text(html)):
            assert n in sent, (n, _text(html))


def test_read_is_offered_with_its_cost_and_refused_in_words_with_none_carried(drawn):
    """UI plan §6.8: Read is a pinch (a tenth of a phial) and ten minutes, said on the
    button from the server's `read_cost` and `read_minutes`; with none carried it is
    disabled and says why beside it (a greyed button with no reason is the defect the
    shelf's "never colour alone" rule exists for)."""
    assert ">Read<" in drawn["flaming"] and "a tenth of a phial, 10 minutes" in drawn["flaming"]
    assert 'data-el="read" disabled aria-describedby="el-read-why"' in drawn["none"]
    assert "You carry none of it to take a pinch from." in drawn["none"]


def test_a_volatile_read_asks_first_only_once_volatile_is_known(served, drawn):
    """UI plan §6.7: reading a volatile essence asks first in --alarm words, Keep it before
    Read it. But the essence route sends `volatile` whatever is known: a confirm keyed on it
    would teach the trait before any read (vorpal's card said nothing of it, yet asked).
    So it asks once "volatile" is a known working trait, and the hard way before that."""
    assert served["vorpal"]["volatile"] is True
    assert drawn["vorpalConfirm"] is False and drawn["vorpalKnown"] is True
    c = drawn["confirm"]
    assert '<p class="el-alarm">This essence bites the one who reads it. Read it anyway?</p>' in c
    assert c.index(">Keep it<") < c.index(">Read it<") and "bench-danger" in c


def test_the_swatch_takes_only_a_plain_colour(drawn):
    """The swatch's colour goes into a style attribute, and it is data: a value with a
    semicolon would let an essence document restyle the card."""
    assert "el-swatch" not in drawn["swatchBad"]
    assert 'style="background:#e0703a"' in drawn["flaming"]


# --- the Journal and the recipes ------------------------------------------------------------

def test_the_journal_says_the_servers_unknown_counts_and_sorts_by_them(served, drawn):
    """The Journal's Essences section prints the ledger's own `unknown` ("6 still
    unknown"), never a count made on the page, and "Unknowns first" puts the least known
    essence on top: vorpal (all unknown) must lead flaming, which leads it by name."""
    rows = {r["id"]: r for r in served["ledger"]["ledger"]}
    text = _text(drawn["rows"])
    assert "6 still unknown" in text and f"{rows['vorpal-essence']['unknown']} still unknown" in text
    plain, first = drawn["rows"], drawn["rowsFirst"]
    assert plain.index('data-el-ess="flaming-essence"') < plain.index('data-el-ess="vorpal-essence"')
    assert first.index('data-el-ess="vorpal-essence"') < first.index('data-el-ess="flaming-essence"')
    opened = drawn["rowsOpen"]
    assert 'aria-expanded="true" aria-controls="el-jr-card-flaming-essence"' in opened
    assert "attuned it, day 1" in opened


def test_the_journal_says_what_to_do_when_empty_or_reading(drawn):
    """Empty and loading states (the skill's §4.5): an empty ledger invites the act that
    fills it; a read in flight says so."""
    assert "No essences yet. Buy, find or harvest one and it appears here." in drawn["rowsEmpty"]
    assert "Reading the ledger." in drawn["rowsReading"]


def test_a_recipe_learned_by_identify_is_listed_with_what_it_needs(served, drawn):
    """UI plan §6.8: identifying a catalogue item teaches its recipe (lane F), and Recipes
    lists it with what it needs; Load hands it to the bench and is disabled, with the
    reason, for a recipe beyond the Enchanter's level."""
    names = [r["name"] for r in served["recipes"]["recipes"]]
    assert "Ring of Protection +1" in names
    assert "Ring of Protection +1" in drawn["recipes"] and "Needs" in drawn["recipes"]
    assert 'data-el-load="mi-ring-protection-1">Load<' in drawn["recipes"]
    assert 'disabled aria-describedby="el-rc-why-mi-ring-protection-1"' in drawn["recipesCant"]
    assert "Beyond your Enchanter level for now." in drawn["recipesCant"]
    assert "No recipes yet." in drawn["recipesNone"]


def test_the_journal_mounts_the_section_after_the_smiths_ledger():
    """Read statically: 21 adds "Essences and recipes" after the smith's ledger (or the
    herbarium), its list id not the heading's id (the history card's first cut replaced its
    own heading by sharing one), and only when 49 is loaded, so a page without it shows no
    empty card."""
    js = _src(JOURNAL)
    assert 'sheetCard("jr-essences", "Essences and recipes", `<div id="jr-essences-list"></div>`' in js
    assert "window.EnchantLedger.journal(document.getElementById(\"jr-essences-list\"))" in js
    assert "herbariumMount(); ledgerMount(); essencesMount();" in js


# --- the item card and Identify --------------------------------------------------------------

def test_a_found_item_says_its_aura_and_offers_identify_and_nothing_more(served, drawn):
    """UI plan §6.6: an unidentified item reads "Magic, faint aura" and offers Identify. A
    card that listed the ring's powers before it was identified would hand over what the
    roll exists to earn."""
    html = drawn["items"][served["ring_key"]]
    assert "<b>Magic</b>, faint aura" in html and "Not identified." in html
    assert "Protection" not in html and "Caster level" not in html
    assert 'data-el-identify="' + served["ring_key"] + '"' in html and ">Identify<" in html


def test_a_flawed_binding_says_flawed_and_never_which_curse(served, drawn):
    """Owner round 4 point 2: a flawed binding is known to be flawed, never which curse.
    The flawed sword's section says FLAWED and that the curse is not known; neither the
    curse's words nor any part of its record (id, row, tags, d100) may appear, and Identify
    stays offered because the curse question is open. Once identified by 10 the curse's
    words appear, and Identify goes, since nothing is left to learn."""
    html = drawn["items"]["stock:flawed-sword"]
    assert "FLAWED" in html and "Which curse it carries is not known." in html
    assert "+1 enhancement" in html and "not yet checked for a curse" in html
    assert served["curse_words"] not in _text(html)
    for secret in SECRETS:
        assert secret not in html.lower(), secret
    assert drawn["can"]["stock:flawed-sword"] is True
    known = drawn["items"]["stock:known-cursed"]
    assert "Curse" in known and served["curse_words"][:30] in _text(known)
    assert drawn["can"]["stock:known-cursed"] is False and "data-el-identify" not in known


def test_no_curse_record_reaches_the_state_the_cards_are_read_from(served):
    """The item cards come from `/api/enchant/state`; a state that carried the curse record
    of an item whose curse is unknown would put it in the page whatever the renderer does.
    The flawed sword's record is swept for in the very answer the tabs read."""
    text = served["state_text"]
    for secret in ("curse:opposite", "curse.opposite", '"opposite"', '"d100"',
                   "item:flawed-sword"):
        assert secret not in text, secret


def test_identify_says_the_dc_the_roll_and_the_verdict_in_words(served, drawn):
    """The brief: Identify "shows the DC, the roll, and the verdict in words". The line is
    built from the server's answer (face, bonus, total, DC, words), so a 20 on the ring
    reads its own numbers and "You learn what it was made to do."; a second try that day is
    the first answer again (CRB Spellcraft) and must say so rather than print the new die
    as if it counted, and a failed answer does not say "tomorrow" twice."""
    r = served["identify"]
    roll = r["roll"]
    line = drawn["identifyLine"]
    assert line == (f"Identify the Plain silver ring: d20 {roll['face']} +{roll['bonus']} = "
                    f"{roll['total']} against DC {r['dc']}. {r['words']}")
    assert r["result"] in ("intent", "curse")
    again = served["identify_again"]
    assert again["repeat"] is True
    assert drawn["identifyAgain"].startswith("You studied the Plain silver ring today already, "
                                             f"and the answer stands (DC {again['dc']})")
    assert "d20 1 " not in drawn["identifyAgain"]
    assert drawn["identifyFail"].count("tomorrow") == 1


def test_an_identified_items_card_says_what_it_does_and_its_caster_level(served, drawn):
    """After Identify the card carries the intent (lane F's lines), the caster level and
    "as the maker intended" while the curse check is still open (the roll beat the DC by
    less than 10, or exactly by the face the test threw)."""
    card = served["identify"]["card"]
    html = drawn["identified"]
    assert card["identified"] is True
    for line in card["lines"]:
        assert line in html
    assert f"Caster level {card['caster_level']}." in html


def test_a_renamed_entry_still_finds_its_card_by_name(drawn):
    """The Equipment row's id is "stock:<the entry's id>", which a binding's rename moves
    away from the shelf key it was stored under (Stock.id is a slug of the name). The
    section falls back on the name so a renamed ring still shows its magic."""
    assert drawn["byName"] and drawn["byName"]["key"] == "stock:x"


def test_the_tabs_place_the_section_and_identify_after_each_draw():
    """Read statically: 05-sheet.js draws the pages and this lane does not own it, so 18
    adds the section after each draw (an observer on #sheetbody's children, as 21 adds the
    herbarium) with Identify among the row's acts, and 17 adds a "Magic carried" card after
    Defence; both read the cards through `EnchantLedger.items` and identify through one
    handler, so the two tabs cannot disagree about an item."""
    eq, sh = _src(EQUIP_TAB), _src(SHEET_TAB)
    assert "new MutationObserver(() => eqMagicDraw())" in eq
    assert 'acts.insertAdjacentHTML("beforeend"' in eq and "data-el-identify" in eq
    assert "L.identify(key, { name })" in eq
    assert 'sheetCard("sh-magic", "Magic carried"' in sh
    assert "await L.items()" in eq and "EnchantLedger.items()" in sh


def test_the_ledger_module_answers_its_contract(drawn):
    """Contracts §13: `EnchantLedger.card(essenceId, anchorEl)`, `.recipes(host)` and
    `.journal(host)`, the names lane U1's bench calls, plus the item card's helpers the
    two tabs use."""
    assert drawn["api"] == []


# --- the perk picker ----------------------------------------------------------------------

def test_the_enchanter_picker_offers_its_four_perks_with_the_servers_words(served):
    """Enchanting answers round 2, "Levels": potency, quality, yield and capacity, the
    enchanter's own. Each choice says what the next pick does in lane E's words with its
    numbers (`perk_info[id].next`), the level line reads "Enchanter", and the picks post to
    the enchant route. Hardening is a smith's perk and duration a herbalist's; on this track
    either would post a pick the server refuses."""
    track = dict(served["track"], picks_banked=2)
    run = _node("perks", {"track": track})
    html = run["html"]
    for perk in ("potency", "quality", "yield", "capacity"):
        assert f'data-perk="{perk}"' in html
        assert track["perk_info"][perk]["next"] in html.replace("&#39;", "'")
    assert 'data-perk="hardening"' not in html and 'data-perk="duration"' not in html
    assert '<h3 id="enchant-perks-t">Pick two perks</h3>' in html
    assert f"<p>Enchanter {track['level']}. The same perk twice is allowed.</p>" in html
    assert run["posts"] == [["/api/enchant/perks", {"picks": ["capacity", "potency"]}]]
    assert run["saved"] == [["capacity", "potency"]] and run["closed"]
    assert not any(re.search(r"\d", p["words"]) for p in run["row"]["perks"]), \
        "a fallback word carries a number the server did not send"


# --- static rules ------------------------------------------------------------------------------

def test_one_esc_closes_the_card_and_not_the_journal_under_it():
    """The forge ledger's live finding (2026-10-04): a card listening on the document's
    bubble phase closed itself AND the Journal on one Esc. Off a bench the card and its
    confirm take Esc in the capture phase and stop it there; on a bench they use the core's
    Esc stack."""
    code = _src(LEDGER)
    assert 'document.addEventListener("keydown", looseEsc, true)' in code
    block = code[code.index("looseEsc = function"):code.index('document.addEventListener("keydown", looseEsc, true)')]
    assert "e.stopPropagation()" in block
    assert 'document.addEventListener("keydown", onKey, true)' in code
    assert "h.pushEsc(escClose)" in code and "h.pushEsc(onEsc)" in code


def test_no_loop_no_dash_no_emoji_in_the_new_code():
    """The benches' standing rules (UI plan §8, §14): nothing loops while idle (no
    setInterval, no requestAnimationFrame), no em-dashes or en-dashes in new strings, and
    no emoji (retired with the old tab's glyphs, UI plan §2)."""
    parts = [_src(LEDGER), _src(EQUIP_TAB)[_src(EQUIP_TAB).index("// --- The item card"):],
             _src(SHEET_TAB)[_src(SHEET_TAB).index("// --- Magic carried"):],
             _src(JOURNAL)[_src(JOURNAL).index("// --- Essences and recipes"):]]
    perks = _src(PERKS)
    parts.append(perks[perks.index("// The enchanter's four"):perks.index("var escHtml")])
    for text in parts:
        assert not re.findall(r"\b(setInterval|requestAnimationFrame)\s*\(", text)
        assert "—" not in text and "–" not in text
        assert not re.search("[\U0001F300-\U0001FAFF☀-➿]", text)
