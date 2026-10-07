"""The alchemist's books: the reagent card, the Formulary, the codex (the bench's and the
Journal's), Identify on a potion in the pack, and the alchemist's row in the perk picker
(docs/alchemy-ui-plan.md §6.7, §6.8, §6.10; contracts §11 and §12). Lane U4.

The card, Formulary and codex are play/static/js/table/54-alchemy-books.js
(`window.AlchemyBooks`); the Journal mounts the codex from 21-tab-journal.js; the picker is
36-bench-perks.js with an `alchemist` track. The behaviour checks load the real files into
node with a small fake DOM, as tests/test_enchant_ledger_ui.py does, and feed them the REAL
server's answers: a campaign is begun, reagents, a potion and a scroll are carried, and the
alchemy routes are driven through the Django test client (a real assay of quicksilver, a
real Identify, a real potion taken apart). They skip, saying why, where node is not
installed. Each test names the defect it prevents.
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

from play import alchemy_views
from play import campaign as cm
from rules import alchemy_items, goods
from rules.crafting import Stock
from rules.sheet import load_pc

ROOT = Path(__file__).resolve().parent.parent
TABLE_JS = ROOT / "play" / "static" / "js" / "table"
BOOKS = TABLE_JS / "54-alchemy-books.js"
PERKS = TABLE_JS / "36-bench-perks.js"
JOURNAL = TABLE_JS / "21-tab-journal.js"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _post(client, url, body):
    r = client.post(url, data=json.dumps(body), content_type="application/json")
    assert r.status_code == 200, r.content[:600]
    return r.json()


# --- the server's answers, from a real campaign -----------------------------------------------

@pytest.fixture(scope="module")
def served(tmp_path_factory):
    """What the page is given: the real views over the real knowledge, formulae and items
    (no fakes), on a scratch campaign dir."""
    tmp = tmp_path_factory.mktemp("alchemy-books")
    with override_settings(CAMPAIGN_DIR=tmp / "campaigns"):
        cm._LIVE.clear()
        alchemy_views._PENDING.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"), start_id="quiet-the-bread-stall")
        pc = c.scene.pc()
        pc.inventory.clear()
        pc.stock.clear()
        pc.herb_known.clear()
        pc.purse = {"gp": 200}
        c.save()
        client = Client()
        out = {"empty_codex": client.get("/api/alchemy/codex").json()}
        goods.deliver(c.scene, pc, goods.good("alchemist's field kit"))
        pc.carry("quicksilver", 1)
        pc.carry("brimstone", 2)
        # Alum, a salt nothing is known of: the codex lists by kind then name (reagents, then
        # salts), so it comes after quicksilver plainly and before it by unknowns.
        pc.carry("alum", 1)
        key = alchemy_items.put(pc, alchemy_items.record_for_formula("potion-of-cure-light-wounds"), 1)
        pc.add_stock(Stock(base="Scroll of Haste", craft="enchanter", holds_spell="haste",
                           count=1, kind="scroll"), 1)
        c.save()
        out["potion_key"] = f"stock:{key}"
        out["qs_before"] = client.get("/api/alchemy/material/quicksilver").json()
        out["codex_before"] = client.get("/api/alchemy/codex").json()
        out["formulary_before"] = client.get("/api/alchemy/formulary").json()
        out["assay"] = _post(client, "/api/alchemy/assay", {"material": "quicksilver", "face": 20})
        out["qs_after"] = client.get("/api/alchemy/material/quicksilver").json()
        out["brimstone"] = client.get("/api/alchemy/material/brimstone").json()
        out["codex_after"] = client.get("/api/alchemy/codex").json()
        out["identify"] = _post(client, "/api/alchemy/identify", {"item": out["potion_key"], "face": 20})
        out["identify_miss"] = _post(client, "/api/alchemy/identify", {"item": out["potion_key"], "face": 1})
        out["learn"] = _post(client, "/api/alchemy/learn", {"from": "potion", "item": out["potion_key"],
                                                            "face": 20})
        scroll = next(w for w in out["formulary_before"]["writings"] if w["route"] == "scroll")
        out["learn_scroll"] = _post(client, "/api/alchemy/learn", {"from": "scroll", "item": scroll["item"],
                                                                   "face": 20})
        out["formulary_after"] = client.get("/api/alchemy/formulary").json()
        out["track"] = client.get("/api/alchemy/state").json()["track"]
        cm._LIVE.clear()
        alchemy_views._PENDING.clear()
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
  querySelectorAll() { return []; }
  contains(x) { return x === this; }
  focus() {}
}
const ids = {};
const doc = { activeElement: null, cookie: '', head: new El(), body: new El(),
  getElementById: (id) => ids[id] || null, createElement: () => new El(), querySelector: () => null,
  querySelectorAll: () => [], addEventListener() {}, dispatchEvent() {}, contains: (x) => !!x && !x.removed };
const sandbox = { document: doc, console, setTimeout, clearTimeout, Promise, JSON, Object, Array,
  String, Number, Math, Error, RegExp, isFinite, addEventListener() {}, innerWidth: 1600, innerHeight: 900,
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
    const run = async (track, state, picks) => {
      const pops = new El(); const posts = []; const saved = [];
      const wrap = P.open({ track, state, pops,
        api: (p, b) => { posts.push([p, b]); return Promise.resolve(Object.assign({}, state, { picks_banked: 0 })); },
        saved: (t, pk) => saved.push(pk) });
      const html = wrap.innerHTML;
      const click = (map) => wrap.listeners.click.forEach((f) => f({ target: target(map) }));
      for (const p of picks) click({ '[data-perk]': { dataset: { perk: p } } });
      click({ '[data-pk]': { dataset: { pk: 'ok' }, disabled: false } });
      await tick(); await tick();
      return { html, posts, saved, closed: wrap.removed };
    };
    out.alchemist = await run('alchemist', data.track, ['containment', 'potency']);
    out.herb = await run('herbalist', Object.assign({}, data.track, { perk_info: {} }), ['potency', 'yield']);
    out.row = P.tracks.alchemist;
  }
  if (args.mode === 'books') {
    vm.runInContext(fs.readFileSync(args.books, 'utf8'), sandbox);
    const B = sandbox.AlchemyBooks, R = B.render;
    out.api = ['card', 'peek', 'unpeek', 'close', 'forget', 'formulary', 'codex', 'identify', 'learn']
      .filter((n) => typeof B[n] !== 'function');
    out.before = R.card(data.qs_before, { actions: true, pinned: true });
    out.after = R.card(data.qs_after, { actions: true });
    out.none = R.card(Object.assign({}, data.qs_after, { carried: 0 }), { actions: true });
    out.teacher = R.card(Object.assign({}, data.qs_after, { teachers: [{ ref: 'npc:mirela', name: 'Mirela', price: '5 gp' }] }), { actions: true });
    out.brimstone = R.card(data.brimstone, { actions: true });
    out.confirmBlind = R.needsConfirm(data.qs_before, {});
    out.confirmShelf = R.needsConfirm(data.qs_before, { hazards: ['toxic to handle'] });
    out.confirmHood = R.needsConfirm(data.qs_before, { hazards: ['toxic to handle'], where: { protected: "the laboratory's fume hood" } });
    out.confirmVolatile = R.needsConfirm(data.brimstone, { hazards: ['volatile'], where: { protected: "the laboratory's fume hood" } });
    out.confirmBare = R.confirm(data.qs_before, { hazards: ['toxic to handle'], where: { protected: '' } });
    out.confirmUnsaid = R.confirm(data.qs_before, { hazards: ['toxic to handle'] });
    out.knownToxic = R.needsConfirm(Object.assign({}, data.qs_after, { properties: data.qs_after.properties.map(
      (p) => p.group === 'toxic' ? Object.assign({}, p, { known: true, text: 'Fortitude DC 14', how: 'assayed, day 2' }) : p) }), {});
    out.colour = R.colour(data.qs_before.color);
    out.colourBad = R.colour('red;background:url(x)');
    out.assayLine = R.assayLine(data.assay);
    out.identifyLine = R.identifyLine(data.identify, 'Potion of Cure Light Wounds');
    out.identifyMiss = R.identifyLine(data.identify_miss, 'Potion of Cure Light Wounds');
    out.learnLine = R.learnLine(data.learn);
    out.learnScroll = R.learnLine(data.learn_scroll);
    const st = (d) => ({ data: d, error: '', msg: '', busy: false, said: {} });
    out.formBefore = R.formulary(st(data.formulary_before));
    out.formAfter = R.formulary(st(data.formulary_after));
    out.formReading = R.formulary(st(null));
    out.formError = R.formulary(Object.assign(st(null), { error: "Couldn't read your formulary. HTTP 500" }));
    const potion = data.formulary_before.writings.filter((w) => w.route === 'potion')[0];
    out.potionRenamed = R.writing(Object.assign({}, potion, { name: 'Murky red vial' }), st(null));
    out.potionPlan = R.planWords(potion);
    const scroll = data.formulary_before.writings.filter((w) => w.route === 'scroll')[0];
    out.scroll = R.writing(scroll, st(null));
    out.scrollRefused = R.writing(Object.assign({}, scroll, { plan: Object.assign({}, scroll.plan, {
      refused: ['You failed to copy Potion of Haste within the week; you may try again on day 9.'] }) }), st(null));
    out.potionSection = R.potion(data.potion_key, potion);
    const cx = (rows, o) => R.codexRows(Object.assign({ codex: rows, error: '', open: '', unknownFirst: false, cards: {} }, o || {}));
    out.codexBefore = cx(data.codex_before.codex);
    out.codexAfter = cx(data.codex_after.codex);
    out.codexFirst = cx(data.codex_after.codex, { unknownFirst: true });
    out.codexOpen = cx(data.codex_after.codex, { open: 'quicksilver', cards: { quicksilver: data.qs_after } });
    out.codexEmpty = cx(data.empty_codex.codex);
    out.codexReading = cx(null);
  }
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""


def _node(mode: str, data: dict) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed; the behaviour checks need a JS engine")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "books.js"
        script.write_text(_NODE, encoding="utf-8")
        blob = Path(tmp) / "data.json"
        blob.write_text(json.dumps(data), encoding="utf-8")
        done = subprocess.run([node, str(script), json.dumps({
            "mode": mode, "data": str(blob), "perks": str(PERKS), "books": str(BOOKS)})],
            capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert done.returncode == 0, done.stderr[:2000]
    return json.loads(done.stdout)


@pytest.fixture(scope="module")
def drawn(served):
    return _node("books", served)


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip().replace("&#39;", "'")


# --- the reagent card ----------------------------------------------------------------------

def test_an_unassayed_reagent_shows_an_unknown_line_per_property_and_nothing_else(served, drawn):
    """Lane A's knowledge: nothing about quicksilver is known before an assay, so the card
    must say "unknown" five times and nothing of what it does. The route sends each unknown
    row's list (`group`: "toxic"), and a careless card prints it: "toxic" beside an unknown
    line teaches the danger before any assay. The document's own `text` ("poisons the blood
    together") gives the properties away in prose, so it is not drawn at all."""
    card = served["qs_before"]
    assert card["unknown"] == 5 and any(p["group"] == "toxic" for p in card["properties"])
    html = drawn["before"]
    assert html.count(">unknown</span>") == 5
    text = _text(html).lower()
    for secret in ("toxic", "constitution", "speed", "harmful", "poison", "mishap"):
        assert secret not in text, secret
    assert "In the bottle" in html and "At the bench" in html


