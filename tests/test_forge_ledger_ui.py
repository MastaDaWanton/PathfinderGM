"""The forge's ledger card, the Journal's ledger and the perk picker for two tracks
(docs/blacksmithing-ui-plan.md §6.7 and §6.8; contracts §6, §7, §11, §13.2). Lane U5.

The card and the Journal section are play/static/js/table/44-forge-ledger.js
(`window.ForgeLedger`); the picker is 36-bench-perks.js, parameterised by track so the
forge's four perks (potency, hardening, quality, yield) use the herb bench's picker. The
behaviour checks load the real files into node with a small fake DOM, as
tests/test_bench_core.py does, and feed them the REAL server's answers: a campaign is
begun, iron and noqual are carried, one property is learned through rules/knowledge.py,
and `/api/forge/material/<id>`, `/api/forge/ledger` and `/api/forge/state` are read through
the Django test client. They skip, saying why, where node is not installed. Each test
names the defect it prevents.
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
from rules import knowledge
from rules.sheet import load_pc

ROOT = Path(__file__).resolve().parent.parent
TABLE_JS = ROOT / "play" / "static" / "js" / "table"
LEDGER = TABLE_JS / "44-forge-ledger.js"
PERKS = TABLE_JS / "36-bench-perks.js"
JOURNAL = TABLE_JS / "21-tab-journal.js"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- the server's answers, from a real campaign -----------------------------------------------

@pytest.fixture(scope="module")
def served(tmp_path_factory):
    """What the page is given: the real views over the real knowledge and materials
    modules (no fakes), on a scratch campaign dir."""
    tmp = tmp_path_factory.mktemp("forge-ledger")
    with override_settings(CAMPAIGN_DIR=tmp / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"), start_id="quiet-the-bread-stall")
        pc = c.scene.pc()
        pc.inventory.clear()
        pc.stock.clear()
        pc.herb_known.clear()
        client = Client()
        out = {"empty_ledger": client.get("/api/forge/ledger").json()}
        pc.carry("iron", 2)
        pc.carry("noqual", 1)
        keys = knowledge.property_keys(knowledge.material("iron"))
        knowledge.reveal(pc, "iron", [keys[0]], "assayed, day 14")
        c.save()
        out["iron"] = client.get("/api/forge/material/iron").json()
        out["noqual"] = client.get("/api/forge/material/noqual").json()
        out["ledger"] = client.get("/api/forge/ledger").json()
        out["track"] = client.get("/api/forge/state").json()["track"]
        cm._LIVE.clear()
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
  addEventListener() {}, contains: (x) => !!x && !x.removed };
const sandbox = { document: doc, console, setTimeout, clearTimeout, Promise, JSON, Object, Array,
  String, Number, Math, Error, RegExp, addEventListener() {}, innerWidth: 1600, innerHeight: 900 };
sandbox.window = sandbox;
vm.createContext(sandbox);
const tick = () => new Promise((r) => setTimeout(r, 0));
const target = (map) => ({ closest: (sel) => map[sel] || null });
const out = {};
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

(async () => {
  if (args.mode === 'herb') {
    // The herb bench's picker, through whichever 36 is named: the same fake Bench for both.
    ids['bench-pops'] = new El(); ids['bench-foot'] = new El();
    const posts = [], said = [];
    sandbox.Bench = { esc, state: { track: data.herbTrack }, sound() {}, pushEsc() {}, dropEsc() {},
      on() {}, emit() {}, renderFoot() {}, runCheck() {}, say: (t) => said.push(t),
      api: (p, b) => { posts.push([p, b]); return Promise.resolve(data.herbTrack); } };
    vm.runInContext(fs.readFileSync(args.perks, 'utf8'), sandbox);
    sandbox.Bench.openPerks();
    const wrap = ids['bench-pops'].kids[0];
    out.first = wrap.innerHTML;
    const click = (map) => wrap.listeners.click.forEach((f) => f({ target: target(map) }));
    click({ '[data-perk]': { dataset: { perk: 'potency' } } });
    out.second = wrap.innerHTML;
    click({ '[data-perk]': { dataset: { perk: 'quality' } } });
    click({ '[data-pk]': { dataset: { pk: 'ok' }, disabled: false } });
    await tick(); await tick();
    out.posts = posts; out.said = said; out.closed = wrap.removed;
  }
  if (args.mode === 'forge') {
    vm.runInContext(fs.readFileSync(args.perks, 'utf8'), sandbox);
    const P = sandbox.BenchPerks;
    out.has = !!P && typeof P.open === 'function';
    const pops = new El(); const posts = []; const saved = []; let after = 0;
    const wrap = P.open({ track: 'blacksmith', state: data.track, pops,
      api: (p, b) => { posts.push([p, b]); return Promise.resolve(Object.assign({}, data.track, { picks_banked: 0 })); },
      saved: (t, picks) => saved.push(picks), afterClose: () => { after += 1; } });
    out.html = wrap.innerHTML;
    out.second = P.open({ track: 'blacksmith', state: data.track, pops }) === null;
    const click = (map) => wrap.listeners.click.forEach((f) => f({ target: target(map) }));
    click({ '[data-perk]': { dataset: { perk: 'hardening' } } });
    click({ '[data-perk]': { dataset: { perk: 'hardening' } } });
    out.picked = wrap.innerHTML;
    click({ '[data-pk]': { dataset: { pk: 'ok' }, disabled: false } });
    await tick(); await tick();
    out.posts = posts; out.saved = saved; out.after = after; out.closed = wrap.removed;
    out.nothing = P.open({ track: 'blacksmith', state: Object.assign({}, data.track, { picks_banked: 0 }), pops }) === null;
    out.unknownTrack = P.open({ track: 'tailor', state: data.track, pops }) === null;
  }
  if (args.mode === 'ledger') {
    vm.runInContext(fs.readFileSync(args.ledger, 'utf8'), sandbox);
    const L = sandbox.ForgeLedger, R = L.render;
    out.api = ['card', 'journal', 'peek', 'unpeek', 'close', 'forget'].filter((n) => typeof L[n] !== 'function');
    out.iron = R.card(data.iron, { actions: true, pinned: true });
    out.ironJournal = R.props(data.iron);
    out.noqual = R.card(data.noqual, { actions: true });
    out.noqualConfirm = R.needsConfirm(data.noqual);
    out.ironConfirm = R.needsConfirm(data.iron);
    out.confirm = R.confirm(data.noqual);
    out.confirmWords = R.confirm(Object.assign({}, data.noqual, { assay_danger: { text: data.recoil } }));
    out.quietOre = R.needsConfirm(Object.assign({}, data.noqual, { assay_danger: null }));
    out.none = R.card(Object.assign({}, data.iron, { carried: 0 }), { actions: true });
    out.smith = R.card(Object.assign({}, data.iron, { smiths_here: [{ ref: 'npc:brannoc', name: 'Brannoc', price: '5 sp' }] }), { actions: true });
    out.found = R.found({ obtain: 'mined', biomes: ['mountain', 'hills'] });
    out.bought = R.found({ obtain: 'bought', biomes: ['urban'] });
    out.monster = R.found({ obtain: 'harvested', source: 'monster' });
    out.foundNone = R.found({});
    out.rows = R.rows({ ledger: data.ledger.ledger, open: '', cards: {}, unknownFirst: false });
    out.rowsFirst = R.rows({ ledger: data.ledger.ledger, open: '', cards: {}, unknownFirst: true });
    out.rowsEmpty = R.rows({ ledger: data.empty_ledger.ledger, open: '', cards: {} });
    out.rowsReading = R.rows({ ledger: null, open: '', cards: {} });
    out.rowsError = R.rows({ ledger: null, error: "The smith's ledger is not available in this build yet.", open: '', cards: {} });
    out.rowsOpen = R.rows({ ledger: data.ledger.ledger, open: 'iron', cards: { iron: data.iron } });
    out.swatchBad = R.card(Object.assign({}, data.iron, { color: 'red;background:url(x)' }), {});
    out.swatchGood = R.card(Object.assign({}, data.iron, { color: '#8a8d91' }), {});
  }
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""

HERB_TRACK = {"level": 4, "perks": {"potency": 1}, "picks_banked": 2,
              "perk_info": {"potency": {"next": "+5% to the strength of what you make, total +10%"}}}
RECOIL = "Magic recoils: your active magic is suppressed for 1d4 rounds."


def _node(mode: str, data: dict, perks: Path = PERKS) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed; the behaviour checks need a JS engine")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "ledger.js"
        script.write_text(_NODE, encoding="utf-8")
        blob = Path(tmp) / "data.json"
        blob.write_text(json.dumps(data), encoding="utf-8")
        done = subprocess.run([node, str(script), json.dumps({
            "mode": mode, "data": str(blob), "perks": str(perks), "ledger": str(LEDGER)})],
            capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert done.returncode == 0, done.stderr[:2000]
    return json.loads(done.stdout)


@pytest.fixture(scope="module")
def ledger(served):
    return _node("ledger", {**served, "recoil": RECOIL})


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


# --- the card ---------------------------------------------------------------------------------

def test_the_card_shows_what_is_known_how_and_one_line_per_unknown(served, ledger):
    """UI plan §6.7: a known property says what it does and how it was learned ("assayed,
    day 14"); every property still unknown is one "unknown" line, never its text. Iron has
    seven properties; with one learned the card must carry six "unknown" lines. A card
    that printed the material's own effect list would hand the player the discovery the
    whole system exists to make them earn."""
    html = ledger["iron"]
    props = served["iron"]["properties"]
    known = [p for p in props if p["known"]]
    assert len(props) == 7 and len(known) == 1
    assert html.count(">unknown</span>") == 6
    assert known[0]["text"] and known[0]["text"] in _text(html).replace("&#39;", "'")
    assert all(p["text"] is None for p in props if not p["known"]), "the server leaked a secret"
    assert "assayed, day 14" in html
    # The Journal draws the very same lines (one renderer, two surfaces).
    assert ledger["ironJournal"].count(">unknown</span>") == 6 and "assayed, day 14" in ledger["ironJournal"]
    # Grouped under where they act; the group of an unknown line is shown, its text is not.
    assert "In a weapon" in html and "In armour" in html and "At the anvil" in html


def test_every_number_on_the_card_is_one_the_server_sent(served, ledger):
    """UI plan §12: "the page never computes a number". The first cut printed "1 of 7
    known" on the card by counting rows on the page, a number the material endpoint never
    sent. Every run of digits in the drawn card must appear in the server's own answer."""
    sent = json.dumps(served["iron"])
    for html in (ledger["iron"], ledger["noqual"], ledger["smith"]):
        for n in re.findall(r"\d+", _text(html)):
            assert n in sent or n == "5", (n, _text(html))     # 5 sp is the smith's own price


def test_assay_is_offered_with_its_cost_and_refused_in_words_with_nothing_to_cut(ledger):
    """The card's two actions (UI plan §6.7): Assay (a sliver) always shows; with none of
    the material carried it is disabled and the reason is said beside it, because a
    greyed button with no reason is the defect the rack's "never colour alone" rule
    exists for (UI plan §6.2)."""
    assert ">Assay<" in ledger["iron"] and "a sliver" in ledger["iron"]
    assert 'data-fl="assay">' in ledger["iron"]
    none = ledger["none"]
    assert 'data-fl="assay" disabled aria-describedby="fl-assay-why"' in none
    assert "You carry none of it to take a sliver from." in none


def test_ask_a_smith_shows_only_when_the_server_names_one_here(ledger):
    """"Ask a smith (when one is in the scene)": with nobody named the button must not be
    there at all (a button that can only fail is worse than none); with one named it reads
    "Ask a smith", the plan's one label for the intent, and names who and the price."""
    assert "Ask a smith" not in ledger["iron"]
    smith = ledger["smith"]
    assert 'data-fl="ask" data-ref="npc:brannoc"' in smith and ">Ask a smith<" in smith
    assert "Brannoc, 5 sp" in smith


def test_a_reactive_assay_asks_first_in_alarm_words(ledger):
    """UI plan §6.7 and contracts §13.2: assaying a reactive metal hurts for real (abysium
    sickens; noqual's magic recoils and suppresses the assayer's active magic for 1d4
    rounds), so it asks first, in --alarm words, "Noqual reacts badly to testing. Assay it
    anyway?", with Keep it before Assay it. Iron, which is safe, asks nothing: a confirm on
    every assay trains the player to click through the one that matters."""
    assert ledger["noqualConfirm"] is True and ledger["ironConfirm"] is False
    c = ledger["confirm"]
    assert '<p class="fl-alarm">Noqual reacts badly to testing. Assay it anyway?</p>' in c
    assert c.index(">Keep it<") < c.index(">Assay it<")
    assert "bench-danger" in c


def test_the_confirm_says_what_the_server_says_the_assay_does(ledger):
    """Contracts §13.2 (owner, 2026-10-04): the noqual confirm must say the magic recoils,
    from whatever the server's card reports, never from a metal's name written into the
    page (fixes are world-agnostic: a world's own reactive metal must warn in its own
    words). With `assay_danger` sent, its words are the second --alarm line; a card that
    says `assay_danger: null` (a reactive ore that harms nobody) asks nothing."""
    assert f'<p class="fl-alarm">{RECOIL}</p>' in ledger["confirmWords"]
    # The real server's noqual card now carries the recoil in words (effectspec renders
    # `suppress_magic` since the 2026-10-04 merge); before that it sent nothing and the
    # confirm fell back on the general warning, which this line used to pin.
    assert '<p class="fl-alarm">Suppresses your active magic for 1d4 rounds</p>' \
        in ledger["confirm"], ledger["confirm"]
    assert "Testing it can turn on you" not in ledger["confirm"]
    assert ledger["quietOre"] is False
    js = _src(LEDGER)
    assert "noqual" not in re.sub(r"//.*", "", js).lower(), "the page names a metal"


def test_where_it_is_found_or_bought_is_said_in_words(ledger):
    """The card's "where found or bought" line, from the material's own `obtain`, `source`
    and `biomes` when the server sends them; nothing at all when it does not (a line
    guessed on the page would be a name the world never gave)."""
    assert ledger["found"] == "Mined in mountain or hills country."
    assert ledger["bought"] == "Bought at a market."
    assert ledger["monster"] == "Taken from monsters."
    assert ledger["foundNone"] == ""


def test_the_swatch_takes_only_a_plain_colour(ledger):
    """The swatch's colour goes into a style attribute, and it is the server's string: a
    value with a semicolon would let a material document restyle the card."""
    assert "fl-swatch" not in ledger["swatchBad"]
    assert 'style="background:#8a8d91"' in ledger["swatchGood"]


# --- the Journal ------------------------------------------------------------------------------

def test_the_journal_counts_what_is_known_from_the_ledger(served, ledger):
    """UI plan §6.7: every material met, with "3 of 7 known" counts. Those counts are the
    ledger's own `known` and `total` (rules/knowledge.py `ledger_row`), so the row for iron
    reads "1 of 7 known" and noqual "0 of 14 known", as the server sent them."""
    rows = {r["id"]: r for r in served["ledger"]["ledger"]}
    assert rows["iron"]["known"] == 1 and rows["iron"]["total"] == 7
    text = _text(ledger["rows"])
    assert "1 of 7 known" in text and f"0 of {rows['noqual']['total']} known" in text


def test_unknowns_first_puts_the_least_known_material_on_top(ledger):
    """The "Unknowns first" toggle: by name, Iron comes before Noqual; unknowns first,
    Noqual (14 unknown) must lead Iron (6 unknown). A toggle that changes its pressed state
    and not the order is the defect."""
    plain, first = ledger["rows"], ledger["rowsFirst"]
    assert plain.index('data-fl-mat="iron"') < plain.index('data-fl-mat="noqual"')
    assert first.index('data-fl-mat="noqual"') < first.index('data-fl-mat="iron"')


def test_the_journal_says_what_to_do_when_empty_reading_or_failed(ledger):
    """Empty, loading and error states (the skill's §4.5): an empty ledger invites the act
    that fills it, the read in flight says so, and a build without the ledger says the
    server's own sentence with a way to try again."""
    assert "No materials yet. Buy or mine one and it appears here." in ledger["rowsEmpty"]
    assert "Reading the ledger." in ledger["rowsReading"]
    assert "not available in this build yet" in ledger["rowsError"] and "data-fl-retry" in ledger["rowsError"]


def test_a_journal_row_opens_onto_the_cards_lines(ledger):
    """Each row is a disclosure: its button says expanded and controls the body, and the
    open body carries the same known and unknown lines the card shows."""
    html = ledger["rowsOpen"]
    assert 'data-fl-mat="iron" aria-expanded="true" aria-controls="fl-jr-card-iron"' in html
    assert 'id="fl-jr-card-iron" class="fl-jr-body">' in html
    assert "assayed, day 14" in html


def test_the_journal_mounts_the_ledger_beside_the_herbarium():
    """Read statically: 21 adds the "Smith's ledger" card after the herbarium, whose list
    id is not the heading's id (the history card's first cut replaced its own heading by
    sharing one), and draws it only when 44 is loaded, so a page without the forge shows
    no empty card."""
    js = _src(JOURNAL)
    assert 'sheetCard("jr-ledger", "Smith\'s ledger", `<div id="jr-ledger-list"></div>`' in js
    assert 'beside.insertAdjacentElement("afterend", card)' in js
    assert "window.ForgeLedger.journal(document.getElementById(\"jr-ledger-list\"))" in js
    assert "herbariumMount(); ledgerMount();" in js


def test_the_ledger_module_answers_its_contract(ledger):
    """Contracts §11: `ForgeLedger.card(materialId, anchorEl)` and `ForgeLedger.journal(host)`,
    the two names lane U2's forge calls; plus peek, unpeek, close and forget for the rack's
    hover and a step that reveals working traits."""
    assert ledger["api"] == []


# --- the perk picker ------------------------------------------------------------------------

def test_the_forge_picker_offers_its_four_perks_with_the_servers_words(served):
    """UI plan §6.8: "the herb picker with the forge's four perks (Potency, Hardening,
    Quality, Yield)". Each choice says what the next pick does in the server's words with
    its numbers (`perk_info[id].next`), the level line reads "Blacksmith", and the picks go
    to the forge's route. Duration is a herb perk; on the forge it would post a pick the
    server refuses."""
    track = dict(served["track"], picks_banked=2)
    run = _node("forge", {"track": track})
    assert run["has"] is True
    html = run["html"]
    for perk in ("potency", "hardening", "quality", "yield"):
        assert f'data-perk="{perk}"' in html
        assert track["perk_info"][perk]["next"] in html
    assert 'data-perk="duration"' not in html
    assert '<h3 id="forge-perks-t">Pick two perks</h3>' in html
    assert f"<p>Blacksmith {track['level']}. The same perk twice is allowed.</p>" in html
    assert ">Hardening" in html
    assert run["second"] is True, "a second picker opened over the first"
    assert 'Hardening <span class="pk-x">×2</span>' in run["picked"]
    assert run["posts"] == [["/api/forge/perks", {"picks": ["hardening", "hardening"]}]]
    assert run["saved"] == [["hardening", "hardening"]] and run["after"] == 1 and run["closed"]
    assert run["nothing"] and run["unknownTrack"]


# The herb picker's first two draws and its post, as the pre-change 36-bench-perks.js built
# them for HERB_TRACK (generated from a218b3a's file through this same harness).
HERB_FIRST = (
    '<div class="bench-scrim"></div><div class="bench-dialog bench-perks v2-framed v2-card-leather">'
    '<i class="v2-rim" aria-hidden="true"></i><h3 id="bench-perks-t">Pick two perks</h3>'
    '<p>Herbalist 4. The same perk twice is allowed.</p><div class="pk-grid">'
    '<button type="button" class="pk" data-perk="potency" aria-pressed="false"><span class="pk-main"><b>Potency</b>'
    '<span class="pk-next">+5% to the strength of what you make, total +10%</span><span class="pk-taken">Taken 1 time</span></span></button>'
    '<button type="button" class="pk" data-perk="duration" aria-pressed="false"><span class="pk-main"><b>Duration</b>'
    '<span class="pk-next">Your products last longer.</span><span class="pk-taken">Not taken yet</span></span></button>'
    '<button type="button" class="pk" data-perk="quality" aria-pressed="false"><span class="pk-main"><b>Quality</b>'
    '<span class="pk-next">Your ceiling rises one rung.</span><span class="pk-taken">Not taken yet</span></span></button>'
    '<button type="button" class="pk" data-perk="yield" aria-pressed="false"><span class="pk-main"><b>Extra yield</b>'
    '<span class="pk-next">A chance of an extra dose from each batch.</span><span class="pk-taken">Not taken yet</span></span></button>'
    '</div><p class="pk-left" role="status">2 to pick</p><div class="bench-dialog-acts">'
    '<button type="button" class="v2-btn is-quiet" data-pk="later">Later</button>'
    '<button type="button" class="v2-btn is-quiet" data-pk="clear" disabled>Clear</button>'
    '<button type="button" class="v2-btn is-go" data-pk="ok" disabled>Confirm</button></div></div>')


def test_the_herb_picker_is_byte_for_byte_what_it_was():
    """The parameterisation promised the herb bench no visible change: its picker is now
    the herbalist row of a two-track table. Its first draw is compared whole against the
    string the pre-change file built (a218b3a), and its picks still post to the herb route
    and are said the same way."""
    run = _node("herb", {"herbTrack": HERB_TRACK})
    assert run["first"] == HERB_FIRST
    assert '<b>Potency <span class="pk-x">×1</span></b>' in run["second"]
    assert run["posts"] == [["/api/bench/perks", {"picks": ["potency", "quality"]}]]
    assert run["said"] == ["Perks taken: potency, quality."] and run["closed"]


# --- static rules ------------------------------------------------------------------------------

def test_one_esc_closes_the_card_and_not_the_journal_under_it():
    """Seen live on 2026-10-04: with the card opened over the Journal, one Esc closed the
    card AND the Journal, because the card listened on the document's bubble phase beside
    the table's own Esc handler. Off the forge's layer the card (and its confirm) must take
    Esc in the capture phase and stop it there; on the layer it goes on the core's Esc
    stack, which already runs one closer per press."""
    code = _src(LEDGER)
    assert 'document.addEventListener("keydown", looseEsc, true)' in code
    block = code[code.index("looseEsc = function"):code.index('document.addEventListener("keydown", looseEsc, true)')]
    assert "e.stopPropagation()" in block
    assert 'document.addEventListener("keydown", onKey, true)' in code
    assert "h.pushEsc(escClose)" in code and "h.pushEsc(onEsc)" in code

def test_no_loop_no_dash_no_emoji_in_the_new_files():
    """The bench's standing rules (herb UI plan §8, §13.6, the skill's §9.G): nothing loops
    while idle (no setInterval, no requestAnimationFrame), zero em-dashes and en-dashes, and
    no emoji: the material card's `glyph` is the retired emoji (UI plan §2, "Retire on the
    forge: emoji glyphs") and must never be drawn."""
    for path in (LEDGER, PERKS):
        text = _src(path)
        assert not re.findall(r"\b(setInterval|requestAnimationFrame)\s*\(", text), path.name
        assert "—" not in text and "–" not in text, path.name
        assert not re.search("[\U0001F300-\U0001FAFF☀-➿]", text), path.name
    assert ".glyph" not in _src(LEDGER)
    new_journal = _src(JOURNAL)[_src(JOURNAL).index("// --- The smith's ledger"):]
    assert "—" not in new_journal and "–" not in new_journal