def test_an_assay_fills_the_card_with_what_it_taught_and_how(served, drawn):
    """A real assay at 20 revealed one benefit and one drawback (plan §13.2). The card after
    it says both, each with "assayed, day 1", marks only the drawback harmful, keeps three
    unknown lines, and says the known danger from the server's `danger_known` alone."""
    revealed = [r["text"] for r in served["assay"]["revealed"]]
    assert len(revealed) == 2
    html, text = drawn["after"], _text(drawn["after"])
    for line in revealed:
        assert line[:1].upper() + line[1:] in text
    assert html.count("assayed, day 1") == 2 and html.count(">harmful<") == 1
    assert html.count(">unknown</span>") == served["qs_after"]["unknown"] == 3
    assert f"You know this can hurt you: {served['qs_after']['danger_known']}." in text


def test_every_number_on_the_card_is_one_the_server_sent(served, drawn):
    """UI plan §12, "the page never computes a number": the forge ledger's first cut printed
    a count it had made by counting rows. Every run of digits on the drawn card must be in
    the server's own answer."""
    sent = json.dumps(served["qs_after"])
    for html in (drawn["after"], drawn["none"]):
        for n in re.findall(r"\d+", _text(html)):
            assert n in sent, (n, _text(html))


def test_assay_is_offered_with_its_cost_and_refused_in_words_with_none_carried(drawn):
    """UI plan §6.8: Assay is a pinch and ten minutes, said on the button from the server's
    `assay`; with none carried it is disabled and says why beside it (a greyed button with
    no reason is the defect the shelf's "never colour alone" rule exists for). Ask an
    alchemist appears only when one is in the scene, by name, with the price."""
    assert ">Assay<" in drawn["after"] and "a tenth of one you carry, 10 minutes" in drawn["after"]
    assert 'data-ab="assay" disabled aria-describedby="ab-assay-why"' in drawn["none"]
    assert "You carry none of it to take a pinch from." in drawn["none"]
    assert 'data-ab="ask"' not in drawn["after"]
    assert 'data-ab-ref="npc:mirela"' in drawn["teacher"] and "Ask Mirela" in drawn["teacher"]
    assert "5 gp" in drawn["teacher"]


def test_a_dangerous_assay_asks_first_only_on_what_the_player_was_told(drawn):
    """UI plan §6.8: assaying a toxic or volatile reagent asks first, in --alarm words, Keep
    it before Assay it. Keyed on anything the player was not told, the confirm would itself
    teach the hazard (the enchanter's card asked about `volatile` before any read). So it
    asks when the shelf has named the hazard (it always names these two, plan §8.1), or the
    toxic or mishap row is known; never on a blind card. A fume hood spares a toxic assay,
    so only a volatile one asks there."""
    assert drawn["confirmBlind"] is False
    assert drawn["confirmShelf"] is True and drawn["knownToxic"] is True
    assert drawn["confirmHood"] is False and drawn["confirmVolatile"] is True
    bare = drawn["confirmBare"]
    assert '<p class="ab-alarm">Quicksilver is toxic to handle, and you wear no mask. Assay it anyway?</p>' in bare
    assert bare.index(">Keep it<") < bare.index(">Assay it<") and "bench-danger" in bare
    # Without the bench's word on protection, nothing is claimed about a mask.
    assert "mask" not in drawn["confirmUnsaid"] and "toxic to handle." in drawn["confirmUnsaid"]


def test_the_swatch_takes_the_servers_colour_and_only_a_plain_one(served, drawn):
    """A reagent's colour is the material document's [r, g, b] (plan §5.2), turned into a CSS
    colour; it goes into a style attribute and is data, so a value with a semicolon would
    let a document restyle the card."""
    assert served["qs_before"]["color"] == [0.8, 0.82, 0.85]
    assert drawn["colour"] == "rgb(204, 209, 217)"
    assert drawn["colourBad"] == ""
    assert 'style="background:rgb(204, 209, 217)"' in drawn["before"]


def test_the_assay_answer_says_the_roll_what_was_learned_and_what_it_cost(served, drawn):
    """The assay's line is the server's: face, bonus, total and DC, the properties revealed,
    and the toxic tell that landed on the unprotected assayer (plan §13.2: "dangerous for
    real"). A line that said only "Learned" would hide the Constitution damage just taken."""
    a = served["assay"]
    roll = a["roll"]
    line = drawn["assayLine"]
    assert line.startswith(f"You assay a pinch of Quicksilver (d20 {roll['face']} +{roll['bonus']} = "
                           f"{roll['total']} against DC {roll['dc']}). Learned: ")
    assert a["danger_applied"] and all(d["tell"] in line for d in a["danger_applied"] if d["tell"])
    assert line.endswith("10 minutes passed.")


# --- the Formulary --------------------------------------------------------------------------

def test_the_formulary_lists_known_formulae_by_family_with_how_and_what_they_need(served, drawn):
    """UI plan §6.7: known formulae grouped by family, each with its requirement in essences
    and how it was learned. A new alchemist knows the four classics "from the start"
    (owner Q5.4); a classic says its book, without the link it was checked against."""
    html, text = drawn["formBefore"], _text(drawn["formBefore"])
    for f in served["formulary_before"]["formulae"]:
        assert f["name"] in text
    assert "Splash flasks" in text and "Potions" in text
    assert "Known from the start, day 1" in text and "Needs acid" in text
    assert "CRB, Goods and Services" in text
    assert "aonprd" not in html and "aspx" not in html
    # Measured live 2026-10-07: the antitoxin's source carried its rules line after a colon.
    assert "+5 alchemical bonus" not in text


def test_a_potion_taken_apart_is_written_with_how_it_was_learned(served, drawn):
    """Owner, open point 9: spend the potion to learn its formula. After a real take-apart,
    the formulary lists Potion of Cure Light Wounds "learned from a potion, day 1" with its
    spell level, caster level and price as the server sent them; and the potion has left
    the writings, because it was spent."""
    f = next(x for x in served["formulary_after"]["formulae"] if x["id"] == "potion-of-cure-light-wounds")
    text = _text(drawn["formAfter"])
    assert "Learned from a potion, day 1" in text
    assert f"spell level {f['spell_level']}, caster level {f['caster_level']}, {f['price_gp']:g} gp" in text
    assert not any(w["route"] == "potion" for w in served["formulary_after"]["writings"])
    assert drawn["learnLine"] == ("You learn the formula for Potion of Cure Light Wounds "
                                  f"(d20 20, total {served['learn']['total']} against DC "
                                  f"{served['learn']['result']['dc']}). The potion is spent. "
                                  "1 hour passed.")


def test_a_potion_is_offered_by_its_own_name_never_by_the_formula_it_hides(served, drawn):
    """Owner Q5.3, "never an unknown name": the formulary route names the formula a carried
    potion would teach (`formula`), and a page that printed it would name an unknown
    formula for a vial whose label says nothing. Renamed "Murky red vial", the row must
    not say cure light wounds; it offers Identify and Take it apart, and says the potion
    is spent whatever the roll."""
    html = drawn["potionRenamed"]
    assert "Murky red vial" in html and "cure light" not in html.lower()
    assert ">Identify<" in html and ">Take it apart<" in html and "bench-danger" in html
    assert drawn["potionPlan"].endswith("The potion is spent whatever the roll.")
    assert "An Alchemist check against DC 16" in drawn["potionPlan"]


def test_a_scroll_offers_learn_from_a_writing_with_its_check_cost_and_wait(served, drawn):
    """UI plan §6.7: Learn from a writing shows the check, the DC, the cost in words and the
    one-week wait after a failure; a writing refused (the week not yet out) is disabled
    with the server's reason beside it."""
    w = next(x for x in served["formulary_before"]["writings"] if x["route"] == "scroll")
    html = drawn["scroll"]
    assert ">Learn from a writing<" in html and "Writes down Potion of Haste" in _text(html)
    assert (f"An Alchemist check against DC {w['plan']['dc']}, {w['plan']['cost_gp']} gp in inks and paper, "
            "4 hours.") in _text(html)
    assert "try again in a week" in html
    refused = drawn["scrollRefused"]
    assert "disabled aria-describedby=" in refused and "you may try again on day 9." in refused
    # A real copy at 20: the scroll is used up and the inks paid (the live run first said
    # "the writing is spent" of a scroll).
    got = served["learn_scroll"]
    assert got["result"]["learned"] and got["result"]["spent"]
    assert drawn["learnScroll"] == (f"You learn the formula for Potion of Haste (d20 20, total {got['total']} "
                                    f"against DC {w['plan']['dc']}). The scroll is spent. Paid {got['paid']}. "
                                    "4 hours passed.")


def test_the_formulary_says_what_to_do_when_reading_or_failed(drawn):
    """Empty, loading and error states (the skill's §4.5)."""
    assert "Reading your formulary." in drawn["formReading"]
    assert "Couldn&#39;t read your formulary." in drawn["formError"] and "data-ab-retry" in drawn["formError"]


def test_identify_says_the_dc_the_roll_and_what_the_potion_holds(served, drawn):
    """Plan §11.3 (owner confirmed): Identify is DC 15 + spell level, the alchemist's own
    check. The line is the server's numbers; a miss says it gives up nothing rather than
    printing a spell the response did not carry."""
    r = served["identify"]
    assert r["dc"] == 16 and r["success"]
    assert drawn["identifyLine"] == ("Identify the Potion of Cure Light Wounds: d20 20 +2 = "
                                     f"{r['total']} against DC 16. It holds cure light wounds, "
                                     f"spell level 1, caster level {r['caster_level']}.")
    assert "It gives up nothing." in drawn["identifyMiss"]
    assert "cure light wounds" not in drawn["identifyMiss"].split(":", 1)[1]


def test_a_potion_in_the_pack_gets_its_own_section_and_identify_on_the_equipment_tab(served, drawn):
    """The enchanter's item card pattern (18-tab-equipment.js): a section added after each
    draw of the Equipment page, and Identify among the row's acts. A potion is not one of
    the enchanter's vessels, so it had no section and nowhere to be identified. Which rows
    are potions is the server's word (the formulary's `writings`), never read off a name."""
    assert "Potion</b>, it holds a spell." in drawn["potionSection"]
    code = _src(BOOKS)
    assert "new MutationObserver(potionWatch).observe(body, { childList: true })" in code
    assert 'if (w.route === "potion") map[w.item] = w;' in code
    assert 'acts.insertAdjacentHTML("beforeend"' in code and "data-ab-identify" in code


# --- the codex --------------------------------------------------------------------------------

def test_the_codex_says_the_servers_counts_and_sorts_unknowns_first(served, drawn):
    """UI plan §6.8: "3 of 7 known", the server's two numbers side by side, never a count
    made on the page; "Unknowns first" puts the least known reagent on top. After the
    assay quicksilver is 2 of 5 known; alum, a salt listed after the reagents, is 0 known of
    more than quicksilver's 3 unknown, so it must rise above quicksilver."""
    rows = {r["id"]: r for r in served["codex_after"]["codex"]}
    assert (rows["quicksilver"]["known"], rows["quicksilver"]["total"]) == (2, 5)
    assert rows["alum"]["known"] == 0 and rows["alum"]["total"] > 3
    text = _text(drawn["codexAfter"])
    assert "2 of 5 known" in text and f"0 of {rows['brimstone']['total']} known" in text
    plain, first = drawn["codexAfter"], drawn["codexFirst"]
    assert plain.index('data-ab-cx="quicksilver"') < plain.index('data-ab-cx="alum"')
    assert first.index('data-ab-cx="alum"') < first.index('data-ab-cx="quicksilver"')
    opened = drawn["codexOpen"]
    assert 'aria-expanded="true" aria-controls="ab-cx-card-quicksilver"' in opened
    assert "assayed, day 1" in opened and opened.count(">unknown</span>") == 3


def test_the_codex_says_what_to_do_when_empty_or_reading(drawn):
    """An empty codex invites the act that fills it; a read in flight says so."""
    assert "No reagents yet. Buy, find or gather one and it appears here." in drawn["codexEmpty"]
    assert "Reading the codex." in drawn["codexReading"]


def test_the_journal_mounts_the_codex_after_the_other_ledgers():
    """Read statically: 21 adds "Alchemist's codex" after the essences (or the smith's ledger,
    or the herbarium), its list id not the heading's id (the history card's first cut
    replaced its own heading by sharing one), and only when 54 is loaded, so a page without
    it shows no empty card."""
    js = _src(JOURNAL)
    assert 'sheetCard("jr-codex", "Alchemist\'s codex", `<div id="jr-codex-list"></div>`, "jr-codex")' in js
    assert 'window.AlchemyBooks.codex(document.getElementById("jr-codex-list"))' in js
    assert "herbariumMount(); ledgerMount(); essencesMount(); codexMount();" in js


def test_the_books_module_answers_its_contract(drawn):
    """Contracts §12: `AlchemyBooks.card(materialId, anchorEl)`, `.formulary(host)` and
    `.codex(host)`, the names lane U1's bench calls, plus Identify and Learn."""
    assert drawn["api"] == []


# --- the perk picker ----------------------------------------------------------------------

def test_the_alchemist_picker_offers_five_perks_with_the_servers_words(served):
    """Owner Q6.2: herbalism's four and Containment. Each choice says what the next pick does
    in lane F's words with its numbers (`perk_info[id].next`), the level line reads
    "Alchemist", and the picks post to the alchemy route. Five is odd, so the last spans
    the row; the four-perk tracks' markup is unchanged (no span), and a fallback word with
    a digit would be a size the server never sent."""
    track = dict(served["track"], picks_banked=2)
    run = _node("perks", {"track": track})
    a = run["alchemist"]
    html = a["html"].replace("&#39;", "'")
    for perk in ("potency", "duration", "quality", "yield", "containment"):
        assert f'data-perk="{perk}"' in html
        assert track["perk_info"][perk]["next"] in html
    assert '<h3 id="alchemy-perks-t">Pick two perks</h3>' in html
    assert f"<p>Alchemist {track['level']}. The same perk twice is allowed.</p>" in html
    assert 'data-perk="containment" style="grid-column: 1 / -1"' in html
    assert a["posts"] == [["/api/alchemy/perks", {"picks": ["containment", "potency"]}]]
    assert a["saved"] == [["containment", "potency"]] and a["closed"]
    assert "grid-column" not in run["herb"]["html"]
    assert not any(re.search(r"\d", p["words"]) for p in run["row"]["perks"])


# --- static rules ------------------------------------------------------------------------------

def test_one_esc_closes_the_card_and_not_the_journal_under_it():
    """The forge ledger's live finding (2026-10-04): a card listening on the document's
    bubble phase closed itself AND the Journal on one Esc. Off a bench the card and its
    confirms take Esc in the capture phase and stop it there; on a bench they use the
    core's Esc stack."""
    code = _src(BOOKS)
    assert 'document.addEventListener("keydown", looseEsc, true)' in code
    block = code[code.index("looseEsc = function"):code.index('document.addEventListener("keydown", looseEsc, true)')]
    assert "e.stopPropagation()" in block
    assert 'document.addEventListener("keydown", onKey, true)' in code
    assert "h.pushEsc(escClose)" in code and "h.pushEsc(onEsc)" in code


def test_no_loop_no_dash_no_emoji_no_planet_in_the_new_code():
    """The benches' standing rules (UI plan §8, §14): nothing loops while idle (no
    setInterval, no requestAnimationFrame), no em-dashes or en-dashes in new strings, no
    emoji (retired with the old tab's glyphs, UI plan §2), and no planet anywhere (owner:
    "this is not earth")."""
    perks, journal = _src(PERKS), _src(JOURNAL)
    parts = [_src(BOOKS),
             perks[perks.index("// The alchemist's five"):perks.index("var escHtml")],
             journal[journal.index("// --- The alchemist's codex"):journal.index("(function watchTheJournal")]]
    planets = r"\b(mars|venus|jupiter|saturn|mercury|planet|planetary)\b|[☉☽♂☿♃♀♄]"
    for text in parts:
        assert not re.findall(r"\b(setInterval|requestAnimationFrame)\s*\(", text)
        assert "—" not in text and "–" not in text
        assert not re.search("[\U0001F300-\U0001FAFF☀-➿]", text)
        assert not re.search(planets, re.sub(r"//.*", "", text).lower())
